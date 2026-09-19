import io
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from analytics.correlation import correlate_captures
from analytics.peeling_chain import detect_coinjoin_mixing, detect_peeling_chains
from analytics.risk_propagation import merge_ciou_risks, propagate_risk_scores
from analytics.shap_explainer import FEATURE_NAMES, explain_anomalies
from config import BASE_DIR
from db import queries
from db.neo4j_driver import run_query
from services.geoip import lookup_ip

logger = logging.getLogger("chainwatch.graph_builder")

MAX_GRAPH_TRANSACTIONS = 1200

# ── Cluster characterisation — dynamic label generation (R5) ─────────────────
_FEATURE_DESCRIPTORS = [
    ("tx_count",                "high-frequency"),
    ("total_volume_btc",        "high-volume"),
    ("unique_ip_count",         "multi-IP"),
    ("tx_velocity",             "burst-velocity"),
    ("amount_variance",         "irregular-amounts"),
    ("unique_asn_count",        "multi-ASN"),
    ("cross_state_ip_ratio",    "cross-jurisdiction"),
    ("avg_output_count",        "high-fan-out"),
    ("avg_src_port",            "high-src-port"),
    ("avg_dst_port",            "non-standard-port"),
    ("dst_src_state_match",     "cross-state-routing"),
    ("script_type_risk_ratio",  "high-risk-scripts"),
    ("balance_violation_ratio", "balance-violations"),
    ("avg_broadcast_confidence","low-confidence-broadcast"),
]

def _cluster_label_from_centroid(centroid: np.ndarray, scaler: StandardScaler) -> str:
    """
    Derive a human-readable cluster label from its centroid in scaled space
    by identifying which feature is furthest above its population mean.
    Falls back to 'General Activity Cluster' if nothing stands out.
    """
    if scaler is None or not hasattr(scaler, "mean_"):
        return "General Activity Cluster"

    # Un-scale centroid back to raw space, then compute z-scores
    raw = scaler.inverse_transform(centroid.reshape(1, -1))[0]
    z   = (raw - scaler.mean_) / (scaler.scale_ + 1e-9)

    # Take the top-2 features by z-score, build a compound label
    ranked = sorted(range(len(z)), key=lambda i: z[i], reverse=True)
    top    = [_FEATURE_DESCRIPTORS[i][1] for i in ranked[:2] if i < len(_FEATURE_DESCRIPTORS) and z[i] > 0.5]
    if not top:
        return "Baseline Activity Cluster"
    return " / ".join(top).title() + " Cluster"


# ── Safe list parser (replaces ast.literal_eval — fixes security issue) ───────
def _parse_list(raw: str) -> list:
    """
    Parse a stringified list from a CSV cell safely.
    Accepts both Python-style  ['a', 'b']  and JSON-style  ["a","b"].
    Raises ValueError with a clear message on failure.
    """
    s = str(raw).strip()
    # Try JSON first (standard format)
    try:
        result = json.loads(s)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try converting Python-style single quotes to JSON double quotes
    try:
        import re
        json_str = re.sub(r"'([^']*)'", r'"\1"', s)
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    raise ValueError(
        f"Cannot parse list field from CSV value: {s!r}. "
        "Expected JSON array [\"a\",\"b\"] or Python list ['a','b']."
    )


# ── Timestamp helper ──────────────────────────────────────────────────────────
def _parse_ts(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except Exception:
        return 0.0


# ── Feature matrix ────────────────────────────────────────────────────────────
def _build_feature_matrix(wallet_stats: dict, transaction_records: list) -> np.ndarray:
    """
    Build the 14-feature matrix used by IsolationForest and SHAP.

    Features (must match FEATURE_NAMES in shap_explainer.py — 14 total):
      0  tx_count
      1  total_volume_btc
      2  unique_ip_count
      3  tx_velocity
      4  amount_variance
      5  unique_asn_count
      6  cross_state_ip_ratio
      7  avg_output_count
      8  avg_src_port
      9  avg_dst_port
     10  dst_src_state_match
     11  script_type_risk_ratio    ← R2: P2SH/P2WSH fraction
     12  balance_violation_ratio   ← R2: input-output balance violations
     13  avg_broadcast_confidence  ← R3: IP correlation quality signal
    """
    txid_output_count = {r["txid"]: len(r["output_addresses"]) for r in transaction_records}

    rows = []
    for wallet, s in wallet_stats.items():
        txs = s.get("txs", [])

        # tx_velocity
        timestamps = [_parse_ts(t["timestamp"]) for t in txs if "timestamp" in t]
        if len(timestamps) >= 2:
            parsed      = sorted(timestamps)
            span_hours  = max((parsed[-1] - parsed[0]) / 3600.0, 1.0 / 60.0)
            tx_velocity = s["tx_count"] / span_hours
        else:
            tx_velocity = float(s["tx_count"])

        # amount_variance
        all_amounts = [t["amount"] for t in txs if "amount" in t]
        if all_amounts:
            mean_amt        = np.mean(all_amounts)
            amount_variance = float(np.std(all_amounts) / (mean_amt + 1e-9))
        else:
            amount_variance = 0.0

        # unique_asn_count
        unique_asn_count = len(set(a for a in s.get("asns", []) if a and a != "N/A"))

        # cross_state_ip_ratio
        unique_states        = len(set(s.get("states", ["Unknown"])))
        unique_ips           = max(len(s["ips"]), 1)
        cross_state_ip_ratio = unique_states / unique_ips

        # avg_output_count
        sent_txids = [t["txid"] for t in txs if t.get("type") == "SENT"]
        if sent_txids:
            out_counts       = [txid_output_count[tid] for tid in sent_txids if tid in txid_output_count]
            avg_output_count = float(np.mean(out_counts)) if out_counts else 1.0
        else:
            avg_output_count = 1.0

        # avg_src_port (R2)
        src_ports    = s.get("src_ports", [])
        avg_src_port = float(np.mean(src_ports)) if src_ports else 0.0

        # avg_dst_port (R2)
        dst_ports    = s.get("dst_ports", [])
        avg_dst_port = float(np.mean(dst_ports)) if dst_ports else 8333.0

        # dst_src_state_match (R3)
        dst_states = s.get("dst_states", [])
        src_states = s.get("states", [])
        if dst_states and src_states:
            pairs     = zip(src_states[-len(dst_states):], dst_states)
            mismatch  = sum(1 for s_st, d_st in pairs if s_st != d_st and d_st != "Unknown")
            dst_src_state_match = mismatch / max(len(dst_states), 1)
        else:
            dst_src_state_match = 0.0

        # script_type_risk_ratio (R2) — fraction of txns using P2SH/P2WSH/P2MS
        HIGH_RISK_SCRIPTS = {"P2SH", "P2WSH", "P2MS"}
        script_types = s.get("script_types", [])
        script_type_risk_ratio = (
            sum(1 for st in script_types if st in HIGH_RISK_SCRIPTS) / max(len(script_types), 1)
        )

        # balance_violation_ratio (R2) — fraction of txns with negative balance
        balance_violation_ratio = s.get("balance_violations", 0) / max(s["tx_count"], 1)

        # avg_broadcast_confidence (R3) — mean IP correlation confidence
        broadcast_confs = s.get("broadcast_confs", [1.0])
        avg_broadcast_confidence = float(np.mean(broadcast_confs)) if broadcast_confs else 1.0

        rows.append([
            float(s["tx_count"]),
            float(s["volume"]),
            float(len(s["ips"])),
            float(tx_velocity),
            float(amount_variance),
            float(unique_asn_count),
            float(cross_state_ip_ratio),
            float(avg_output_count),
            float(avg_src_port),
            float(avg_dst_port),
            float(dst_src_state_match),
            float(script_type_risk_ratio),
            float(balance_violation_ratio),
            float(avg_broadcast_confidence),
        ])

    return np.array(rows, dtype=float)


# ── Main pipeline ─────────────────────────────────────────────────────────────
def process_ledger_csv(contents: bytes) -> dict:
    """
    Full orchestration pipeline:
      1.  CSV parsing & GeoIP resolution (src_ip + dst_ip)
      2.  Broadcast IP exponential-decay correlation
      3.  Feature engineering (11 features incl. src_port, dst_port, dst_state)
      4.  IsolationForest anomaly detection
      5.  KMeans clustering with dynamic centroid-derived labels
      6.  SHAP TreeExplainer attributions
      7.  Peeling-chain & CoinJoin detection
      8.  Risk score propagation (BFS decay)
      9.  Neo4j batch MERGE writes
      10. JSON file outputs — anomaly_results sorted by risk_score desc
    """
    df = pd.read_csv(io.BytesIO(contents))

    wallet_stats: dict = defaultdict(lambda: {
        "tx_count": 0, "volume": 0.0, "ips": set(),
        "states": [], "asns": [], "orgs": [], "locations": [],
        "src_ports": [], "dst_ports": [], "dst_states": [],
        "script_types": [], "balance_violations": 0,
        "broadcast_confs": [],
    })
    transaction_records: list[dict] = []
    network_captures:    list[dict] = []
    rows_skipped         = 0
    rows_skipped_sample: list[str] = []

    # ── Step 1: parse rows ────────────────────────────────────────────────────
    for _, row in df.iterrows():
        txid      = str(row["txid"])
        src_ip    = str(row["src_ip"])
        timestamp = str(row.get("timestamp", pd.Timestamp.now().isoformat()))

        ip_info = lookup_ip(src_ip)
        state   = ip_info["state"] if ip_info["state"] != "Unknown" else str(row.get("geo_state", "Unknown"))
        asn     = ip_info["asn"]
        org     = ip_info["org"]

        # Safe list parsing (security fix — was ast.literal_eval)
        try:
            inputs         = _parse_list(str(row["input_addresses"]))
            amounts        = [float(a) for a in _parse_list(str(row["input_amounts"]))]
            outputs        = _parse_list(str(row["output_addresses"]))
            output_amounts = [float(a) for a in _parse_list(str(row["output_amounts"]))]
        except ValueError as exc:
            rows_skipped += 1
            if len(rows_skipped_sample) < 5:
                rows_skipped_sample.append(f"Row txid={txid}: {str(exc)[:80]}")
            logger.warning(f"Skipping malformed row txid={txid}: {exc}")
            continue

        # R2: parse port fields
        src_port = int(row["src_port"]) if "src_port" in row and pd.notna(row["src_port"]) else 0
        dst_port = int(row["dst_port"]) if "dst_port" in row and pd.notna(row["dst_port"]) else 8333

        # R2: parse fee (actual value, not hardcoded 0.0)
        fee = float(row["fee"]) if "fee" in row and pd.notna(row["fee"]) else 0.0

        # R2: parse script_type
        script_type = str(row["script_type"]) if "script_type" in row and pd.notna(row["script_type"]) else "P2PKH"

        # R3: dst_ip enrichment
        dst_ip      = str(row.get("dst_ip", "Unknown"))
        dst_ip_info = lookup_ip(dst_ip)
        dst_state   = dst_ip_info["state"]

        transaction_records.append({
            "txid":             txid,
            "timestamp":        timestamp,
            "src_ip":           src_ip,
            "dst_ip":           dst_ip,
            "src_port":         src_port,
            "dst_port":         dst_port,
            "fee":              fee,
            "script_type":      script_type,
            "src_ip_info":      ip_info,
            "dst_ip_info":      dst_ip_info,
            "input_addresses":  inputs,
            "input_amounts":    amounts,
            "output_addresses": outputs,
            "output_amounts":   output_amounts,
        })

        network_captures.append({"txid": txid, "src_ip": src_ip, "timestamp": timestamp})

        for wallet, amt in zip(inputs, amounts):
            ws = wallet_stats[wallet]
            ws["tx_count"] += 1
            ws["volume"]   += float(amt)
            ws["ips"].add(src_ip)
            ws["states"].append(state)
            ws["asns"].append(asn)
            ws["orgs"].append(org)
            ws["src_ports"].append(src_port)
            ws["dst_ports"].append(dst_port)
            ws["dst_states"].append(dst_state)
            ws["script_types"].append(script_type)
            ws.setdefault("txs", []).append({
                "txid": txid, "type": "SENT",
                "amount": float(amt), "ip": src_ip, "timestamp": timestamp,
            })
            if ip_info["latitude"] is not None and ip_info["longitude"] is not None:
                ws["locations"].append((ip_info["latitude"], ip_info["longitude"]))

        # Balance verification — sum(inputs) - sum(outputs) - fee should be >= 0
        balance_check = sum(amounts) - sum(output_amounts) - fee
        if balance_check < -0.0001:
            for wallet in inputs:
                wallet_stats[wallet]["balance_violations"] += 1

        for wallet, amt in zip(outputs, output_amounts):
            ws = wallet_stats[wallet]
            ws.setdefault("txs", []).append({
                "txid": txid, "type": "RECEIVED",
                "amount": float(amt), "ip": src_ip, "timestamp": timestamp,
            })

    # ── Step 2: broadcast correlation ────────────────────────────────────────
    correlated_ips    = correlate_captures(network_captures)
    ip_confidence_map = {(c["txid"], c["src_ip"]): c["confidence"] for c in correlated_ips}

    # ── Step 2b: back-fill avg_broadcast_confidence per wallet ───────────────
    # ip_confidence_map is now available; loop transaction_records to accumulate
    # per-wallet confidence scores (cannot be done inline above — map built after)
    for record in transaction_records:
        conf = ip_confidence_map.get((record["txid"], record["src_ip"]), 1.0)
        for wallet in record["input_addresses"]:
            wallet_stats[wallet]["broadcast_confs"].append(conf)

    # ── Steps 3–6: ML pipeline ────────────────────────────────────────────────
    wallets  = list(wallet_stats.keys())
    features = _build_feature_matrix(wallet_stats, transaction_records)  # (n, 11)

    anomaly_results:     list[dict] = []
    seed_threat_wallets: dict       = {}
    cluster_name_map:    dict       = {}

    if len(wallets) > 0:
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(features)

        # IsolationForest
        iso        = IsolationForest(n_estimators=200, contamination=0.10, random_state=42)
        iso_labels = iso.fit_predict(X_scaled)
        iso_scores = iso.decision_function(X_scaled)

        # KMeans with dynamic centroid-derived cluster labels (R5 fix)
        n_clusters     = min(6, len(wallets))
        kmeans         = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(X_scaled)

        # Build cluster name map from centroids — not hardcoded strings
        cluster_name_map = {
            cid: _cluster_label_from_centroid(kmeans.cluster_centers_[cid], scaler)
            for cid in range(n_clusters)
        }

        flagged_idx = [i for i, lbl in enumerate(iso_labels) if lbl == -1]

        if flagged_idx:
            flagged_scores = iso_scores[flagged_idx]
            lo, hi         = float(flagged_scores.min()), float(flagged_scores.max())
        else:
            lo, hi = 0.0, 1.0
        score_range = (hi - lo) if hi != lo else 1e-9

        # SHAP — FEATURE_NAMES is now the canonical 11-feature registry
        shap_results = explain_anomalies(
            iso_model=iso,
            X_scaled=X_scaled,
            X_raw=features,
            scaler=scaler,
            wallet_indices=flagged_idx,
            feature_names=FEATURE_NAMES,
            top_k=3,
        )

        for i in flagged_idx:
            w    = wallets[i]
            s    = wallet_stats[w]
            conf = round(60 + 39 * (hi - float(iso_scores[i])) / score_range, 1)
            seed_threat_wallets[w] = conf

            primary_state = Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown"
            primary_asn   = Counter(s["asns"]).most_common(1)[0][0]   if s["asns"]   else "N/A"
            primary_org   = Counter(s["orgs"]).most_common(1)[0][0]   if s["orgs"]   else "N/A"

            shap_data         = shap_results.get(i, {})
            shap_attributions = shap_data.get("shap_attributions", [])
            reason            = shap_data.get("reason") or (
                f"AI anomaly: {s['tx_count']} TXNs, {s['volume']:.4f} BTC, {len(s['ips'])} IPs."
            )

            cid = int(cluster_labels[i])
            anomaly_results.append({
                "wallet_address":    w,
                "confidence_score":  conf,
                "cluster_id":        cid,
                "cluster_name":      cluster_name_map.get(cid, "Activity Cluster"),
                "reason":            reason,
                "shap_attributions": shap_attributions,
                "correlated_txids":  list({t["txid"] for t in s.get("txs", [])})[:20],
                "tx_count":          s["tx_count"],
                "total_volume_btc":  round(s["volume"], 4),
                "unique_ip_count":   len(s["ips"]),
                "primary_state":     primary_state,
                "asn":               primary_asn,
                "isp":               primary_org,
                "lat": round(float(np.mean([loc[0] for loc in s["locations"]])), 6) if s["locations"] else None,
                "lng": round(float(np.mean([loc[1] for loc in s["locations"]])), 6) if s["locations"] else None,
            })

    # ── Step 7: peeling chain & CoinJoin ─────────────────────────────────────
    peeling_chains  = detect_peeling_chains(transaction_records, min_hops=3)
    coinjoin_mixers = detect_coinjoin_mixing(transaction_records)

    for chain in peeling_chains:
        for w in chain["wallets_involved"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), chain["risk_score"])
    for mix in coinjoin_mixers:
        for w in mix["input_wallets"] + mix["output_wallets"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), mix["risk_score"])

    # ── Step 8: risk propagation ──────────────────────────────────────────────
    propagated_risks = propagate_risk_scores(
        transaction_records, seed_threat_wallets, decay_factor=0.70
    )
    # CIOU boost: co-spending wallets inherit risk from flagged peers
    propagated_risks = merge_ciou_risks(propagated_risks, transaction_records)

    for alert in anomaly_results:
        w = alert["wallet_address"]
        if w in propagated_risks:
            alert["risk_score"]   = propagated_risks[w]["risk_score"]
            alert["risk_factors"] = propagated_risks[w]["risk_factors"]

    # R6 fix: sort alerts by risk_score descending so FILE #1 = highest threat
    anomaly_results.sort(
        key=lambda a: a.get("risk_score") or a.get("confidence_score") or 0.0,
        reverse=True,
    )

    # ── Step 9: Neo4j batch MERGE writes ──────────────────────────────────────
    try:
        logger.info("Wiping previous graph data for clean ingestion…")
        run_query(*queries.clear_all_data(), write=True)

        batch_wallets = [
            {
                "address": wallet,
                "state":   Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown",
            }
            for wallet, s in wallet_stats.items()
        ]
        batch_risks = [
            {
                "address":      wallet,
                "risk_score":   info.get("risk_score", 0.0),
                "risk_factors": info.get("risk_factors", []),
                "flagged":      wallet in seed_threat_wallets,
            }
            for wallet, info in propagated_risks.items()
        ]

        batch_txs        = []
        batch_sent       = []
        batch_rec        = []
        batch_ips_dict   = {}
        batch_broadcasts = []
        batch_ciou       = []

        for record in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
            txid = record["txid"]
            # R2 fix: write actual fee from CSV, not hardcoded 0.0
            batch_txs.append({
                "txid":      txid,
                "timestamp": record["timestamp"],
                "fee":       record["fee"],
            })

            for wallet, amt in zip(record["input_addresses"], record["input_amounts"]):
                batch_sent.append({"wallet_address": wallet, "txid": txid, "amount": amt})

            for wallet, amt in zip(record["output_addresses"], record["output_amounts"]):
                batch_rec.append({"txid": txid, "wallet_address": wallet, "amount": amt})

            src_ip  = record["src_ip"]
            ip_info = record["src_ip_info"]
            batch_ips_dict[src_ip] = {
                "address": src_ip,
                "asn":     ip_info["asn"],
                "org":     ip_info["org"],
                "state":   ip_info["state"],
                "lat":     ip_info["latitude"],
                "lon":     ip_info["longitude"],
            }

            conf = ip_confidence_map.get((txid, src_ip), 1.0)
            batch_broadcasts.append({"ip_address": src_ip, "txid": txid, "confidence": conf})

            inp_list = record["input_addresses"]
            if len(inp_list) > 1:
                for a_idx in range(len(inp_list)):
                    for b_idx in range(a_idx + 1, len(inp_list)):
                        a, b = sorted([inp_list[a_idx], inp_list[b_idx]])
                        batch_ciou.append({"a": a, "b": b, "reason": "CIOU"})

        if batch_wallets:
            run_query(*queries.batch_merge_wallets(batch_wallets), write=True)
        if batch_risks:
            run_query(*queries.batch_update_wallet_risks(batch_risks), write=True)
        if batch_txs:
            run_query(*queries.batch_merge_transactions(batch_txs), write=True)
        if batch_sent:
            run_query(*queries.batch_merge_sent_relationships(batch_sent), write=True)
        if batch_rec:
            run_query(*queries.batch_merge_received_relationships(batch_rec), write=True)
        if batch_ips_dict:
            run_query(*queries.batch_merge_ips(list(batch_ips_dict.values())), write=True)
        if batch_broadcasts:
            run_query(*queries.batch_merge_broadcast_relationships(batch_broadcasts), write=True)
        if batch_ciou:
            run_query(*queries.batch_merge_same_entity_relationships(batch_ciou), write=True)

        logger.info("✅ Neo4j batch write completed.")
    except Exception as exc:
        logger.warning(f"Neo4j write skipped (file-backed fallback active): {exc}")

    # ── Step 10: build JSON graph + persist files ─────────────────────────────
    wallet_shap_lookup: dict[str, list] = {
        alert["wallet_address"]: alert.get("shap_attributions", [])
        for alert in anomaly_results
    }

    nodes: dict[str, dict] = {}
    links: dict[str, dict] = {}

    for record in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
        tx_id    = f"tx:{record['txid']}"
        tx_value = sum(record["input_amounts"]) + sum(record["output_amounts"])
        nodes[tx_id] = {
            "id":          tx_id,
            "type":        "transaction",
            "label":       record["txid"][:12],
            "value":       round(tx_value, 4),
            "fee":         record["fee"],
            "script_type": record["script_type"],
        }

        ip_key  = record["src_ip"]
        ip_info = record["src_ip_info"]
        ip_id   = f"ip:{ip_key}"
        nodes[ip_id] = {
            "id":           ip_id,
            "type":         "ip",
            "label":        ip_key,
            "ip":           ip_key,
            "state":        ip_info["state"],
            "asn":          ip_info["asn"],
            "organization": ip_info["org"],
            "latitude":     ip_info["latitude"],
            "longitude":    ip_info["longitude"],
        }

        link_id = f"BROADCASTED:{ip_id}:{tx_id}"
        links[link_id] = {
            "id":     link_id,
            "source": ip_id,
            "target": tx_id,
            "type":   "BROADCASTED",
            "value":  ip_confidence_map.get((record["txid"], ip_key), 1.0),
        }

        for wallet, amount in zip(record["input_addresses"], record["input_amounts"]):
            w_id      = f"wallet:{wallet}"
            risk_data = propagated_risks.get(wallet, {})
            nodes[w_id] = {
                "id":                w_id,
                "type":              "wallet",
                "label":             wallet[:12],
                "address":           wallet,
                "state":             ip_info["state"],
                "flagged":           wallet in seed_threat_wallets,
                "risk_score":        risk_data.get("risk_score", 0.0),
                "risk_factors":      risk_data.get("risk_factors", []),
                "shap_attributions": wallet_shap_lookup.get(wallet, []),
            }
            l_id = f"INPUT_TO_TX:{w_id}:{tx_id}"
            links[l_id] = {"id": l_id, "source": w_id, "target": tx_id, "type": "INPUT_TO_TX", "value": amount}

        for wallet, amount in zip(record["output_addresses"], record["output_amounts"]):
            w_id      = f"wallet:{wallet}"
            risk_data = propagated_risks.get(wallet, {})
            nodes[w_id] = {
                "id":                w_id,
                "type":              "wallet",
                "label":             wallet[:12],
                "address":           wallet,
                "state":             ip_info["state"],
                "flagged":           wallet in seed_threat_wallets,
                "risk_score":        risk_data.get("risk_score", 0.0),
                "risk_factors":      risk_data.get("risk_factors", []),
                "shap_attributions": wallet_shap_lookup.get(wallet, []),
            }
            l_id = f"OUTPUT_TO_WALLET:{tx_id}:{w_id}"
            links[l_id] = {"id": l_id, "source": tx_id, "target": w_id, "type": "OUTPUT_TO_WALLET", "value": amount}

    # ── SAME_ENTITY_AS (CIOU) co-spending edges → graph JSON ─────────────────
    seen_ciou: set = set()
    for record in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
        inp_list = record["input_addresses"]
        if len(inp_list) > 1:
            for a_idx in range(len(inp_list)):
                for b_idx in range(a_idx + 1, len(inp_list)):
                    a, b     = sorted([inp_list[a_idx], inp_list[b_idx]])
                    edge_key = f"SAME_ENTITY:{a}:{b}"
                    if edge_key not in seen_ciou:
                        seen_ciou.add(edge_key)
                        # Only add if both wallet nodes exist in the graph
                        if f"wallet:{a}" in nodes and f"wallet:{b}" in nodes:
                            links[edge_key] = {
                                "id":     edge_key,
                                "source": f"wallet:{a}",
                                "target": f"wallet:{b}",
                                "type":   "SAME_ENTITY_AS",
                                "value":  1,
                            }

    graph_payload = {
        "nodes":             list(nodes.values()),
        "links":             list(links.values()),
        "transaction_count": len(transaction_records),
        "peeling_chains":    peeling_chains,
        "coinjoin_mixers":   coinjoin_mixers,
    }

    with open(BASE_DIR / "anomaly_results.json", "w") as fh:
        json.dump(anomaly_results, fh, indent=2)

    with open(BASE_DIR / "stats.json", "w") as fh:
        json.dump(
            {
                "total_transactions":      len(df),
                "total_wallets":           len(wallets),
                "anomalies_detected":      len(anomaly_results),
                "peeling_chains_detected": len(peeling_chains),
                "coinjoin_mixers_detected": len(coinjoin_mixers),
                "wallet_locations": [
                    {
                        "wallet_address":   wallet,
                        "primary_state":    Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown",
                        "is_threat":        wallet in seed_threat_wallets,
                        "confidence_score": seed_threat_wallets.get(wallet, 0.0),
                        "risk_score":       propagated_risks.get(wallet, {}).get("risk_score", 0.0),
                        "risk_factors":     propagated_risks.get(wallet, {}).get("risk_factors", []),
                        "tx_count":         s.get("tx_count", 0),
                        "total_volume_btc": round(s.get("volume", 0.0), 4),
                        "latitude":  round(float(np.mean([loc[0] for loc in s["locations"]])), 6) if s["locations"] else None,
                        "longitude": round(float(np.mean([loc[1] for loc in s["locations"]])), 6) if s["locations"] else None,
                        "transactions": s.get("txs", [])[:10],
                    }
                    for wallet, s in wallet_stats.items()
                ],
            },
            fh,
            indent=2,
        )

    with open(BASE_DIR / "graph.json", "w") as fh:
        json.dump(graph_payload, fh, indent=2)

    return {
        "message":                 "Ingestion and Forensic ML Analysis Complete",
        "anomalies_found":         len(anomaly_results),
        "peeling_chains_found":    len(peeling_chains),
        "coinjoin_mixers_found":   len(coinjoin_mixers),
        "propagated_risk_wallets": len(propagated_risks),
        "rows_skipped":            rows_skipped,
        "rows_skipped_sample":     rows_skipped_sample,
        "graph_truncated":         len(transaction_records) > MAX_GRAPH_TRANSACTIONS,
        "graph_transaction_count": min(len(transaction_records), MAX_GRAPH_TRANSACTIONS),
        "total_transaction_count": len(transaction_records),
    }

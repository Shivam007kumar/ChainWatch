"""
ingestion/pipeline.py
──────────────────────
New orchestrator for the ChainWatch forensic pipeline.

TRANSITION STATE:
  graph_builder.py continues to run as the ACTIVE pipeline.
  This module wires together the new modular components (anomaly.py,
  clustering.py, evidence.py, validator.py) and will replace
  graph_builder.py ONLY after tests/test_integration.py confirms
  equivalent detection output.

  Do NOT call this from main.py until that gate is passed.

Architecture:
  CSV bytes
    ↓ ingestion/parser.py       → raw row dicts
    ↓ ingestion/validator.py    → CanonicalTransaction[]
    ↓ services/geoip.py         → src_geo / dst_geo enrichment
    ↓ analytics/correlation.py  → broadcast_confidence per tx
    ↓ _build_feature_matrix()   → 14-feature np.ndarray
    ↓ analytics/anomaly.py      → DetectionResult[] (IsolationForest + SHAP)
    ↓ analytics/clustering.py   → wallet → cluster_name dict
    ↓ analytics/peeling_chain.py→ DetectionResult[] (peeling, coinjoin)
    ↓ analytics/risk_propagation→ DetectionResult[] (BFS + CIOU)
    ↓ services/evidence.py      → Alert[] (aggregated, persisted)
    ↓ db/queries/               → Neo4j batch writes
    ↓ JSON file outputs          → backward-compatible fallback
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from analytics import correlation as _correlation
from analytics import anomaly as _anomaly
from analytics import clustering as _clustering
from analytics.peeling_chain import detect_peeling_chains, detect_coinjoin_mixing
from analytics.risk_propagation import propagate_risk_scores, merge_ciou_risks
from config import BASE_DIR
from ingestion.validator import validate_rows
from models.domain.alert import DetectionResult, Evidence, risk_to_severity
from models.domain.job import IngestionJob, PipelineStage
from services.evidence import aggregate_evidence
from services.geoip import lookup_ip

logger = logging.getLogger("chainwatch.pipeline")

# Maximum transactions written to Neo4j / graph JSON (performance guard)
MAX_GRAPH_TRANSACTIONS = 1200


# ── Timestamp helper ──────────────────────────────────────────────────────────
def _parse_ts(ts) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except Exception:
        return 0.0


# ── Safe list parser ──────────────────────────────────────────────────────────
def _parse_list(raw: str) -> list:
    """json.loads first, single-quote regex fallback."""
    import re
    s = str(raw).strip()
    try:
        result = json.loads(s)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        json_str = re.sub(r"'([^']*)'", r'"\1"', s)
        result = json.loads(json_str)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    raise ValueError(f"Cannot parse list: {s!r}")


# ── Feature matrix (must stay in sync with analytics/anomaly.py) ─────────────
def _build_feature_matrix(wallet_stats: dict, transaction_records: list) -> np.ndarray:
    """14-feature matrix — identical to graph_builder.py implementation."""
    txid_out_count = {r["txid"]: len(r["output_addresses"]) for r in transaction_records}
    HIGH_RISK = {"P2SH", "P2WSH", "P2MS"}
    rows = []

    for wallet, s in wallet_stats.items():
        txs = s.get("txs", [])

        # tx_velocity
        tss = sorted([_parse_ts(t["timestamp"]) for t in txs if "timestamp" in t])
        if len(tss) >= 2:
            span = max((tss[-1] - tss[0]) / 3600.0, 1.0 / 60.0)
            tx_velocity = s["tx_count"] / span
        else:
            tx_velocity = float(s["tx_count"])

        # amount_variance
        amts = [t["amount"] for t in txs if "amount" in t]
        amount_variance = float(np.std(amts) / (np.mean(amts) + 1e-9)) if amts else 0.0

        unique_asn_count     = len(set(a for a in s.get("asns", []) if a and a != "N/A"))
        cross_state_ip_ratio = len(set(s.get("states", ["Unknown"]))) / max(len(s["ips"]), 1)

        sent = [t["txid"] for t in txs if t.get("type") == "SENT"]
        out_counts = [txid_out_count[tid] for tid in sent if tid in txid_out_count]
        avg_output_count = float(np.mean(out_counts)) if out_counts else 1.0

        avg_src_port = float(np.mean(s.get("src_ports", [0]))) if s.get("src_ports") else 0.0
        avg_dst_port = float(np.mean(s.get("dst_ports", [8333]))) if s.get("dst_ports") else 8333.0

        dst_st = s.get("dst_states", [])
        src_st = s.get("states", [])
        if dst_st and src_st:
            pairs = zip(src_st[-len(dst_st):], dst_st)
            mismatch = sum(1 for a, b in pairs if a != b and b != "Unknown")
            dst_src_state_match = mismatch / max(len(dst_st), 1)
        else:
            dst_src_state_match = 0.0

        script_types = s.get("script_types", [])
        script_type_risk_ratio = (
            sum(1 for st in script_types if st in HIGH_RISK) / max(len(script_types), 1)
        )

        balance_violation_ratio = s.get("balance_violations", 0) / max(s["tx_count"], 1)

        confs = s.get("broadcast_confs", [1.0])
        avg_broadcast_confidence = float(np.mean(confs)) if confs else 1.0

        rows.append([
            float(s["tx_count"]), float(s["volume"]), float(len(s["ips"])),
            float(tx_velocity), float(amount_variance), float(unique_asn_count),
            float(cross_state_ip_ratio), float(avg_output_count),
            float(avg_src_port), float(avg_dst_port), float(dst_src_state_match),
            float(script_type_risk_ratio), float(balance_violation_ratio),
            float(avg_broadcast_confidence),
        ])

    return np.array(rows, dtype=float)


# ── Main pipeline entry point ──────────────────────────────────────────────────
def run_pipeline(
    contents: bytes,
    filename: str = "ledger.csv",
    job: IngestionJob | None = None,
    job_store=None,
) -> dict:
    """
    Execute the full forensic pipeline on raw CSV bytes.

    Parameters
    ----------
    contents   : raw CSV bytes from the uploaded file
    filename   : original filename (for dataset metadata)
    job        : optional IngestionJob — if provided, stage updates are written
    job_store  : optional JobStore — used only when job is provided

    Returns
    -------
    dict compatible with graph_builder.process_ledger_csv() return shape
    (enables drop-in replacement after integration test gate)
    """

    def _stage(stage: PipelineStage, **kwargs):
        if job and job_store:
            job_store.update_stage(job.job_id, stage, **kwargs)
        logger.info(f"Pipeline stage: {stage.value}")

    t0 = time.monotonic()

    # ── Dataset identity ──────────────────────────────────────────────────────
    dataset_id = hashlib.sha256(contents).hexdigest()[:16]

    _stage(PipelineStage.VALIDATING)

    df = pd.read_csv(io.BytesIO(contents))
    raw_rows = df.to_dict("records")

    # Use new validator — builds CanonicalTransaction objects
    valid_txs, rejected = validate_rows(raw_rows, dataset_id=dataset_id)

    rows_skipped        = len(rejected)
    rows_skipped_sample = [r.reason for r in rejected[:5]]

    if job:
        job.records_total   = len(raw_rows)
        job.records_skipped = rows_skipped

    _stage(PipelineStage.GEOIP_ENRICHMENT)

    # Build the wallet_stats and transaction_records in the format the
    # existing ML functions expect (dict-based, for now)
    wallet_stats: dict = defaultdict(lambda: {
        "tx_count": 0, "volume": 0.0, "ips": set(),
        "states": [], "asns": [], "orgs": [], "locations": [],
        "src_ports": [], "dst_ports": [], "dst_states": [],
        "script_types": [], "balance_violations": 0,
        "broadcast_confs": [],
    })
    transaction_records: list[dict] = []
    network_captures:    list[dict] = []

    for tx in valid_txs:
        # GeoIP enrichment
        ip_info      = lookup_ip(tx.src_ip)
        dst_ip_info  = lookup_ip(tx.dst_ip)
        state        = ip_info["state"] if ip_info["state"] != "Unknown" else "Unknown"

        rec = {
            "txid":             tx.txid,
            "timestamp":        tx.timestamp.isoformat(),
            "src_ip":           tx.src_ip,
            "dst_ip":           tx.dst_ip,
            "src_port":         tx.src_port,
            "dst_port":         tx.dst_port,
            "fee":              tx.fee,
            "script_type":      tx.script_type,
            "src_ip_info":      ip_info,
            "dst_ip_info":      dst_ip_info,
            "input_addresses":  tx.input_addresses,
            "input_amounts":    tx.input_amounts,
            "output_addresses": tx.output_addresses,
            "output_amounts":   tx.output_amounts,
        }
        transaction_records.append(rec)
        network_captures.append({"txid": tx.txid, "src_ip": tx.src_ip,
                                  "timestamp": tx.timestamp.isoformat()})

        for wallet, amt in zip(tx.input_addresses, tx.input_amounts):
            ws = wallet_stats[wallet]
            ws["tx_count"]   += 1
            ws["volume"]     += amt
            ws["ips"].add(tx.src_ip)
            ws["states"].append(state)
            ws["asns"].append(ip_info["asn"])
            ws["orgs"].append(ip_info["org"])
            ws["src_ports"].append(tx.src_port)
            ws["dst_ports"].append(tx.dst_port)
            ws["dst_states"].append(dst_ip_info["state"])
            ws["script_types"].append(tx.script_type)
            ws.setdefault("txs", []).append({
                "txid": tx.txid, "type": "SENT", "amount": amt,
                "ip": tx.src_ip, "timestamp": tx.timestamp.isoformat(),
            })
            if tx.has_balance_violation:
                ws["balance_violations"] += 1
            if ip_info["latitude"] and ip_info["longitude"]:
                ws["locations"].append((ip_info["latitude"], ip_info["longitude"]))

        for wallet, amt in zip(tx.output_addresses, tx.output_amounts):
            ws = wallet_stats[wallet]
            ws.setdefault("txs", []).append({
                "txid": tx.txid, "type": "RECEIVED", "amount": amt,
                "ip": tx.src_ip, "timestamp": tx.timestamp.isoformat(),
            })

    _stage(PipelineStage.BROADCAST_CORRELATION)

    correlated   = _correlation.correlate_captures(network_captures)
    conf_map     = {(c["txid"], c["src_ip"]): c["confidence"] for c in correlated}

    for rec in transaction_records:
        c = conf_map.get((rec["txid"], rec["src_ip"]), 1.0)
        for wallet in rec["input_addresses"]:
            wallet_stats[wallet]["broadcast_confs"].append(c)

    _stage(PipelineStage.FEATURE_ENGINEERING)

    wallets  = list(wallet_stats.keys())
    features = _build_feature_matrix(wallet_stats, transaction_records)

    if not wallets:
        return _empty_result(dataset_id, rows_skipped, rows_skipped_sample,
                             len(transaction_records), t0)

    scaler   = StandardScaler()
    scaler.fit(features)

    _stage(PipelineStage.ANOMALY_DETECTION)

    anomaly_results, iso_model, X_scaled = _anomaly.run(
        wallets=wallets, features=features,
        wallet_stats=wallet_stats, scaler=scaler,
    )

    seed_threat_wallets = {
        dr.entity_id: dr.risk_score for dr in anomaly_results
    }

    _stage(PipelineStage.SHAP)
    # SHAP runs inside _anomaly.run() — nothing extra needed here

    _stage(PipelineStage.CLUSTERING)

    cluster_map = _clustering.run(
        wallets=wallets, X_scaled=X_scaled, scaler=scaler,
    )

    _stage(PipelineStage.PEELING_DETECTION)

    peeling_chains  = detect_peeling_chains(transaction_records, min_hops=3)
    for chain in peeling_chains:
        for w in chain["wallets_involved"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), chain["risk_score"])

    _stage(PipelineStage.COINJOIN_DETECTION)

    coinjoin_mixers = detect_coinjoin_mixing(transaction_records)
    for mix in coinjoin_mixers:
        for w in mix["input_wallets"] + mix["output_wallets"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), mix["risk_score"])

    _stage(PipelineStage.RISK_PROPAGATION)

    propagated_risks = propagate_risk_scores(
        transaction_records, seed_threat_wallets, decay_factor=0.70
    )
    propagated_risks = merge_ciou_risks(propagated_risks, transaction_records)

    # Merge propagated risk back onto anomaly DetectionResults
    # so evidence.py sees the final scores
    propagated_drs: list[DetectionResult] = []
    for wallet, info in propagated_risks.items():
        if wallet in seed_threat_wallets:
            continue   # already in anomaly_results
        propagated_drs.append(DetectionResult(
            detector    = "risk_propagation",
            entity_type = "wallet",
            entity_id   = wallet,
            risk_score  = info["risk_score"],
            anomaly_score = None,
            confidence  = None,
            evidence    = [],
            metadata    = {
                "risk_factors":  info.get("risk_factors", []),
                "distance":      info.get("distance", 0),
                "primary_state": Counter(wallet_stats[wallet]["states"]).most_common(1)[0][0]
                                 if wallet_stats[wallet]["states"] else "Unknown",
            },
        ))

    all_detection_results = anomaly_results + propagated_drs

    # Enrich anomaly DetectionResults with cluster_name and propagated risk
    for dr in anomaly_results:
        dr.metadata["cluster_name"]  = cluster_map.get(dr.entity_id, "Activity Cluster")
        pr = propagated_risks.get(dr.entity_id, {})
        if pr:
            dr.risk_score = max(dr.risk_score, pr.get("risk_score", 0.0))
            dr.metadata["risk_factors"]     = pr.get("risk_factors", [])
            dr.metadata["correlated_txids"] = list(
                {t["txid"] for t in wallet_stats[dr.entity_id].get("txs", [])}
            )[:20]

    _stage(PipelineStage.NEO4J_PERSISTENCE)

    # Build and persist alerts via evidence aggregator
    alerts = aggregate_evidence(all_detection_results, dataset_id)

    try:
        from db import queries
        from db.neo4j_driver import run_query

        run_query(*queries.clear_all_data(), write=True)

        # Wallet MERGE
        batch_wallets = [
            {"address": w, "state": Counter(s["states"]).most_common(1)[0][0]
             if s["states"] else "Unknown"}
            for w, s in wallet_stats.items()
        ]
        if batch_wallets:
            run_query(*queries.batch_merge_wallets(batch_wallets), write=True)

        # Risk updates
        batch_risks = [
            {"address": w, "risk_score": info["risk_score"],
             "risk_factors": info.get("risk_factors", []),
             "flagged": w in seed_threat_wallets}
            for w, info in propagated_risks.items()
        ]
        if batch_risks:
            run_query(*queries.batch_update_wallet_risks(batch_risks), write=True)

        batch_txs = batch_sent = batch_rec = []
        batch_ips: dict = {}
        batch_bcast = batch_ciou = batch_dst = []

        batch_txs   = [{"txid": r["txid"], "timestamp": r["timestamp"],
                         "fee": r["fee"], "script_type": r["script_type"]}
                        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]]
        batch_sent  = [{"wallet_address": w, "txid": r["txid"], "amount": a}
                        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]
                        for w, a in zip(r["input_addresses"], r["input_amounts"])]
        batch_rec   = [{"txid": r["txid"], "wallet_address": w, "amount": a}
                        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]
                        for w, a in zip(r["output_addresses"], r["output_amounts"])]
        batch_ips   = {r["src_ip"]: {
                         "address": r["src_ip"],
                         "asn": r["src_ip_info"]["asn"],
                         "org": r["src_ip_info"]["org"],
                         "state": r["src_ip_info"]["state"],
                         "lat": r["src_ip_info"]["latitude"],
                         "lon": r["src_ip_info"]["longitude"],
                       } for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]}
        batch_bcast = [{"ip_address": r["src_ip"], "txid": r["txid"],
                         "confidence": conf_map.get((r["txid"], r["src_ip"]), 1.0)}
                        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]]
        batch_ciou  = []
        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
            inp = r["input_addresses"]
            if len(inp) > 1:
                for ai in range(len(inp)):
                    for bi in range(ai + 1, len(inp)):
                        a, b = sorted([inp[ai], inp[bi]])
                        batch_ciou.append({"a": a, "b": b, "reason": "CIOU"})
        batch_dst   = [{"txid": r["txid"], "dst_ip": r["dst_ip"],
                         "dst_asn": r["dst_ip_info"]["asn"],
                         "dst_state": r["dst_ip_info"]["state"],
                         "src_port": r["src_port"], "dst_port": r["dst_port"],
                         "timestamp": r["timestamp"]}
                        for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]
                        if r["dst_ip"] and r["dst_ip"] != "Unknown"]

        if batch_txs:
            run_query(*queries.batch_merge_transactions(batch_txs), write=True)
        if batch_sent:
            run_query(*queries.batch_merge_sent_relationships(batch_sent), write=True)
        if batch_rec:
            run_query(*queries.batch_merge_received_relationships(batch_rec), write=True)
        if batch_ips:
            run_query(*queries.batch_merge_ips(list(batch_ips.values())), write=True)
        if batch_bcast:
            run_query(*queries.batch_merge_broadcast_relationships(batch_bcast), write=True)
        if batch_ciou:
            run_query(*queries.batch_merge_same_entity_relationships(batch_ciou), write=True)
        if batch_dst:
            run_query(*queries.batch_merge_observed_destinations(batch_dst), write=True)

        # Dataset isolation
        run_query(*queries.merge_dataset(dataset_id, filename, len(transaction_records)), write=True)
        all_addrs = list(wallet_stats.keys())
        all_txids = [r["txid"] for r in transaction_records[:MAX_GRAPH_TRANSACTIONS]]
        all_ips   = list(batch_ips.keys())
        if all_addrs: run_query(*queries.batch_link_dataset_wallets(dataset_id, all_addrs), write=True)
        if all_txids: run_query(*queries.batch_link_dataset_txs(dataset_id, all_txids), write=True)
        if all_ips:   run_query(*queries.batch_link_dataset_ips(dataset_id, all_ips), write=True)

        # Alert persistence
        alert_props = [a.to_neo4j_props() for a in alerts]
        if alert_props:
            run_query(*queries.batch_merge_alerts(alert_props), write=True)

        logger.info("✅ Neo4j batch write completed (new pipeline).")
    except Exception as exc:
        logger.warning(f"Neo4j write skipped (file-backed fallback): {exc}")

    _stage(PipelineStage.FINALIZING)

    # ── Write JSON files (backward-compatible) ────────────────────────────────
    _write_json_outputs(
        wallet_stats, transaction_records, peeling_chains, coinjoin_mixers,
        propagated_risks, seed_threat_wallets, alerts, conf_map, BASE_DIR,
    )

    elapsed = round(time.monotonic() - t0, 2)
    if job:
        job.elapsed_seconds          = elapsed
        job.anomalies_found          = len([a for a in alerts if a.detector == "isolation_forest"])
        job.peeling_chains_found     = len(peeling_chains)
        job.coinjoin_mixers_found    = len(coinjoin_mixers)
        job.propagated_risk_wallets  = len(propagated_risks)
        job.records_processed        = len(transaction_records)

    return {
        "message":                 "Ingestion and Forensic ML Analysis Complete",
        "dataset_id":              dataset_id,
        "anomalies_found":         len([a for a in alerts if a.detector == "isolation_forest"]),
        "peeling_chains_found":    len(peeling_chains),
        "coinjoin_mixers_found":   len(coinjoin_mixers),
        "propagated_risk_wallets": len(propagated_risks),
        "rows_skipped":            rows_skipped,
        "rows_skipped_sample":     rows_skipped_sample,
        "graph_truncated":         len(transaction_records) > MAX_GRAPH_TRANSACTIONS,
        "graph_transaction_count": min(len(transaction_records), MAX_GRAPH_TRANSACTIONS),
        "total_transaction_count": len(transaction_records),
    }


def _empty_result(dataset_id, rows_skipped, rows_skipped_sample, total, t0):
    return {
        "message":                 "No valid transactions to process.",
        "dataset_id":              dataset_id,
        "anomalies_found":         0,
        "peeling_chains_found":    0,
        "coinjoin_mixers_found":   0,
        "propagated_risk_wallets": 0,
        "rows_skipped":            rows_skipped,
        "rows_skipped_sample":     rows_skipped_sample,
        "graph_truncated":         False,
        "graph_transaction_count": 0,
        "total_transaction_count": total,
    }


def _write_json_outputs(wallet_stats, transaction_records, peeling_chains,
                         coinjoin_mixers, propagated_risks, seed_threat_wallets,
                         alerts, conf_map, base_dir):
    """Write anomaly_results.json, stats.json, graph.json (backward compat)."""
    import json as _json

    anomaly_list = []
    for a in alerts:
        if a.detector != "isolation_forest":
            continue
        w = a.entity_id
        s = wallet_stats.get(w, {})
        anomaly_list.append({
            "wallet_address":    w,
            "confidence_score":  round(a.risk_score, 1),
            "cluster_id":        0,
            "cluster_name":      a.cluster_name,
            "reason":            a.evidence[0]["details"].get("reason", "") if a.evidence else "",
            "shap_attributions": a.shap_attributions,
            "correlated_txids":  a.correlated_txids,
            "tx_count":          s.get("tx_count", 0),
            "total_volume_btc":  round(s.get("volume", 0.0), 4),
            "unique_ip_count":   len(s.get("ips", set())),
            "primary_state":     a.primary_state,
            "asn":               Counter(s.get("asns", ["N/A"])).most_common(1)[0][0] if s.get("asns") else "N/A",
            "isp":               Counter(s.get("orgs", ["N/A"])).most_common(1)[0][0] if s.get("orgs") else "N/A",
            "risk_score":        round(a.risk_score, 1),
            "risk_factors":      a.risk_factors,
        })

    with open(base_dir / "anomaly_results.json", "w") as fh:
        _json.dump(anomaly_list, fh, indent=2)

    wallets = list(wallet_stats.keys())
    with open(base_dir / "stats.json", "w") as fh:
        _json.dump({
            "total_transactions":       len(transaction_records),
            "total_wallets":            len(wallets),
            "anomalies_detected":       len(anomaly_list),
            "peeling_chains_detected":  len(peeling_chains),
            "coinjoin_mixers_detected": len(coinjoin_mixers),
            "wallet_locations": [
                {
                    "wallet_address":   w,
                    "primary_state":    Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown",
                    "is_threat":        w in seed_threat_wallets,
                    "confidence_score": seed_threat_wallets.get(w, 0.0),
                    "risk_score":       propagated_risks.get(w, {}).get("risk_score", 0.0),
                    "risk_factors":     propagated_risks.get(w, {}).get("risk_factors", []),
                    "tx_count":         s.get("tx_count", 0),
                    "total_volume_btc": round(s.get("volume", 0.0), 4),
                    "latitude":  round(float(np.mean([loc[0] for loc in s["locations"]])), 6) if s["locations"] else None,
                    "longitude": round(float(np.mean([loc[1] for loc in s["locations"]])), 6) if s["locations"] else None,
                    "transactions": s.get("txs", [])[:10],
                }
                for w, s in wallet_stats.items()
            ],
        }, fh, indent=2)

    # graph.json — minimal compatible format
    with open(base_dir / "graph.json", "w") as fh:
        _json.dump({
            "nodes": [], "links": [],
            "transaction_count": len(transaction_records),
            "peeling_chains":    peeling_chains,
            "coinjoin_mixers":   coinjoin_mixers,
        }, fh, indent=2)

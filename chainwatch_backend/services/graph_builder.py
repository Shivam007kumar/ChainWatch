import ast
import io
import json
import logging
from collections import defaultdict, Counter
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from config import BASE_DIR
from services.geoip import lookup_ip
from analytics.correlation import correlate_captures
from analytics.peeling_chain import detect_peeling_chains, detect_coinjoin_mixing
from analytics.risk_propagation import propagate_risk_scores
from db.neo4j_driver import run_query
from db import queries

logger = logging.getLogger("chainwatch.graph_builder")
MAX_GRAPH_TRANSACTIONS = 1200


def process_ledger_csv(contents: bytes) -> dict:
    """
    Complete orchestration pipeline:
      1. Feature extraction & GeoIP resolution
      2. Broadcast correlation
      3. Machine Learning (IsolationForest + KMeans)
      4. Peeling Chain & CoinJoin Detection
      5. Risk Score Propagation
      6. Neo4j Idempotent MERGE Graph Writes (Batch Cypher for speed)
    """
    df = pd.read_csv(io.BytesIO(contents))
    
    wallet_stats = defaultdict(lambda: {
        "tx_count": 0, "volume": 0.0, "ips": set(), "states": list(),
        "asns": list(), "orgs": list(), "locations": list()
    })
    transaction_records = []
    network_captures = []

    for _, row in df.iterrows():
        txid = str(row["txid"])
        src_ip = str(row["src_ip"])
        timestamp = str(row.get("timestamp", pd.Timestamp.now().isoformat()))
        
        ip_info = lookup_ip(src_ip)
        state = ip_info["state"] if ip_info["state"] != "Unknown" else str(row.get("geo_state", "Unknown"))
        asn = ip_info["asn"]
        org = ip_info["org"]

        inputs = ast.literal_eval(str(row["input_addresses"]))
        amounts = [float(a) for a in ast.literal_eval(str(row["input_amounts"]))]
        outputs = ast.literal_eval(str(row["output_addresses"]))
        output_amounts = [float(a) for a in ast.literal_eval(str(row["output_amounts"]))]

        dst_ip = str(row.get("dst_ip", "Unknown"))
        dst_ip_info = lookup_ip(dst_ip)

        transaction_records.append({
            "txid": txid,
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_ip_info": ip_info,
            "dst_ip_info": dst_ip_info,
            "input_addresses": inputs,
            "input_amounts": amounts,
            "output_addresses": outputs,
            "output_amounts": output_amounts,
        })

        network_captures.append({
            "txid": txid,
            "src_ip": src_ip,
            "timestamp": timestamp
        })

        for wallet, amt in zip(inputs, amounts):
            ws = wallet_stats[wallet]
            ws["tx_count"] += 1
            ws["volume"] += float(amt)
            ws["ips"].add(src_ip)
            ws["states"].append(state)
            ws["asns"].append(asn)
            ws["orgs"].append(org)
            ws.setdefault("txs", []).append({"txid": txid, "type": "SENT", "amount": float(amt), "ip": src_ip, "timestamp": timestamp})
            if ip_info["latitude"] is not None and ip_info["longitude"] is not None:
                ws["locations"].append((ip_info["latitude"], ip_info["longitude"]))

        for wallet, amt in zip(outputs, output_amounts):
            ws = wallet_stats[wallet]
            ws.setdefault("txs", []).append({"txid": txid, "type": "RECEIVED", "amount": float(amt), "ip": src_ip, "timestamp": timestamp})

    # 1. Exponential Decay Broadcast IP Correlation
    correlated_ips = correlate_captures(network_captures)
    ip_confidence_map = {(c["txid"], c["src_ip"]): c["confidence"] for c in correlated_ips}

    # 2. Machine Learning Pipeline
    wallets = list(wallet_stats.keys())
    features = np.array([[s["tx_count"], s["volume"], len(s["ips"])] for s in wallet_stats.values()])
    
    if len(wallets) > 0:
        X_scaled = StandardScaler().fit_transform(features)
        iso = IsolationForest(n_estimators=200, contamination=0.10, random_state=42)
        iso_labels = iso.fit_predict(X_scaled)
        iso_scores = iso.decision_function(X_scaled)
        
        kmeans = KMeans(n_clusters=min(6, len(wallets)), random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(X_scaled)
        CLUSTER_NAMES = [
            "Micro-Transactor Ring", "High-Volume Laundering Node",
            "Multi-Hop Relay Cluster", "Dormant-then-Active",
            "Cross-Border Cell", "Retail Node"
        ]

        flagged_idx = [i for i in range(len(wallets)) if iso_labels[i] == -1]
        lo, hi = (min(iso_scores[flagged_idx]), max(iso_scores[flagged_idx])) if flagged_idx else (0, 1)
        score_range = (hi - lo) if hi != lo else 1e-9

        anomaly_results = []
        seed_threat_wallets = {}

        for i in flagged_idx:
            w = wallets[i]
            s = wallet_stats[w]
            conf = round(60 + 39 * (hi - iso_scores[i]) / score_range, 1)
            seed_threat_wallets[w] = conf

            primary_state = Counter(s["states"]).most_common(1)[0][0]
            primary_asn = Counter(s["asns"]).most_common(1)[0][0]
            primary_org = Counter(s["orgs"]).most_common(1)[0][0]

            anomaly_results.append({
                "wallet_address": w,
                "confidence_score": conf,
                "cluster_id": int(cluster_labels[i]),
                "cluster_name": CLUSTER_NAMES[int(cluster_labels[i])],
                "reason": f"AI detected {s['tx_count']} rapid TXNs masking {s['volume']:.2f} BTC across {len(s['ips'])} distinct IPs.",
                "tx_count": s["tx_count"],
                "total_volume_btc": round(s["volume"], 4),
                "unique_ip_count": len(s["ips"]),
                "primary_state": primary_state,
                "asn": primary_asn,
                "isp": primary_org,
                "lat": round(np.mean([loc[0] for loc in s["locations"]]), 6) if s["locations"] else None,
                "lng": round(np.mean([loc[1] for loc in s["locations"]]), 6) if s["locations"] else None
            })
    else:
        anomaly_results = []
        seed_threat_wallets = {}

    # 3. Peeling Chain & CoinJoin Detection
    peeling_chains = detect_peeling_chains(transaction_records, min_hops=3)
    coinjoin_mixers = detect_coinjoin_mixing(transaction_records)

    for chain in peeling_chains:
        for w in chain["wallets_involved"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), chain["risk_score"])
    for mix in coinjoin_mixers:
        for w in mix["input_wallets"] + mix["output_wallets"]:
            seed_threat_wallets[w] = max(seed_threat_wallets.get(w, 0.0), mix["risk_score"])

    # 4. Risk Score Propagation
    propagated_risks = propagate_risk_scores(transaction_records, seed_threat_wallets, decay_factor=0.70)

    for alert in anomaly_results:
        w = alert["wallet_address"]
        if w in propagated_risks:
            alert["risk_score"] = propagated_risks[w]["risk_score"]
            alert["risk_factors"] = propagated_risks[w]["risk_factors"]

    # 5. High-Performance Batch Neo4j Graph Writes
    try:
        logger.info("Wiping previous database graph data for clean ingestion...")
        run_query(*queries.clear_all_data(), write=True)
        logger.info("Batch writing nodes and edges to Neo4j database...")
        
        # Prepare Batch Data
        batch_wallets = [
            {
                "address": wallet,
                "state": Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown"
            }
            for wallet, s in wallet_stats.items()
        ]
        
        batch_risks = [
            {
                "address": wallet,
                "risk_score": risk_info.get("risk_score", 0.0),
                "risk_factors": risk_info.get("risk_factors", []),
                "flagged": (wallet in seed_threat_wallets)
            }
            for wallet, risk_info in propagated_risks.items()
        ]

        batch_txs = []
        batch_sent = []
        batch_rec = []
        batch_ips_dict = {}
        batch_broadcasts = []
        batch_ciou = []

        for record in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
            txid = record["txid"]
            batch_txs.append({"txid": txid, "timestamp": record["timestamp"], "fee": 0.0})

            for wallet, amt in zip(record["input_addresses"], record["input_amounts"]):
                batch_sent.append({"wallet_address": wallet, "txid": txid, "amount": amt})

            for wallet, amt in zip(record["output_addresses"], record["output_amounts"]):
                batch_rec.append({"txid": txid, "wallet_address": wallet, "amount": amt})

            src_ip = record["src_ip"]
            ip_info = record["src_ip_info"]
            batch_ips_dict[src_ip] = {
                "address": src_ip, "asn": ip_info["asn"], "org": ip_info["org"],
                "state": ip_info["state"], "lat": ip_info["latitude"], "lon": ip_info["longitude"]
            }

            conf = ip_confidence_map.get((txid, src_ip), 1.0)
            batch_broadcasts.append({"ip_address": src_ip, "txid": txid, "confidence": conf})

            inputs = record["input_addresses"]
            if len(inputs) > 1:
                for idx1 in range(len(inputs)):
                    for idx2 in range(idx1 + 1, len(inputs)):
                        a, b = sorted([inputs[idx1], inputs[idx2]])
                        batch_ciou.append({"a": a, "b": b, "reason": "CIOU"})

        # Execute Batch Cypher Writes
        if batch_wallets:
            q, p = queries.batch_merge_wallets(batch_wallets)
            run_query(q, p, write=True)

        if batch_risks:
            q, p = queries.batch_update_wallet_risks(batch_risks)
            run_query(q, p, write=True)

        if batch_txs:
            q, p = queries.batch_merge_transactions(batch_txs)
            run_query(q, p, write=True)

        if batch_sent:
            q, p = queries.batch_merge_sent_relationships(batch_sent)
            run_query(q, p, write=True)

        if batch_rec:
            q, p = queries.batch_merge_received_relationships(batch_rec)
            run_query(q, p, write=True)

        if batch_ips_dict:
            q, p = queries.batch_merge_ips(list(batch_ips_dict.values()))
            run_query(q, p, write=True)

        if batch_broadcasts:
            q, p = queries.batch_merge_broadcast_relationships(batch_broadcasts)
            run_query(q, p, write=True)

        if batch_ciou:
            q, p = queries.batch_merge_same_entity_relationships(batch_ciou)
            run_query(q, p, write=True)

        logger.info("✅ Neo4j Graph batch write completed successfully.")
    except Exception as e:
        logger.warning(f"Neo4j database write skipped or failed (operating in file-backed fallback): {e}")

    # 6. Build Local JSON Graph fallback
    nodes = {}
    links = {}

    for record in transaction_records[:MAX_GRAPH_TRANSACTIONS]:
        tx_id = f"tx:{record['txid']}"
        tx_value = sum(record["input_amounts"]) + sum(record["output_amounts"])
        nodes[tx_id] = {"id": tx_id, "type": "transaction", "label": record["txid"][:12], "value": round(tx_value, 4)}

        ip_key = record["src_ip"]
        ip_info = record["src_ip_info"]
        ip_id = f"ip:{ip_key}"
        nodes[ip_id] = {
            "id": ip_id, "type": "ip", "label": ip_key, "ip": ip_key,
            "state": ip_info["state"], "asn": ip_info["asn"], "organization": ip_info["org"],
            "latitude": ip_info["latitude"], "longitude": ip_info["longitude"]
        }

        link_id = f"BROADCASTED:{ip_id}:{tx_id}"
        links[link_id] = {
            "id": link_id, "source": ip_id, "target": tx_id,
            "type": "BROADCASTED", "value": ip_confidence_map.get((record["txid"], ip_key), 1.0)
        }

        for wallet, amount in zip(record["input_addresses"], record["input_amounts"]):
            w_id = f"wallet:{wallet}"
            risk_data = propagated_risks.get(wallet, {})
            nodes[w_id] = {
                "id": w_id, "type": "wallet", "label": wallet[:12], "address": wallet,
                "state": record["src_ip_info"]["state"], "flagged": (wallet in seed_threat_wallets),
                "risk_score": risk_data.get("risk_score", 0.0),
                "risk_factors": risk_data.get("risk_factors", [])
            }
            l_id = f"INPUT_TO_TX:{w_id}:{tx_id}"
            links[l_id] = {"id": l_id, "source": w_id, "target": tx_id, "type": "INPUT_TO_TX", "value": amount}

        for wallet, amount in zip(record["output_addresses"], record["output_amounts"]):
            w_id = f"wallet:{wallet}"
            risk_data = propagated_risks.get(wallet, {})
            nodes[w_id] = {
                "id": w_id, "type": "wallet", "label": wallet[:12], "address": wallet,
                "state": record["src_ip_info"]["state"], "flagged": (wallet in seed_threat_wallets),
                "risk_score": risk_data.get("risk_score", 0.0),
                "risk_factors": risk_data.get("risk_factors", [])
            }
            l_id = f"OUTPUT_TO_WALLET:{tx_id}:{w_id}"
            links[l_id] = {"id": l_id, "source": tx_id, "target": w_id, "type": "OUTPUT_TO_WALLET", "value": amount}

    graph_payload = {
        "nodes": list(nodes.values()),
        "links": list(links.values()),
        "transaction_count": len(transaction_records),
        "peeling_chains": peeling_chains,
        "coinjoin_mixers": coinjoin_mixers
    }

    # Save JSON files
    with open(BASE_DIR / "anomaly_results.json", "w") as f:
        json.dump(anomaly_results, f, indent=2)

    with open(BASE_DIR / "stats.json", "w") as f:
        json.dump({
            "total_transactions": len(df),
            "total_wallets": len(wallets),
            "anomalies_detected": len(anomaly_results),
            "peeling_chains_detected": len(peeling_chains),
            "coinjoin_mixers_detected": len(coinjoin_mixers),
            "wallet_locations": [
                {
                    "wallet_address": wallet,
                    "primary_state": Counter(stats["states"]).most_common(1)[0][0] if stats["states"] else "Unknown",
                    "is_threat": wallet in seed_threat_wallets,
                    "confidence_score": seed_threat_wallets.get(wallet, 0.0),
                    "risk_score": propagated_risks.get(wallet, {}).get("risk_score", 0.0),
                    "risk_factors": propagated_risks.get(wallet, {}).get("risk_factors", []),
                    "tx_count": stats.get("tx_count", 0),
                    "total_volume_btc": round(stats.get("volume", 0.0), 4),
                    "latitude": round(np.mean([loc[0] for loc in stats["locations"]]), 6) if stats["locations"] else None,
                    "longitude": round(np.mean([loc[1] for loc in stats["locations"]]), 6) if stats["locations"] else None,
                    "transactions": stats.get("txs", [])[:10]
                }
                for wallet, stats in wallet_stats.items()
            ]
        }, f, indent=2)

    with open(BASE_DIR / "graph.json", "w") as f:
        json.dump(graph_payload, f, indent=2)

    return {
        "message": "Ingestion and Forensic ML Analysis Complete",
        "anomalies_found": len(anomaly_results),
        "peeling_chains_found": len(peeling_chains),
        "coinjoin_mixers_found": len(coinjoin_mixers),
        "propagated_risk_wallets": len(propagated_risks)
    }

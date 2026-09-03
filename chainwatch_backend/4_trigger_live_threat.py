#!/usr/bin/env python3
"""
ChainWatch — Live Threat Injector (Terminal Command)
Run this during the presentation to simulate a real-time anomaly detection.
"""

import json
import csv
import time
import random

CSV_FILE = "synthetic_bitcoin_traffic.csv"
ANOMALY_FILE = "anomaly_results.json"
STATS_FILE = "stats.json"

def trigger_live_threat():
    print("\n[+] INITIALIZING LIVE THREAT MONITORING...")
    time.sleep(1)
    print("[+] Scanning network mempool for anomalous state-level routing...")
    time.sleep(2)

    # 1. Fetch ACTUAL data from the CSV (Find a high-volume MH transaction)
    print("[!] Deep-Packet Inspection: Analyzing recent blocks...")
    time.sleep(1.5)
    
    target_tx = None
    with open(CSV_FILE, "r") as f:
        reader = list(csv.DictReader(f))
        # Filter for Maharashtra transactions
        mh_txs = [row for row in reader if row.get("geo_state") == "Maharashtra"]
        if mh_txs:
            target_tx = random.choice(mh_txs)
        else:
            target_tx = random.choice(reader) # Fallback

    txid = target_tx["txid"]
    wallet = eval(target_tx["input_addresses"])[0]
    volume = sum(eval(target_tx["input_amounts"]))
    
    print(f"\n[⚠️] CRITICAL ANOMALY DETECTED!")
    print(f"    -> State: Maharashtra")
    print(f"    -> Wallet: {wallet}")
    print(f"    -> Volume: {volume:.4f} BTC")
    print(f"    -> TXID: {txid}")
    time.sleep(1)

    # 2. Update the anomaly_results.json
    print("\n[+] Pushing threat signature to API layer...")
    with open(ANOMALY_FILE, "r") as f:
        anomalies = json.load(f)

    live_alert = {
        "wallet_address": wallet,
        "confidence_score": 99.9,
        "cluster_id": 1,
        "cluster_name": "Active Ransomware Cash-Out",
        "reason": f"LIVE INTRUSION: Real-time isolation forest detected sudden burst. Wallet {wallet[:8]}... moved {volume:.4f} BTC via Maharashtra nodes.",
        "tx_count": random.randint(45, 80),
        "total_volume_btc": round(volume * random.randint(10, 50), 4),
        "unique_ip_count": random.randint(5, 12),
        "high_risk_hits": random.randint(20, 40),
        "sample_txid": txid,
        "is_live_injection": True # We will use this flag in React to trigger the red flashing!
    }

    # Insert at the top
    anomalies.insert(0, live_alert)

    with open(ANOMALY_FILE, "w") as f:
        json.dump(anomalies, f, indent=2)

    # 3. Update stats.json to reflect the new anomaly
    with open(STATS_FILE, "r") as f:
        stats = json.load(f)
    
    stats["anomalies_detected"] += 1
    stats["high_risk_wallets"] += 1

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    print("[+] API Cache updated successfully.")
    print("[+] Dashboard will sync in < 3 seconds...\n")

if __name__ == "__main__":
    trigger_live_threat()
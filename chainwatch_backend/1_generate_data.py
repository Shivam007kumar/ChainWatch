"""
ChainWatch — Synthetic Bitcoin Traffic Generator (v2)
======================================================
Fixes the v1 bug: v1 generated a brand-new random wallet/IP for every
transaction, so no wallet ever appeared twice. That made every ML feature
(tx_count, unique_ip_count, country_diversity) constant at ~1 for every
wallet — which is why every alert got the same generic "reason" and the
model was effectively just finding the top of a uniform amount distribution.

v2 fixes this by:
  1. Sampling wallets/IPs from a small fixed pool, so real entities recur
     across transactions (this is also just more realistic — real Bitcoin
     addresses get reused).
  2. Explicitly planting a handful of "seed" anomalous wallets with
     deliberately suspicious behavior (high tx frequency, many distinct
     IPs, multiple high-risk-country hits). This gives you real ground
     truth to cite: "we planted N known-bad wallets, our model recovered
     M of them" — a genuinely stronger claim than an unlabeled guess.
"""

import csv
import json
import random
import uuid
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)  # reproducible for demo/debugging

NUM_RECORDS = 200
WALLET_POOL_SIZE = 45
IP_POOL_SIZE = 30
NUM_PLANTED_ANOMALIES = 6

COUNTRIES = ['India', 'Russia', 'USA', 'China', 'Nigeria', 'Unknown']
COUNTRY_WEIGHTS = [40, 20, 20, 10, 5, 5]
HIGH_RISK = {"Russia", "Nigeria", "Unknown"}

# ── Pools ──────────────────────────────────────────────────────────────────
wallet_pool = [fake.sha256()[:34] for _ in range(WALLET_POOL_SIZE)]
ip_pool = [fake.ipv4() for _ in range(IP_POOL_SIZE)]

# Planted anomalous wallets: pulled from the same pool, but we'll bias
# transaction generation to route through them disproportionately, with
# high-risk countries and multiple IPs.
planted_anomalies = random.sample(wallet_pool, NUM_PLANTED_ANOMALIES)


def make_transaction(force_anomalous=False):
    """Generate one transaction record. If force_anomalous, bias wallet
    selection toward planted anomalies and use high-risk countries."""
    src_ip = random.choice(ip_pool)
    dst_ip = random.choice(ip_pool)

    if force_anomalous:
        geo_country = random.choice(list(HIGH_RISK))
        # bias inputs/outputs toward planted anomalous wallets
        pool_for_pick = planted_anomalies + random.sample(
            wallet_pool, k=min(2, len(wallet_pool))
        )
        n_in = random.randint(1, 3)
        n_out = random.randint(1, 3)
        inputs = random.choices(pool_for_pick, k=n_in)
        outputs = random.choices(pool_for_pick, k=n_out)
    else:
        geo_country = random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0]
        n_in = random.randint(1, 3)
        n_out = random.randint(1, 3)
        inputs = random.sample(wallet_pool, k=min(n_in, len(wallet_pool)))
        outputs = random.sample(wallet_pool, k=min(n_out, len(wallet_pool)))

    input_amounts = [round(random.uniform(0.1, 5.0), 4) for _ in inputs]
    output_amounts = [round(random.uniform(0.1, 5.0), 4) for _ in outputs]

    return {
        "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 10000))).isoformat(),
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": random.randint(1024, 65535),
        "dst_port": 8333,
        "txid": uuid.uuid4().hex,
        "input_addresses": inputs,
        "output_addresses": outputs,
        "input_amounts": input_amounts,
        "output_amounts": output_amounts,
        "geo_country": geo_country,
    }


def generate_crypto_data():
    data = []
    # ~15% of transactions are deliberately routed through planted
    # anomalous wallets, so those wallets accumulate real tx_count,
    # unique_ip_count, and high_risk_hits — the features your reasons
    # actually key off.
    for _ in range(NUM_RECORDS):
        force = random.random() < 0.15
        data.append(make_transaction(force_anomalous=force))
    return data


if __name__ == "__main__":
    records = generate_crypto_data()

    keys = records[0].keys()
    with open("synthetic_bitcoin_traffic.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(records)

    # Save ground truth separately — used for optional precision/recall
    # reporting in your technical write-up, not consumed by the API.
    with open("ground_truth.json", "w") as f:
        json.dump({"planted_anomalous_wallets": planted_anomalies}, f, indent=2)

    print(f"✅ Generated {NUM_RECORDS} rows -> synthetic_bitcoin_traffic.csv")
    print(f"   Wallet pool: {WALLET_POOL_SIZE} | IP pool: {IP_POOL_SIZE}")
    print(f"   Planted anomalous wallets ({NUM_PLANTED_ANOMALIES}): saved to ground_truth.json")
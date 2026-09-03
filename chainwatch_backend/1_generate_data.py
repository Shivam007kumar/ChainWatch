"""
ChainWatch — Synthetic Bitcoin Traffic Generator (v3 - Scaled for SIH)
Generates up to 10,000 transactions mapped to Indian States.
"""

import csv
import json
import random
import uuid
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)

# ── Scale Parameters (Massive Dataset) ──
NUM_RECORDS = 10000
WALLET_POOL_SIZE = 800
IP_POOL_SIZE = 300
NUM_PLANTED_ANOMALIES = 15

# ── NTRO Domestic Theme (Indian States) ──
INDIAN_STATES = [
    'Maharashtra', 'Delhi', 'Karnataka', 'Gujarat', 
    'Tamil Nadu', 'West Bengal', 'Uttar Pradesh', 
    'Telangana', 'Kerala', 'Rajasthan'
]
STATE_WEIGHTS = [25, 20, 15, 10, 10, 5, 5, 5, 3, 2]

# We will train the ML to recognize these specific states as high-risk origins
# for this specific cyber-threat scenario.
HIGH_RISK_STATES = {"Maharashtra", "Delhi", "West Bengal"}

# ── Pools ──────────────────────────────────────────────────────────────────
wallet_pool = [fake.sha256()[:34] for _ in range(WALLET_POOL_SIZE)]
ip_pool = [fake.ipv4() for _ in range(IP_POOL_SIZE)]
planted_anomalies = random.sample(wallet_pool, NUM_PLANTED_ANOMALIES)

def make_transaction(force_anomalous=False):
    src_ip = random.choice(ip_pool)
    dst_ip = random.choice(ip_pool)

    if force_anomalous:
        geo_state = random.choice(list(HIGH_RISK_STATES))
        pool_for_pick = planted_anomalies + random.sample(wallet_pool, k=5)
        n_in, n_out = random.randint(2, 5), random.randint(1, 3)
        inputs = random.choices(pool_for_pick, k=n_in)
        outputs = random.choices(pool_for_pick, k=n_out)
    else:
        geo_state = random.choices(INDIAN_STATES, weights=STATE_WEIGHTS)[0]
        n_in, n_out = random.randint(1, 3), random.randint(1, 3)
        inputs = random.sample(wallet_pool, k=n_in)
        outputs = random.sample(wallet_pool, k=n_out)

    # Realistic BTC amounts (Anomalies move larger volumes)
    multiplier = 5.0 if force_anomalous else 1.0
    input_amounts = [round(random.uniform(0.01, 2.5) * multiplier, 4) for _ in inputs]
    output_amounts = [round(random.uniform(0.01, 2.5) * multiplier, 4) for _ in outputs]

    return {
        "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 43200))).isoformat(),
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": random.randint(1024, 65535),
        "dst_port": 8333,
        "txid": uuid.uuid4().hex,
        "input_addresses": inputs,
        "output_addresses": outputs,
        "input_amounts": input_amounts,
        "output_amounts": output_amounts,
        "geo_state": geo_state, # Changed from geo_country
    }

def generate_crypto_data():
    data = []
    for _ in range(NUM_RECORDS):
        force = random.random() < 0.12 # 12% of 10k = ~1,200 anomalous TXs
        data.append(make_transaction(force_anomalous=force))
    return data

if __name__ == "__main__":
    print(f"⏳ Generating {NUM_RECORDS} bulk transactions...")
    records = generate_crypto_data()

    keys = records[0].keys()
    with open("synthetic_bitcoin_traffic.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(records)

    with open("ground_truth.json", "w") as f:
        json.dump({"planted_anomalous_wallets": planted_anomalies}, f, indent=2)

    print(f"✅ Generated {NUM_RECORDS} rows -> synthetic_bitcoin_traffic.csv")
    print(f"   Wallet pool: {WALLET_POOL_SIZE} | IP pool: {IP_POOL_SIZE}")
    print(f"   Planted anomalous wallets ({NUM_PLANTED_ANOMALIES}): saved to ground_truth.json")
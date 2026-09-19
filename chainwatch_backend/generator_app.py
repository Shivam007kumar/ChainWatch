import streamlit as st
import pandas as pd
import numpy as np
import random
import uuid
import json as _json
from datetime import datetime, timedelta
from ipaddress import IPv4Address, ip_address
from pathlib import Path
from faker import Faker

# --- CONFIGURATION ---
st.set_page_config(page_title="NTRO Data Generator", page_icon="🛡️", layout="wide")
fake = Faker()
BASE_DIR = Path(__file__).resolve().parent
IP_REFERENCE_FILE = BASE_DIR.parent / "IP_Address.csv"

st.markdown("""
<style>
    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }
    .hero {
        padding: 1.4rem 1.6rem;
        border-radius: 14px;
        background: linear-gradient(120deg, #102a43 0%, #1f5f78 100%);
        color: white;
        margin-bottom: 1.5rem;
    }
    .hero h1 { margin: 0; font-size: 2.2rem; }
    .hero p { margin: 0.45rem 0 0; color: #d9f0f2; }
    .target-card {
        padding: 1rem 1.1rem;
        border-left: 4px solid #e09f3e;
        border-radius: 8px;
        background: #fff8ec;
        margin: 0.5rem 0 1rem;
    }
    .target-label { color: #825b19; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; }
    .target-state { color: #102a43; font-size: 1.15rem; font-weight: 700; margin-top: 0.2rem; }
    .qa-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        margin: 1rem 0 1.5rem;
    }
    .qa-card {
        padding: 1rem 1.1rem;
        border: 1px solid #d9e2ec;
        border-radius: 10px;
        background: #f8fafc;
        min-height: 142px;
    }
    .qa-question { color: #102a43; font-weight: 700; margin-bottom: 0.5rem; }
    .qa-answer { color: #52606d; font-size: 0.92rem; line-height: 1.5; }
    @media (max-width: 900px) { .qa-grid { grid-template-columns: 1fr; } }
</style>
""", unsafe_allow_html=True)

INDIAN_STATES = [
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", 
    "Chandigarh", "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", 
    "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", 
    "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", 
    "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", 
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

# --- EDUCATIONAL UI ---
st.markdown("""
<div class="hero">
    <h1>🛡️ ChainWatch Synthetic Intelligence Generator</h1>
    <p>NTRO forensic proof of concept · Neo4j & Graph-Based Threat Generation</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="qa-grid">
    <div class="qa-card">
        <div class="qa-question">📖 Augmented Traffic</div>
        <div class="qa-answer">Normal retail volume sets the baseline while targeted threat clusters create detectable graph patterns.</div>
    </div>
    <div class="qa-card">
        <div class="qa-question">🍌 Peeling Chains</div>
        <div class="qa-answer">Multi-hop laundering sequences splitting 50 BTC into small cashout peels and change relays.</div>
    </div>
    <div class="qa-card">
        <div class="qa-question">🌪️ CoinJoin Mixers</div>
        <div class="qa-answer">Uniform-amount multi-party mixing transactions designed to obscure origin tracing.</div>
    </div>
    <div class="qa-card">
        <div class="qa-question">🕸️ Risk Propagation</div>
        <div class="qa-answer">Decay scoring (R(w) = max R(s) * 0.70^d) mapping downstream recipient threat levels.</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# --- INTERACTIVE GENERATOR ---
st.subheader("⚙️ Generate Target Data")
st.write("Choose target parameters to plant cyber-threat anomalies, peeling chains, and coinjoin mixers.")

col1, col2 = st.columns([1, 2])

with col1:
    target_state = st.selectbox(
        "Target location",
        INDIAN_STATES,
        index=INDIAN_STATES.index("Maharashtra"),
        help="Anomalous transactions will be concentrated in this state or union territory.",
    )
    
    plant_peeling = st.checkbox("Plant Peeling-Chain Laundering Sequence (6 hops)", value=True)
    plant_coinjoin = st.checkbox("Plant CoinJoin Mixing Protocol", value=True)

    st.markdown(f"""
    <div class="target-card">
        <div class="target-label">Selected target jurisdiction</div>
        <div class="target-state">📍 {target_state}</div>
    </div>
    """, unsafe_allow_html=True)
    
    generate_btn = st.button("🚀 Generate 1,000 Ledger Transactions", type="primary")


@st.cache_data
def load_ip_reference():
    if not IP_REFERENCE_FILE.exists():
        return {"all": [], "by_state": {}}

    reference = pd.read_csv(IP_REFERENCE_FILE, encoding="utf-8-sig")
    reference.columns = [column.strip().lstrip("\ufeff").lower() for column in reference.columns]
    ranges = []
    for row in reference.to_dict("records"):
        try:
            start = int(ip_address(str(row["start"]).strip()))
            end = int(ip_address(str(row["end"]).strip()))
            if start <= end:
                ranges.append({
                    "start": start,
                    "end": end,
                    "state": str(row.get("state", "Unknown")).strip(),
                })
        except (ValueError, TypeError):
            continue

    by_state = {}
    for ip_range in ranges:
        by_state.setdefault(ip_range["state"], []).append(ip_range)
    return {"all": ranges, "by_state": by_state}


def sample_reference_ip(ip_ranges):
    if not ip_ranges:
        return fake.ipv4(public=True)
    selected_range = random.choice(ip_ranges)
    value = random.randint(selected_range["start"], selected_range["end"])
    return str(IPv4Address(value))


@st.cache_data
def generate_data(target_state, include_peeling=True, include_coinjoin=True):
    NUM_RECORDS = 1000
    WALLET_POOL = [fake.sha256()[:34] for _ in range(150)]
    ip_reference = load_ip_reference()
    all_ip_ranges = ip_reference["all"]
    target_ip_ranges = ip_reference["by_state"].get(target_state, all_ip_ranges)
    
    threat_wallets = random.sample(WALLET_POOL, 3)
    data = []

    # 1. Plant Peeling Chain Sequence (if requested)
    if include_peeling:
        peel_hops = 6
        chain_wallets = [fake.sha256()[:34] for _ in range(peel_hops + 1)]
        peel_cashouts = [fake.sha256()[:34] for _ in range(peel_hops)]
        current_amount = 50.0

        for hop in range(peel_hops):
            src_w = chain_wallets[hop]
            change_w = chain_wallets[hop + 1]
            peel_w = peel_cashouts[hop]
            peel_amt = 0.5
            change_amt = current_amount - peel_amt
            current_amount = change_amt

            data.append({
                "timestamp": (datetime.now() - timedelta(minutes=random.randint(10, 200))).isoformat(),
                "src_ip": sample_reference_ip(target_ip_ranges),
                "dst_ip": sample_reference_ip(all_ip_ranges),
                "src_port": random.randint(1024, 65535),
                "dst_port": 8333,
                "txid": f"peel_tx_{hop+1}_" + uuid.uuid4().hex[:12],
                "input_addresses": _json.dumps([src_w]),
                "output_addresses": _json.dumps([change_w, peel_w]),
                "input_amounts": _json.dumps([round(current_amount + peel_amt, 4)]),
                "output_amounts": _json.dumps([round(change_amt, 4), round(peel_amt, 4)]),
                "fee": round(random.uniform(0.0001, 0.0005), 6),
                "script_type": "P2PKH",
                "geo_state": target_state,
            })

    # 2. Plant CoinJoin Mixing Transaction (if requested)
    if include_coinjoin:
        mix_inputs = [fake.sha256()[:34] for _ in range(4)]
        mix_outputs = [fake.sha256()[:34] for _ in range(4)]
        denom = 5.0
        data.append({
            "timestamp": datetime.now().isoformat(),
            "src_ip": sample_reference_ip(target_ip_ranges),
            "dst_ip": sample_reference_ip(all_ip_ranges),
            "src_port": random.randint(1024, 65535),
            "dst_port": 8333,
            "txid": "coinjoin_tx_" + uuid.uuid4().hex[:12],
            "input_addresses": _json.dumps(mix_inputs),
            "output_addresses": _json.dumps(mix_outputs),
            "input_amounts": _json.dumps([denom] * 4),
            "output_amounts": _json.dumps([denom - 0.001] * 4),
            "fee": round(random.uniform(0.0001, 0.0003), 6),
            "script_type": "P2SH",
            "geo_state": target_state,
        })

    # 3. Fill remaining records with retail + anomaly traffic
    remaining_records = NUM_RECORDS - len(data)
    for i in range(remaining_records):
        is_anomaly = random.random() < 0.05
        
        if is_anomaly:
            geo_state = target_state
            src_ip = sample_reference_ip(target_ip_ranges)
            inputs = random.choices(threat_wallets, k=random.randint(2, 4))
            outputs = random.choices(threat_wallets + random.sample(WALLET_POOL, 2), k=random.randint(1, 2))
            multiplier = np.random.uniform(10.0, 50.0)
        else:
            geo_state = random.choice(INDIAN_STATES)
            src_ip = sample_reference_ip(ip_reference["by_state"].get(geo_state, all_ip_ranges))
            inputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            outputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            multiplier = np.random.uniform(0.01, 1.5)
            
        data.append({
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 10000))).isoformat(),
            "src_ip": src_ip,
            "dst_ip": sample_reference_ip(all_ip_ranges),
            "src_port": random.randint(1024, 65535),
            "dst_port": 8333,
            "txid": uuid.uuid4().hex,
            "input_addresses": _json.dumps(inputs),
            "output_addresses": _json.dumps(outputs),
            "input_amounts": _json.dumps([round(random.uniform(0.1, 2.0) * multiplier, 4) for _ in inputs]),
            "output_amounts": _json.dumps([round(random.uniform(0.1, 2.0) * multiplier, 4) for _ in outputs]),
            "fee": round(random.uniform(0.00005, 0.0008), 6),
            "script_type": random.choice(["P2PKH", "P2SH", "P2WPKH", "P2WSH"]),
            "geo_state": geo_state,
        })
        
    return pd.DataFrame(data)

with col2:
    if generate_btn:
        with st.spinner(f"Augmenting synthetic ledger... Planting anomalies & peeling chains in {target_state}..."):
            df = generate_data(target_state, include_peeling=plant_peeling, include_coinjoin=plant_coinjoin)
            
            st.success("✅ Forensic Dataset Generated Successfully!")
            st.write("### Raw Data Proof (First 5 Rows)")
            st.dataframe(df.head(5))
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download ledger.csv",
                data=csv,
                file_name='ledger.csv',
                mime='text/csv',
            )
            st.caption("Next Step: Upload this ledger.csv into the ChainWatch Workspace to execute the Neo4j ML Pipeline.")
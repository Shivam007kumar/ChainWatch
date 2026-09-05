import streamlit as st
import pandas as pd
import numpy as np
import random
import uuid
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
    .hero h1 {
        margin: 0;
        font-size: 2.2rem;
    }
    .hero p {
        margin: 0.45rem 0 0;
        color: #d9f0f2;
    }
    .target-card {
        padding: 1rem 1.1rem;
        border-left: 4px solid #e09f3e;
        border-radius: 8px;
        background: #fff8ec;
        margin: 0.5rem 0 1rem;
    }
    .target-label {
        color: #825b19;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .target-state {
        color: #102a43;
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }
    .qa-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
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
    .qa-question {
        color: #102a43;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .qa-answer {
        color: #52606d;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    @media (max-width: 900px) {
        .qa-grid { grid-template-columns: 1fr; }
    }
</style>
""", unsafe_allow_html=True)

# 36 States and UTs of India
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
    <h1>🛡️ ChainWatch</h1>
    <p>Synthetic ledger generator · NTRO proof of concept</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="qa-grid">
    <div class="qa-card">
        <div class="qa-question">📖 Why augmented data?</div>
        <div class="qa-answer">Normal traffic creates a baseline. A small group of high-volume, clustered transactions gives the model a meaningful signal to find.</div>
    </div>
    <div class="qa-card">
        <div class="qa-question">🧠 How are anomalies found?</div>
        <div class="qa-answer">Isolation Forest spots unusual wallet behavior using volume, frequency, and IP diversity. K-Means groups similar behavior patterns.</div>
    </div>
    <div class="qa-card">
        <div class="qa-question">🕸️ Why graph storage?</div>
        <div class="qa-answer">Wallet-to-wallet relationships are easier to trace as connected paths, especially across multi-hop transaction chains.</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# --- INTERACTIVE GENERATOR ---
st.subheader("⚙️ Generate Target Data")
st.write("Choose a location to plant a targeted cyber-threat anomaly. The engine will generate 1,000 augmented transactions around this threat.")

col1, col2 = st.columns([1, 2])

with col1:
    target_state = st.selectbox(
        "Target location",
        INDIAN_STATES,
        index=INDIAN_STATES.index("Maharashtra"),
        help="Anomalous transactions will be concentrated in this state or union territory.",
    )
    st.markdown(f"""
    <div class="target-card">
        <div class="target-label">Selected target</div>
        <div class="target-state">📍 {target_state}</div>
    </div>
    """, unsafe_allow_html=True)
    
    generate_btn = st.button("🚀 Generate 1,000 Transactions", type="primary")

# --- DATA GENERATION LOGIC ---
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
            if start > end:
                continue
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
def generate_data(target_state):
    NUM_RECORDS = 1000
    WALLET_POOL = [fake.sha256()[:34] for _ in range(150)]
    ip_reference = load_ip_reference()
    all_ip_ranges = ip_reference["all"]
    target_ip_ranges = ip_reference["by_state"].get(target_state, all_ip_ranges)
    
    # Planted Threat Actors
    threat_wallets = random.sample(WALLET_POOL, 3)
    
    data = []
    for i in range(NUM_RECORDS):
        # 5% chance of being the targeted anomaly
        is_anomaly = random.random() < 0.05 
        
        if is_anomaly:
            geo_state = target_state
            src_ip = sample_reference_ip(target_ip_ranges)
            inputs = random.choices(threat_wallets, k=random.randint(2, 4))
            outputs = random.choices(threat_wallets + random.sample(WALLET_POOL, 2), k=random.randint(1, 2))
            multiplier = np.random.uniform(10.0, 50.0) # High volume bias
        else:
            # Normal Pareto-distributed retail traffic
            geo_state = random.choice(INDIAN_STATES)
            src_ip = sample_reference_ip(ip_reference["by_state"].get(geo_state, all_ip_ranges))
            inputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            outputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            multiplier = np.random.uniform(0.01, 1.5) # Low volume baseline
            
        data.append({
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 10000))).isoformat(),
            "src_ip": src_ip,
            "dst_ip": sample_reference_ip(all_ip_ranges),
            "src_port": random.randint(1024, 65535),
            "dst_port": 8333,
            "txid": uuid.uuid4().hex,
            "input_addresses": str(inputs),
            "output_addresses": str(outputs),
            "input_amounts": str([round(random.uniform(0.1, 2.0) * multiplier, 4) for _ in inputs]),
            "output_amounts": str([round(random.uniform(0.1, 2.0) * multiplier, 4) for _ in outputs]),
            "geo_state": geo_state,
        })
        
    return pd.DataFrame(data)

with col2:
    if generate_btn:
        with st.spinner(f"Augmenting synthetic data... Planting anomaly in {target_state}..."):
            df = generate_data(target_state)
            
            st.success("✅ Dataset Generated Successfully!")
            st.write("### Raw Data Proof (First 5 Rows)")
            st.dataframe(df.head(5))
            
            # Physical Download Button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download ledger.csv",
                data=csv,
                file_name='ledger.csv',
                mime='text/csv',
            )
            st.caption("Next Step: Upload this ledger.csv into the ChainWatch Workspace to run the ML Pipeline.")
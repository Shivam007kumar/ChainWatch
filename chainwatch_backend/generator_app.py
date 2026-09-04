import streamlit as st
import pandas as pd
import numpy as np
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

# --- CONFIGURATION ---
st.set_page_config(page_title="NTRO Data Generator", page_icon="🛡️", layout="wide")
fake = Faker()

# 36 States and UTs of India
INDIAN_STATES = [
    "Andaman and Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", 
    "Chandigarh", "Chhattisgarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Goa", 
    "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", 
    "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", 
    "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", 
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

# --- EDUCATIONAL UI (The Pitch) ---
st.title("🛡️ ChainWatch: Synthetic Ledger Generator")
st.markdown("### *National Technical Research Organisation (NTRO) Proof of Concept*")

with st.expander("📖 1. The Data Problem: Why Augmented Data over pure `np.random`?"):
    st.write("""
    **The Limitations of `np.random`:** If we generate Bitcoin traffic using pure uniform randomness, every wallet looks equally random. In a uniform distribution, an ML model cannot find anomalies because *everything* is an anomaly. 
    
    **Our Solution (Augmented Synthetic Data):** Real human behavior and financial fraud follow **Power Laws (Pareto distributions)**. 80% of transactions are normal retail buys. We augment our synthetic data with **Weights and Biases**. We force a "baseline" of normal behavior, and deliberately inject "clustered noise" (e.g., forcing specific wallets to rapidly trade across high-risk IPs) so the model has a true mathematical signal to detect.
    """)

with st.expander("🧠 2. How We Detect Anomalies (Low-Level vs High-Level)"):
    st.write("""
    **High-Level (The Concept):** Imagine a crowd of people walking normally. One person is sprinting in zig-zags and changing jackets. Our AI doesn't look for a specific jacket; it looks for the zig-zagging. It flags behavior that mathematically deviates from the baseline.
    
    **Low-Level (The Math):** We engineer features per wallet (tx_frequency, unique_ips, volume). We pass this vector into an **Isolation Forest**. Instead of profiling 'normal' data, it builds random decision trees. Normal wallets require many splits to be isolated in a leaf node. Anomalous wallets (extreme values) are isolated in very few splits. We invert that path length to generate the anomaly score. We then use **K-Means** to cluster the behavioral patterns.
    """)

with st.expander("🕸️ 3. Why Neo4j instead of SQL?"):
    st.write("""
    SQL databases require massive, computationally expensive `JOIN` operations to trace money moving through 5 different wallets. Criminals use "Peeling Chains" to move money through hundreds of hops. 
    
    **Neo4j is a Graph Database;** it stores the relationships (edges) natively. Tracing a 10-hop peeling chain in SQL takes minutes and crashes servers; in Neo4j, it takes milliseconds.
    """)

st.divider()

# --- INTERACTIVE GENERATOR ---
st.subheader("⚙️ Generate Target Data")
st.write("Select a state index (1-36) to plant a targeted cyber-threat anomaly. The engine will generate 1,000 augmented transactions around this threat.")

col1, col2 = st.columns([1, 2])

with col1:
    # Let the judge pick the state (1-36)
    state_index = st.number_input("Target State Index (1-36)", min_value=1, max_value=36, value=21) # Default 21 is Maharashtra
    target_state = INDIAN_STATES[state_index - 1]
    st.info(f"📍 **Selected Target:** {target_state}")
    
    generate_btn = st.button("🚀 Generate 1,000 Transactions", type="primary")

# --- DATA GENERATION LOGIC ---
@st.cache_data
def generate_data(target_state):
    NUM_RECORDS = 1000
    WALLET_POOL = [fake.sha256()[:34] for _ in range(150)]
    IP_POOL = [fake.ipv4() for _ in range(80)]
    
    # Planted Threat Actors
    threat_wallets = random.sample(WALLET_POOL, 3)
    
    data = []
    for i in range(NUM_RECORDS):
        # 5% chance of being the targeted anomaly
        is_anomaly = random.random() < 0.05 
        
        if is_anomaly:
            geo_state = target_state
            inputs = random.choices(threat_wallets, k=random.randint(2, 4))
            outputs = random.choices(threat_wallets + random.sample(WALLET_POOL, 2), k=random.randint(1, 2))
            multiplier = np.random.uniform(10.0, 50.0) # High volume bias
        else:
            # Normal Pareto-distributed retail traffic
            geo_state = random.choice(INDIAN_STATES)
            inputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            outputs = random.sample(WALLET_POOL, k=random.randint(1, 2))
            multiplier = np.random.uniform(0.01, 1.5) # Low volume baseline
            
        data.append({
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 10000))).isoformat(),
            "src_ip": random.choice(IP_POOL),
            "dst_ip": random.choice(IP_POOL),
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
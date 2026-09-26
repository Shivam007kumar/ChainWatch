import streamlit as st
import pandas as pd
import numpy as np
import random
import hashlib
import json as _json
from datetime import datetime, timedelta
from ipaddress import IPv4Address, ip_address
from pathlib import Path


# ============================================================
# CHAINWATCH SYNTHETIC LEDGER GENERATOR — FINAL V2
# ============================================================
# Output CSV is intentionally kept to the frozen ChainWatch schema:
#
# timestamp, src_ip, dst_ip, src_port, dst_port, txid,
# input_addresses, output_addresses, input_amounts, output_amounts,
# fee, script_type, geo_state
#
# Ground-truth anomaly labels are NOT added to the CSV.
# A separate manifest can be downloaded for demonstration/testing.
# ============================================================

st.set_page_config(
    page_title="ChainWatch Synthetic Intelligence Generator",
    page_icon="🛡️",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
IP_REFERENCE_FILE = BASE_DIR.parent / "IP_Address.csv"

SCHEMA = [
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "txid",
    "input_addresses",
    "output_addresses",
    "input_amounts",
    "output_amounts",
    "fee",
    "script_type",
    "geo_state",
]

INDIAN_STATES = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

SCRIPT_TYPES = ["P2PKH", "P2SH", "P2WPKH", "P2WSH"]

DATASET_SIZES = {
    "Demo — 1,000": 1_000,
    "Standard — 10,000": 10_000,
    "Large — 50,000": 50_000,
    "Stress — 100,000": 100_000,
}


# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------

st.markdown(
    """
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}
.hero {
    padding: 1.5rem 1.7rem;
    border-radius: 14px;
    background: linear-gradient(120deg, #102a43 0%, #1f5f78 100%);
    color: white;
    margin-bottom: 1.4rem;
}
.hero h1 { margin: 0; font-size: 2.2rem; }
.hero p { margin: 0.45rem 0 0; color: #d9f0f2; }
.small-note {
    color: #52606d;
    font-size: 0.9rem;
}
.metric-card {
    border: 1px solid #d9e2ec;
    border-radius: 10px;
    padding: 0.9rem 1rem;
    background: #f8fafc;
}
.metric-title {
    font-size: 0.76rem;
    font-weight: 700;
    color: #52606d;
    text-transform: uppercase;
}
.metric-value {
    font-size: 1.35rem;
    font-weight: 800;
    color: #102a43;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
    <h1>🛡️ ChainWatch Synthetic Intelligence Generator</h1>
    <p>Deterministic synthetic Bitcoin traffic for graph forensics, anomaly detection,
    risk propagation and IP-layer correlation.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.info(
    "The CSV deliberately contains only the production 13-column schema. "
    "Detection ground truth is exported separately so the uploaded ledger remains "
    "indistinguishable from an unlabeled forensic dataset."
)


# ------------------------------------------------------------
# IP reference
# ------------------------------------------------------------

@st.cache_data
def load_ip_reference():
    if not IP_REFERENCE_FILE.exists():
        return {"all": [], "by_state": {}}

    try:
        reference = pd.read_csv(IP_REFERENCE_FILE, encoding="utf-8-sig")
    except Exception:
        return {"all": [], "by_state": {}}

    reference.columns = [
        str(column).strip().lstrip("\ufeff").lower()
        for column in reference.columns
    ]

    ranges = []

    for row in reference.to_dict("records"):
        try:
            start = int(ip_address(str(row["start"]).strip()))
            end = int(ip_address(str(row["end"]).strip()))
            if start <= end:
                ranges.append(
                    {
                        "start": start,
                        "end": end,
                        "state": str(row.get("state", "Unknown")).strip(),
                    }
                )
        except (ValueError, TypeError, KeyError):
            continue

    by_state = {}
    for ip_range in ranges:
        by_state.setdefault(ip_range["state"], []).append(ip_range)

    return {"all": ranges, "by_state": by_state}


def sample_reference_ip(ip_ranges, rng):
    if not ip_ranges:
        # Deterministic public-looking fallback.
        while True:
            value = rng.randint(0x01000000, 0xDFFFFFFF)
            ip = IPv4Address(value)
            if not (
                ip.is_private
                or ip.is_loopback
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_link_local
            ):
                return str(ip)

    selected = rng.choice(ip_ranges)
    value = rng.randint(selected["start"], selected["end"])
    return str(IPv4Address(value))


# ------------------------------------------------------------
# Deterministic identifiers
# ------------------------------------------------------------

def digest_hex(seed, namespace, index, length=64):
    raw = f"chainwatch:{seed}:{namespace}:{index}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def wallet_id(seed, index):
    return digest_hex(seed, "wallet", index, 34)


def tx_id(seed, namespace, index):
    # 64-character hex string, matching the shape of a Bitcoin txid.
    return digest_hex(seed, namespace, index, 64)


# ------------------------------------------------------------
# Scenario planning
# ------------------------------------------------------------

def scenario_plan(n):
    """
    Exact deterministic scenario counts.

    The plan intentionally keeps anomaly families visible at 10k and
    still useful at 100k without turning the whole dataset into anomalies.
    """

    return {
        "peeling_chain_transactions": max(12, round(n * 0.003)),
        "coinjoin_transactions": max(3, round(n * 0.001)),
        "high_fanout_transactions": max(10, round(n * 0.010)),
        "high_fanin_transactions": max(5, round(n * 0.005)),
        "burst_transactions": max(30, round(n * 0.012)),
        "high_volume_transactions": max(20, round(n * 0.010)),
        "irregular_amount_transactions": max(10, round(n * 0.010)),
    }


def rows_for_plan(plan):
    return sum(plan.values())


# ------------------------------------------------------------
# Row helpers
# ------------------------------------------------------------

def make_row(
    *,
    timestamp,
    src_ip,
    dst_ip,
    src_port,
    dst_port,
    txid,
    inputs,
    outputs,
    input_amounts,
    output_amounts,
    fee,
    script_type,
    geo_state,
):
    return {
        "timestamp": timestamp.isoformat(),
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "src_port": int(src_port),
        "dst_port": int(dst_port),
        "txid": txid,
        "input_addresses": _json.dumps(inputs, separators=(",", ":")),
        "output_addresses": _json.dumps(outputs, separators=(",", ":")),
        "input_amounts": _json.dumps(
            [round(float(x), 8) for x in input_amounts],
            separators=(",", ":"),
        ),
        "output_amounts": _json.dumps(
            [round(float(x), 8) for x in output_amounts],
            separators=(",", ":"),
        ),
        "fee": round(float(fee), 8),
        "script_type": script_type,
        "geo_state": geo_state,
    }


def split_amount(total, count, rng):
    """Positive deterministic split that sums to approximately total."""
    if count == 1:
        return [round(total, 8)]

    weights = np.array([rng.random() + 0.15 for _ in range(count)])
    weights = weights / weights.sum()
    values = [round(float(total * w), 8) for w in weights]

    # Correct floating rounding drift on final output.
    drift = round(total - sum(values), 8)
    values[-1] = round(values[-1] + drift, 8)

    return values


# ------------------------------------------------------------
# Main generator
# ------------------------------------------------------------

@st.cache_data(show_spinner=False)
def generate_dataset(
    n_records,
    target_state,
    seed,
    enable_peeling,
    enable_coinjoin,
    enable_fanout,
    enable_fanin,
    enable_burst,
    enable_high_volume,
    enable_irregular,
):
    rng = random.Random(int(seed))
    np.random.seed(int(seed) % (2**32 - 1))

    ip_reference = load_ip_reference()
    all_ip_ranges = ip_reference["all"]
    target_ip_ranges = ip_reference["by_state"].get(target_state, all_ip_ranges)

    # Scale wallet pool with dataset size so the graph does not become
    # artificially dense at 100k rows.
    wallet_count = max(300, min(30_000, int(n_records * 0.22)))

    wallets = [
        wallet_id(seed, i)
        for i in range(wallet_count)
    ]

    rows = []
    truth = []

    base_time = datetime(2026, 9, 25, 18, 0, 0)

    def add_truth(txid, category, wallet_ids=None, details=None):
        truth.append(
            {
                "txid": txid,
                "category": category,
                "wallets": wallet_ids or [],
                "details": details or {},
            }
        )

    def add_normal_transaction(index, timestamp=None):
        timestamp = timestamp or (
            base_time - timedelta(seconds=rng.randint(0, 14 * 24 * 3600))
        )

        input_count = rng.choice([1, 1, 1, 2])
        output_count = rng.choice([1, 1, 2])

        inputs = rng.sample(wallets, input_count)

        available_outputs = [w for w in wallets if w not in inputs]
        outputs = rng.sample(available_outputs, output_count)

        input_total = round(rng.uniform(0.15, 3.0), 8)
        fee = round(rng.uniform(0.00005, 0.0008), 8)
        output_total = round(max(0.001, input_total - fee), 8)

        output_amounts = split_amount(output_total, output_count, rng)
        input_amounts = [input_total]

        state = rng.choice(INDIAN_STATES)
        state_ranges = ip_reference["by_state"].get(state, all_ip_ranges)

        txid = tx_id(seed, "normal", index)

        rows.append(
            make_row(
                timestamp=timestamp,
                src_ip=sample_reference_ip(state_ranges, rng),
                dst_ip=sample_reference_ip(all_ip_ranges, rng),
                src_port=rng.randint(1024, 65535),
                dst_port=8333,
                txid=txid,
                inputs=inputs,
                outputs=outputs,
                input_amounts=input_amounts,
                output_amounts=output_amounts,
                fee=fee,
                script_type=rng.choice(SCRIPT_TYPES),
                geo_state=state,
            )
        )

    # --------------------------------------------------------
    # 1. PEELING CHAINS — exact 80/20 split, 6 hops
    # --------------------------------------------------------

    plan = scenario_plan(n_records)

    if enable_peeling:
        peel_rows = plan["peeling_chain_transactions"]
        chain_count = max(1, peel_rows // 6)

        for chain_index in range(chain_count):
            chain = [
                wallet_id(seed, wallet_count + chain_index * 20 + j)
                for j in range(8)
            ]
            current_amount = 50.0

            for hop in range(6):
                if len(rows) >= n_records:
                    break

                src = chain[hop]
                change = chain[hop + 1]
                cashout = wallet_id(
                    seed,
                    wallet_count + chain_index * 20 + 10 + hop,
                )

                # Preserve the 80/20 split of the spendable amount, with the
                # transaction fee accounted for in the input total.
                fee = round(rng.uniform(0.0001, 0.0004), 8)
                input_amount = round(current_amount + fee, 8)
                peel_amount = round(current_amount * 0.20, 8)
                change_amount = round(current_amount * 0.80, 8)

                txid = tx_id(seed, "peeling", chain_index * 6 + hop)
                timestamp = base_time - timedelta(
                    minutes=(chain_index * 12 + hop)
                )

                rows.append(
                    make_row(
                        timestamp=timestamp,
                        src_ip=sample_reference_ip(target_ip_ranges, rng),
                        dst_ip=sample_reference_ip(all_ip_ranges, rng),
                        src_port=rng.randint(20000, 60000),
                        dst_port=8333,
                        txid=txid,
                        inputs=[src],
                        outputs=[change, cashout],
                        input_amounts=[input_amount],
                        output_amounts=[change_amount, peel_amount],
                        fee=fee,
                        script_type="P2PKH",
                        geo_state=target_state,
                    )
                )

                add_truth(
                    txid,
                    "PEELING_CHAIN",
                    [src, change, cashout],
                    {
                        "chain_index": chain_index,
                        "hop": hop + 1,
                        "split": "80/20",
                    },
                )

                current_amount = change_amount

    # --------------------------------------------------------
    # 2. COINJOIN — 4+ inputs, 4 equal outputs
    # --------------------------------------------------------

    if enable_coinjoin:
        for i in range(plan["coinjoin_transactions"]):
            inputs = rng.sample(wallets, 4)
            outputs = rng.sample(
                [w for w in wallets if w not in inputs],
                4,
            )

            denomination = round(rng.choice([2.0, 5.0, 8.0]), 6)
            fee = round(rng.uniform(0.0004, 0.002), 8)
            output_amount = round(denomination - fee / 4, 8)

            txid = tx_id(seed, "coinjoin", i)

            rows.append(
                make_row(
                    timestamp=base_time - timedelta(minutes=100 + i),
                    src_ip=sample_reference_ip(target_ip_ranges, rng),
                    dst_ip=sample_reference_ip(all_ip_ranges, rng),
                    src_port=rng.randint(20000, 60000),
                    dst_port=8333,
                    txid=txid,
                    inputs=inputs,
                    outputs=outputs,
                    input_amounts=[denomination] * 4,
                    output_amounts=[output_amount] * 4,
                    fee=fee,
                    script_type="P2SH",
                    geo_state=target_state,
                )
            )

            add_truth(
                txid,
                "COINJOIN",
                inputs + outputs,
                {
                    "inputs": 4,
                    "outputs": 4,
                    "uniform_output_amount": True,
                },
            )

    # --------------------------------------------------------
    # 3. HIGH FAN-OUT
    # --------------------------------------------------------

    if enable_fanout:
        for i in range(plan["high_fanout_transactions"]):
            count = rng.randint(8, 14)
            src = rng.choice(wallets)
            outputs = rng.sample(
                [w for w in wallets if w != src],
                count,
            )

            total = round(rng.uniform(8.0, 60.0), 6)
            fee = round(rng.uniform(0.0005, 0.003), 8)
            amounts = split_amount(total - fee, count, rng)
            txid = tx_id(seed, "fanout", i)

            rows.append(
                make_row(
                    timestamp=base_time - timedelta(hours=2, minutes=i),
                    src_ip=sample_reference_ip(target_ip_ranges, rng),
                    dst_ip=sample_reference_ip(all_ip_ranges, rng),
                    src_port=rng.randint(1024, 65535),
                    dst_port=8333,
                    txid=txid,
                    inputs=[src],
                    outputs=outputs,
                    input_amounts=[total],
                    output_amounts=amounts,
                    fee=fee,
                    script_type="P2WPKH",
                    geo_state=target_state,
                )
            )

            add_truth(
                txid,
                "HIGH_FAN_OUT",
                [src] + outputs,
                {"output_count": count},
            )

    # --------------------------------------------------------
    # 4. HIGH FAN-IN
    # --------------------------------------------------------

    if enable_fanin:
        for i in range(plan["high_fanin_transactions"]):
            count = rng.randint(8, 14)
            inputs = rng.sample(wallets, count)
            output = rng.choice(
                [w for w in wallets if w not in inputs]
            )

            amounts = [
                round(rng.uniform(0.2, 2.0), 6)
                for _ in range(count)
            ]
            total = round(sum(amounts), 8)
            fee = round(rng.uniform(0.0005, 0.003), 8)
            output_amount = round(total - fee, 8)

            txid = tx_id(seed, "fanin", i)

            rows.append(
                make_row(
                    timestamp=base_time - timedelta(hours=4, minutes=i),
                    src_ip=sample_reference_ip(target_ip_ranges, rng),
                    dst_ip=sample_reference_ip(all_ip_ranges, rng),
                    src_port=rng.randint(1024, 65535),
                    dst_port=8333,
                    txid=txid,
                    inputs=inputs,
                    outputs=[output],
                    input_amounts=amounts,
                    output_amounts=[output_amount],
                    fee=fee,
                    script_type="P2WSH",
                    geo_state=target_state,
                )
            )

            add_truth(
                txid,
                "HIGH_FAN_IN",
                inputs + [output],
                {"input_count": count},
            )

    # --------------------------------------------------------
    # 5. BURST VELOCITY — same wallet, tightly clustered timestamps
    # --------------------------------------------------------

    if enable_burst:
        burst_groups = max(1, plan["burst_transactions"] // 6)

        for group in range(burst_groups):
            actor = rng.choice(wallets)

            for j in range(6):
                tx_index = group * 6 + j
                txid = tx_id(seed, "burst", tx_index)

                output = rng.choice(
                    [w for w in wallets if w != actor]
                )
                amount = round(rng.uniform(0.5, 2.5), 6)
                fee = round(rng.uniform(0.0001, 0.0005), 8)

                rows.append(
                    make_row(
                        timestamp=base_time
                        - timedelta(hours=8)
                        + timedelta(seconds=group * 300 + j * 7),
                        src_ip=sample_reference_ip(target_ip_ranges, rng),
                        dst_ip=sample_reference_ip(all_ip_ranges, rng),
                        src_port=rng.randint(20000, 60000),
                        dst_port=8333,
                        txid=txid,
                        inputs=[actor],
                        outputs=[output],
                        input_amounts=[round(amount + fee, 8)],
                        output_amounts=[amount],
                        fee=fee,
                        script_type="P2WPKH",
                        geo_state=target_state,
                    )
                )

                add_truth(
                    txid,
                    "BURST_VELOCITY",
                    [actor, output],
                    {
                        "burst_group": group,
                        "seconds_from_group_start": j * 7,
                    },
                )

    # --------------------------------------------------------
    # 6. HIGH VOLUME
    # --------------------------------------------------------

    if enable_high_volume:
        for i in range(plan["high_volume_transactions"]):
            src, output = rng.sample(wallets, 2)
            amount = round(rng.uniform(15.0, 75.0), 6)
            fee = round(rng.uniform(0.001, 0.005), 8)
            txid = tx_id(seed, "high_volume", i)

            rows.append(
                make_row(
                    timestamp=base_time - timedelta(hours=12, minutes=i),
                    src_ip=sample_reference_ip(target_ip_ranges, rng),
                    dst_ip=sample_reference_ip(all_ip_ranges, rng),
                    src_port=rng.randint(1024, 65535),
                    dst_port=8333,
                    txid=txid,
                    inputs=[src],
                    outputs=[output],
                    input_amounts=[amount],
                    output_amounts=[round(amount - fee, 8)],
                    fee=fee,
                    script_type=rng.choice(["P2PKH", "P2WPKH"]),
                    geo_state=target_state,
                )
            )

            add_truth(
                txid,
                "HIGH_VOLUME",
                [src, output],
                {"input_btc": amount},
            )

    # --------------------------------------------------------
    # 7. IRREGULAR AMOUNTS
    # --------------------------------------------------------

    if enable_irregular:
        for i in range(plan["irregular_amount_transactions"]):
            src = rng.choice(wallets)
            outputs = rng.sample(
                [w for w in wallets if w != src],
                4,
            )

            output_amounts = [
                0.0011,
                0.0377,
                0.8123,
                round(rng.uniform(8.0, 18.0), 6),
            ]

            fee = round(rng.uniform(0.0002, 0.001), 8)
            total = round(sum(output_amounts) + fee, 8)

            txid = tx_id(seed, "irregular", i)

            rows.append(
                make_row(
                    timestamp=base_time - timedelta(hours=16, minutes=i),
                    src_ip=sample_reference_ip(target_ip_ranges, rng),
                    dst_ip=sample_reference_ip(all_ip_ranges, rng),
                    src_port=rng.randint(1024, 65535),
                    dst_port=8333,
                    txid=txid,
                    inputs=[src],
                    outputs=outputs,
                    input_amounts=[total],
                    output_amounts=output_amounts,
                    fee=fee,
                    script_type="P2SH",
                    geo_state=target_state,
                )
            )

            add_truth(
                txid,
                "IRREGULAR_AMOUNTS",
                [src] + outputs,
                {"output_variance": "high"},
            )

    # --------------------------------------------------------
    # Fill remaining capacity with normal background traffic
    # --------------------------------------------------------

    while len(rows) < n_records:
        add_normal_transaction(len(rows))

    # Exact requested size.
    rows = rows[:n_records]

    # Shuffle so the planted scenarios are not grouped together.
    rng.shuffle(rows)

    df = pd.DataFrame(rows, columns=SCHEMA)

    # Ground truth may contain scenario rows that were cut if a very small
    # dataset is requested. Keep only txids actually present in the CSV.
    actual_txids = set(df["txid"])
    truth = [item for item in truth if item["txid"] in actual_txids]

    return df, truth


# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------

def validate_dataset(df):
    errors = []

    if list(df.columns) != SCHEMA:
        errors.append(
            f"Schema mismatch. Expected {len(SCHEMA)} exact columns."
        )

    if len(df) == 0:
        errors.append("Dataset is empty.")

    if df["txid"].duplicated().any():
        errors.append("Duplicate txid detected.")

    for column in ["timestamp", "src_ip", "dst_ip", "txid", "geo_state"]:
        if df[column].isna().any():
            errors.append(f"Missing values in {column}.")

    for column in ["src_port", "dst_port", "fee"]:
        numeric = pd.to_numeric(df[column], errors="coerce")
        if numeric.isna().any():
            errors.append(f"Non-numeric values in {column}.")

    for column in ["input_addresses", "output_addresses", "input_amounts", "output_amounts"]:
        if df[column].isna().any():
            errors.append(f"Missing serialized list in {column}.")

    return errors


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

st.subheader("Generate forensic test data")

left, right = st.columns([1, 2])

with left:
    size_label = st.selectbox(
        "Dataset size",
        list(DATASET_SIZES.keys()),
        index=1,
    )
    n_records = DATASET_SIZES[size_label]

    target_state = st.selectbox(
        "Target threat jurisdiction",
        INDIAN_STATES,
        index=INDIAN_STATES.index("Maharashtra"),
    )

    seed = st.number_input(
        "Deterministic seed",
        min_value=1,
        max_value=999_999_999,
        value=20260926,
        step=1,
    )

    st.markdown("### Planned anomaly families")

    enable_peeling = st.checkbox(
        "Peeling chains — 80/20 split, 6 hops",
        value=True,
    )
    enable_coinjoin = st.checkbox(
        "CoinJoin — 4 inputs / 4 uniform outputs",
        value=True,
    )
    enable_fanout = st.checkbox(
        "High fan-out — 8–14 outputs",
        value=True,
    )
    enable_fanin = st.checkbox(
        "High fan-in — 8–14 inputs",
        value=True,
    )
    enable_burst = st.checkbox(
        "Burst velocity — 6 transactions / 35 seconds",
        value=True,
    )
    enable_high_volume = st.checkbox(
        "High-volume transfers — 15–75 BTC",
        value=True,
    )
    enable_irregular = st.checkbox(
        "Irregular output amounts",
        value=True,
    )

    generate_btn = st.button(
        f"Generate {n_records:,} Transactions",
        type="primary",
        use_container_width=True,
    )

with right:
    plan = scenario_plan(n_records)

    st.markdown("### Exact scenario budget")

    metrics = [
        ("PEEL", plan["peeling_chain_transactions"], "6-hop 80/20 chains"),
        ("COINJOIN", plan["coinjoin_transactions"], "4×4 uniform mix"),
        ("FAN-OUT", plan["high_fanout_transactions"], "8–14 outputs"),
        ("FAN-IN", plan["high_fanin_transactions"], "8–14 inputs"),
        ("BURST", plan["burst_transactions"], "tight timestamp bursts"),
        ("HIGH VOL", plan["high_volume_transactions"], "15–75 BTC"),
        ("IRREGULAR", plan["irregular_amount_transactions"], "high output variance"),
    ]

    cols = st.columns(4)

    for i, (name, count, description) in enumerate(metrics):
        with cols[i % 4]:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">{name}</div>
                    <div class="metric-value">{count:,}</div>
                    <div class="small-note">{description}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    planned = rows_for_plan(plan)
    st.write(
        f"Approximately **{planned:,} rows** are reserved for planted "
        f"behavioral scenarios; the remainder is normal background traffic."
    )

    st.caption(
        "The actual number of detected alerts will not necessarily equal these "
        "counts. These are generator ground-truth cases, while ChainWatch's "
        "detectors independently decide what is suspicious."
    )


# ------------------------------------------------------------
# Generation result
# ------------------------------------------------------------

if generate_btn:
    with st.spinner(
        f"Generating {n_records:,} transactions with structured forensic patterns..."
    ):
        df, truth = generate_dataset(
            n_records=n_records,
            target_state=target_state,
            seed=int(seed),
            enable_peeling=enable_peeling,
            enable_coinjoin=enable_coinjoin,
            enable_fanout=enable_fanout,
            enable_fanin=enable_fanin,
            enable_burst=enable_burst,
            enable_high_volume=enable_high_volume,
            enable_irregular=enable_irregular,
        )

    errors = validate_dataset(df)

    if errors:
        st.error("Dataset validation failed.")
        for error in errors:
            st.write(f"- {error}")
    else:
        st.success(
            f"Validated {len(df):,} transactions against the exact ChainWatch schema."
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{len(df):,}")
        wallet_ids = {
            address
            for column in ("input_addresses", "output_addresses")
            for serialized in df[column]
            for address in _json.loads(serialized)
        }
        c2.metric("Wallet IDs", f"{len(wallet_ids):,}")
        c3.metric("Target State", target_state)
        c4.metric("Ground Truth Cases", f"{len(truth):,}")

        st.subheader("Generated ledger — first 10 rows")
        st.dataframe(df.head(10), use_container_width=True)

        st.subheader("Ground-truth scenario distribution")
        truth_df = pd.DataFrame(truth)

        if not truth_df.empty:
            distribution = (
                truth_df["category"]
                .value_counts()
                .rename_axis("category")
                .reset_index(name="transactions")
            )
            st.dataframe(distribution, use_container_width=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")

        manifest = {
            "generator": "ChainWatch Synthetic Intelligence Generator V2",
            "seed": int(seed),
            "records": int(len(df)),
            "target_state": target_state,
            "schema": SCHEMA,
            "ground_truth": truth,
            "note": (
                "Ground truth is intentionally excluded from ledger.csv. "
                "Use it only for validating ChainWatch detector coverage."
            ),
        }

        manifest_bytes = _json.dumps(
            manifest,
            indent=2,
        ).encode("utf-8")

        st.download_button(
            "📥 Download ledger.csv",
            data=csv_bytes,
            file_name=f"chainwatch_{len(df)}.csv",
            mime="text/csv",
            type="primary",
        )

        st.download_button(
            "🧪 Download ground_truth.json",
            data=manifest_bytes,
            file_name=f"chainwatch_{len(df)}_ground_truth.json",
            mime="application/json",
        )

        st.caption(
            "Upload only the CSV into ChainWatch. Keep ground_truth.json outside "
            "the ingestion pipeline for detector validation."
        )
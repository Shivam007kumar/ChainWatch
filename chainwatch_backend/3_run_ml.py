import csv
import ast
import json
from collections import defaultdict
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

INPUT_CSV = "synthetic_bitcoin_traffic.csv"
ANOMALY_OUTPUT = "anomaly_results.json"
GRAPH_OUTPUT = "graph_data.json"
GROUND_TRUTH = "ground_truth.json"

HIGH_RISK_STATES = {"Maharashtra", "Delhi", "West Bengal"}

# ── GeoIP Resolution (Looking for Subdivisions/States) ──
# ── GeoIP Resolution & Coordinates ──
GEOIP_DB_PATH = "GeoLite2-City.mmdb" 
geoip_reader = None
try:
    import geoip2.database
    geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
    print(f"🌍 GeoIP: loaded {GEOIP_DB_PATH}, will resolve real src_ip -> State/Coords.")
except Exception:
    print(f"⚠️ GeoIP: '{GEOIP_DB_PATH}' not found. Falling back to CSV 'geo_state'.")

# Fallback coordinates for the center of Indian States
STATE_COORDS = {
    'Maharashtra': (19.7515, 75.7139), 'Delhi': (28.7041, 77.1025),
    'Karnataka': (15.3173, 75.7139), 'Gujarat': (22.2587, 71.1924),
    'Tamil Nadu': (11.1271, 78.6569), 'West Bengal': (22.9868, 87.8550),
    'Uttar Pradesh': (26.8467, 80.9462), 'Telangana': (18.1124, 79.0193),
    'Kerala': (10.8505, 76.2711), 'Rajasthan': (27.0238, 74.2179)
}

geoip_resolved_count = 0
geoip_fallback_count = 0

def resolve_location(src_ip: str, csv_fallback_state: str):
    global geoip_resolved_count, geoip_fallback_count
    if geoip_reader is not None:
        try:
            resp = geoip_reader.city(src_ip)
            if resp.subdivisions.most_specific.name and resp.location.latitude:
                geoip_resolved_count += 1
                return resp.subdivisions.most_specific.name, resp.location.latitude, resp.location.longitude
        except Exception:
            pass  
    
    geoip_fallback_count += 1
    # Fallback to the synthetic state and its rough coordinates
    lat, lng = STATE_COORDS.get(csv_fallback_state, (20.5937, 78.9629)) # default to center of India
    return csv_fallback_state, lat, lng


def resolve_state(src_ip: str, csv_fallback_state: str) -> str:
    global geoip_resolved_count, geoip_fallback_count
    if geoip_reader is not None:
        try:
            resp = geoip_reader.city(src_ip)
            if resp.subdivisions.most_specific.name:
                geoip_resolved_count += 1
                return resp.subdivisions.most_specific.name
        except Exception:
            pass  
    geoip_fallback_count += 1
    return csv_fallback_state
# ── Load CSV ──
rows = []
with open(INPUT_CSV, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        row["input_addresses"] = ast.literal_eval(row["input_addresses"])
        row["output_addresses"] = ast.literal_eval(row["output_addresses"])
        row["input_amounts"] = ast.literal_eval(row["input_amounts"])
        row["output_amounts"] = ast.literal_eval(row["output_amounts"])
        
        # Get State, Lat, Lng
        state, lat, lng = resolve_location(row["src_ip"], row["geo_state"])
        row["resolved_state"] = state
        row["lat"] = lat
        row["lng"] = lng
        rows.append(row)
# ── Feature Engineering ──
from collections import Counter # Add this import at the top

wallet_stats = defaultdict(lambda: {
    "tx_count": 0, "total_received": 0.0, "total_sent": 0.0,
    "unique_ips": set(), "states": set(), "txids": [], "high_risk_state_hits": 0,
    "location_history": [] # Track all locations to find the primary one
})

for row in rows:
    state, lat, lng = row["resolved_state"], row["lat"], row["lng"]
    src_ip, txid = row["src_ip"], row["txid"]

    for wallet, amt in zip(row["input_addresses"], row["input_amounts"]):
        ws = wallet_stats[wallet]
        ws["tx_count"] += 1
        ws["total_sent"] += float(amt)
        ws["unique_ips"].add(src_ip)
        ws["states"].add(state)
        ws["txids"].append(txid)
        ws["location_history"].append((state, lat, lng))
        if state in HIGH_RISK_STATES: ws["high_risk_state_hits"] += 1

for wallet, amt in zip(row["output_addresses"], row["output_amounts"]):
        ws = wallet_stats[wallet]
        ws["tx_count"] += 1
        ws["total_received"] += float(amt)
        ws["unique_ips"].add(src_ip)
        ws["states"].add(state)
        ws["txids"].append(txid)
        ws["location_history"].append((state, lat, lng))
        if state in HIGH_RISK_STATES: ws["high_risk_state_hits"] += 1

wallets = list(wallet_stats.keys())
feature_rows = []
for w in wallets:
    s = wallet_stats[w]
    feature_rows.append([
        s["tx_count"], s["total_received"], s["total_sent"],
        len(s["unique_ips"]), len(s["states"]), s["high_risk_state_hits"],
        s["total_received"] + s["total_sent"],
    ])

X = np.array(feature_rows, dtype=float)
X_scaled = StandardScaler().fit_transform(X)

# ── Isolation Forest ──
print("🤖 Running Isolation Forest Anomaly Detection...")
iso = IsolationForest(n_estimators=300, contamination=0.10, random_state=42)
iso_labels = iso.fit_predict(X_scaled)
iso_scores = iso.decision_function(X_scaled)

# ── K-Means ──
print("🔗 Running K-Means clustering...")
n_clusters = min(6, len(wallets))
cluster_labels = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit_predict(X_scaled)
CLUSTER_NAMES = ["Micro-Transactor Ring", "High-Volume Laundering Node", "Multi-Hop Relay Cluster", "Dormant-then-Active Wallet", "Inter-State Flow Cell", "Low-Risk Retail Activity"]

# ── Explainability ──
def build_reason(features):
    reasons = []
    if features[3] > 5: reasons.append(f"active across {int(features[3])} distinct IPs")
    if features[5] > 10: reasons.append(f"heavy routing through high-risk states (MH/DL/WB)")
    if features[4] > 3: reasons.append(f"spread across {int(features[4])} Indian states")
    if features[0] > 50: reasons.append(f"unusually high transaction frequency ({int(features[0])} TXs)")
    if features[6] > 50: reasons.append(f"massive volume of {features[6]:.2f} BTC")
    if not reasons: reasons.append("statistical outlier in transaction graph topology")
    return "Flagged: " + "; ".join(reasons[:3]) + "."

# ── Build Results ──
print("📊 Building anomaly results...")
flagged_idx = [i for i in range(len(wallets)) if iso_labels[i] == -1]
flagged_raw_scores = [iso_scores[i] for i in flagged_idx]

lo, hi = (min(flagged_raw_scores), max(flagged_raw_scores)) if flagged_raw_scores else (0, 0)
score_range = (hi - lo) if hi != lo else 1e-9

def to_confidence(raw_score):
    return round(60 + 39 * (hi - raw_score) / score_range, 1)

anomaly_results = []
for i in flagged_idx:
    wallet = wallets[i]
    features = feature_rows[i]
    s = wallet_stats[wallet]
    
    # Calculate Primary Operating Region (Most frequent state/coords)
    most_common_loc = Counter(s["location_history"]).most_common(1)[0][0]
    primary_state, primary_lat, primary_lng = most_common_loc

    anomaly_results.append({
        "wallet_address": wallet, "confidence_score": to_confidence(iso_scores[i]),
        "cluster_id": int(cluster_labels[i]), "cluster_name": CLUSTER_NAMES[int(cluster_labels[i])],
        "reason": build_reason(features), "tx_count": int(features[0]),
        "total_volume_btc": round(float(features[6]), 4), "unique_ip_count": int(features[3]),
        "high_risk_hits": int(features[5]), "sample_txid": s["txids"][0] if s["txids"] else "N/A",
        
        # New True Backend Data for the Map!
        "primary_state": primary_state,
        "lat": primary_lat,
        "lng": primary_lng
    })
anomaly_results.sort(key=lambda x: x["confidence_score"], reverse=True)
with open(ANOMALY_OUTPUT, "w") as f: json.dump(anomaly_results, f, indent=2)

# ── Build Graph Data (Limit to 150 nodes to prevent browser crash) ──
flagged_wallets = {r["wallet_address"] for r in anomaly_results}
wallet_clusters = {wallets[i]: int(cluster_labels[i]) for i in range(len(wallets))}
nodes, links, seen_nodes, seen_links = [], [], set(), set()

def add_node(node_id, node_type, label, flagged=False):
    if node_id not in seen_nodes:
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": node_type, "label": label, "flagged": flagged})

def add_link(source, target, rel_type):
    key = f"{source}→{target}"
    if key not in seen_links:
        seen_links.add(key)
        links.append({"source": source, "target": target, "type": rel_type})

# Only send the first 150 transactions to the frontend graph to keep it smooth
for row in rows[:150]:
    txid, src_ip, dst_ip, state = row["txid"], row["src_ip"], row["dst_ip"], row["resolved_state"]
    add_node(txid, "transaction", txid[:8] + "…")
    add_node(src_ip, "ip", src_ip, flagged=(state in HIGH_RISK_STATES))
    add_node(dst_ip, "ip", dst_ip)
    add_link(src_ip, txid, "BROADCASTED")
    add_link(txid, dst_ip, "SENT_TO_NODE")
    for wallet in row["input_addresses"]:
        add_node(wallet, "wallet", wallet[:8] + "…", flagged=(wallet in flagged_wallets))
        add_link(wallet, txid, "INPUT_TO_TX")
    for wallet in row["output_addresses"]:
        add_node(wallet, "wallet", wallet[:8] + "…", flagged=(wallet in flagged_wallets))
        add_link(txid, wallet, "OUTPUT_TO_WALLET")

with open(GRAPH_OUTPUT, "w") as f: json.dump({"nodes": nodes, "links": links}, f, indent=2)

# ── Stats ──
stats = {
    "total_transactions": len(rows), "total_wallets": len(wallets),
    "anomalies_detected": len(anomaly_results),
    "high_risk_wallets": len([r for r in anomaly_results if r["confidence_score"] >= 85]),
    "clusters_identified": n_clusters,
}
with open("stats.json", "w") as f: json.dump(stats, f, indent=2)
print(f"✅ ML pipeline complete. Found {len(anomaly_results)} anomalies out of {len(wallets)} wallets.")
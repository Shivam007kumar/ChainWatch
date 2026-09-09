import json
import ast
import io
from html import escape
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from collections import defaultdict, Counter
from typing import List, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import maxminddb
import ipaddress
from weasyprint import HTML

# --- APP SETUP ---
app = FastAPI(title="ChainWatch Core Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
CITY_DB = BASE_DIR / "database" / "GeoIP-City.mmdb"
ASN_DB = BASE_DIR / "database" / "GeoIP-ASN.mmdb"
LOCATION_CSV = BASE_DIR.parent / "IP_Address.csv"
ASN_CSV = BASE_DIR.parent / "dbip-asn-lite-2026-09.csv"
GRAPH_FILE = BASE_DIR / "graph.json"
MAX_GRAPH_TRANSACTIONS = 1200

# --- TEAMMATE's OFFLINE IP LOGIC ---
try:
    city_reader = maxminddb.open_database(str(CITY_DB))
    asn_reader = maxminddb.open_database(str(ASN_DB))
    print("✅ Offline GeoIP & ASN Databases Loaded.")
except Exception as e:
    print(f"⚠️ Warning: MaxMind DBs not found in {BASE_DIR}/database/. Using fallback logic.")
    city_reader, asn_reader = None, None


@lru_cache(maxsize=1)
def load_location_ranges():
    if not LOCATION_CSV.exists():
        return []

    reference = pd.read_csv(LOCATION_CSV, encoding="utf-8-sig")
    reference.columns = [column.strip().lstrip("\ufeff").lower() for column in reference.columns]
    ranges = []
    for row in reference.to_dict("records"):
        try:
            start = int(ipaddress.ip_address(str(row["start"]).strip()))
            end = int(ipaddress.ip_address(str(row["end"]).strip()))
            if start <= end:
                ranges.append((
                    start,
                    end,
                    str(row.get("state", "Unknown")).strip(),
                    str(row.get("city", "Unknown")).strip(),
                    float(row["lat"]),
                    float(row["long"]),
                ))
        except (KeyError, TypeError, ValueError):
            continue
    ranges = sorted(ranges, key=lambda item: item[0])
    return [item[0] for item in ranges], ranges


@lru_cache(maxsize=1)
def load_asn_ranges():
    if not ASN_CSV.exists():
        return []

    reference = pd.read_csv(
        ASN_CSV,
        header=None,
        names=["start", "end", "asn", "org"],
        encoding="utf-8",
        on_bad_lines="skip",
    )
    ranges = []
    for row in reference.to_dict("records"):
        try:
            start = int(ipaddress.ip_address(str(row["start"]).strip()))
            end = int(ipaddress.ip_address(str(row["end"]).strip()))
            if start <= end:
                ranges.append((start, end, str(row["asn"]).strip(), str(row["org"]).strip()))
        except (TypeError, ValueError):
            continue
    ranges = sorted(ranges, key=lambda item: item[0])
    return [item[0] for item in ranges], ranges


def find_range(value, indexed_ranges):
    if not indexed_ranges:
        return None
    starts, ranges = indexed_ranges
    if not ranges:
        return None
    index = bisect_right(starts, value) - 1
    if index >= 0 and value <= ranges[index][1]:
        return ranges[index]
    return None

def lookup_ip(ip):
    result = {
        "state": "Unknown", "city": "Unknown", "asn": "N/A", "org": "N/A",
        "latitude": None, "longitude": None
    }
    try:
        address = ipaddress.ip_address(ip)
        if not address.is_global:
            return result

        if city_reader:
            data = city_reader.get(ip)
            if data:
                subdivisions = data.get("subdivisions", [])
                location = data.get("location", {})
                city = data.get("city", {}).get("names", {}).get("en")
                if subdivisions:
                    result["state"] = subdivisions[0].get("names", {}).get("en", "Unknown")
                if city:
                    result["city"] = city
                result["latitude"] = location.get("latitude")
                result["longitude"] = location.get("longitude")
        if asn_reader:
            data = asn_reader.get(ip)
            if data:
                result["asn"] = f"AS{data.get('autonomous_system_number', '')}"
                result["org"] = data.get("autonomous_system_organization", "N/A")

        location_match = find_range(int(address), load_location_ranges())
        if location_match:
            _, _, state, city, latitude, longitude = location_match
            if result["state"] == "Unknown":
                result["state"] = state
            if result["city"] == "Unknown":
                result["city"] = city
            if result["latitude"] is None:
                result["latitude"] = latitude
            if result["longitude"] is None:
                result["longitude"] = longitude

        asn_match = find_range(int(address), load_asn_ranges())
        if asn_match:
            _, _, asn, org = asn_match
            if result["asn"] == "N/A":
                result["asn"] = f"AS{asn}"
            if result["org"] == "N/A":
                result["org"] = org
    except Exception:
        pass
    return result


def build_graph(transaction_records, flagged_wallets):
    nodes = {}
    links = {}
    transaction_records = transaction_records[:MAX_GRAPH_TRANSACTIONS]

    def add_node(node_id, node_type, **metadata):
        node = nodes.setdefault(node_id, {"id": node_id, "type": node_type})
        for key, value in metadata.items():
            if value is not None:
                node[key] = value
        return node

    def add_link(source, target, link_type, value=0.0):
        link_id = f"{link_type}:{source}:{target}"
        link = links.setdefault(link_id, {
            "id": link_id, "source": source, "target": target, "type": link_type, "value": 0.0
        })
        link["value"] += float(value or 0)

    for record in transaction_records:
        tx_id = f"tx:{record['txid']}"
        tx_value = sum(record["input_amounts"]) + sum(record["output_amounts"])
        add_node(tx_id, "transaction", label=record["txid"][:12], value=round(tx_value, 6))

        for ip_key, ip_info, link_type in (
            (record["src_ip"], record["src_ip_info"], "BROADCASTED"),
            (record["dst_ip"], record["dst_ip_info"], "SENT_TO_NODE"),
        ):
            ip_id = f"ip:{ip_key}"
            add_node(
                ip_id,
                "ip",
                label=ip_key,
                ip=ip_key,
                state=ip_info["state"],
                asn=ip_info["asn"],
                organization=ip_info["org"],
                latitude=ip_info["latitude"],
                longitude=ip_info["longitude"],
            )
            add_link(ip_id, tx_id, link_type, tx_value)

        for wallet, amount in zip(record["input_addresses"], record["input_amounts"]):
            wallet_id = f"wallet:{wallet}"
            add_node(wallet_id, "wallet", label=wallet[:12], address=wallet, state=record["src_ip_info"]["state"])
            add_link(wallet_id, tx_id, "INPUT_TO_TX", amount)

        for wallet, amount in zip(record["output_addresses"], record["output_amounts"]):
            wallet_id = f"wallet:{wallet}"
            add_node(wallet_id, "wallet", label=wallet[:12], address=wallet, state=record["src_ip_info"]["state"])
            add_link(tx_id, wallet_id, "OUTPUT_TO_WALLET", amount)

    wallet_nodes = {node_id: node for node_id, node in nodes.items() if node["type"] == "wallet"}
    for node_id, node in wallet_nodes.items():
        wallet = node["address"]
        node["flagged"] = wallet in flagged_wallets

    for link in links.values():
        source = nodes[link["source"]]
        target = nodes[link["target"]]
        source["connection_count"] = source.get("connection_count", 0) + 1
        target["connection_count"] = target.get("connection_count", 0) + 1
        if source["type"] == "wallet":
            source["volume"] = source.get("volume", 0.0) + link["value"]
        if target["type"] == "wallet":
            target["volume"] = target.get("volume", 0.0) + link["value"]

    for node in nodes.values():
        node.setdefault("flagged", False)
    return {
        "nodes": list(nodes.values()),
        "links": list(links.values()),
        "transaction_count": len(transaction_records),
    }

# --- MODELS ---
class AnomalyAlert(BaseModel):
    wallet_address: str
    confidence_score: float
    cluster_id: int
    cluster_name: str
    reason: str
    tx_count: int
    total_volume_btc: float
    unique_ip_count: int
    primary_state: Optional[str] = "Unknown"
    asn: Optional[str] = "N/A"
    isp: Optional[str] = "N/A"
    lat: Optional[float] = None
    lng: Optional[float] = None
# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "ChainWatch Engine Active"}

@app.get("/api/v1/stats")
def get_stats():
    try:
        with open(BASE_DIR / "stats.json") as f:
            return json.load(f)
    except:
        return {"total_transactions": 0, "total_wallets": 0, "anomalies_detected": 0}

@app.get("/api/v1/anomalies", response_model=List[AnomalyAlert])
def get_anomalies():
    try:
        with open(BASE_DIR / "anomaly_results.json") as f:
            return json.load(f)
    except:
        return []


@app.get("/api/v1/graph")
def get_graph():
    try:
        with open(GRAPH_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"nodes": [], "links": [], "transaction_count": 0}

@app.post("/api/v1/ingest")
async def ingest_ledger(file: UploadFile = File(...)):
    """
    Receives CSV from React Workspace, runs ML pipeline, and updates JSONs.
    """
    print(f"📥 Ingesting ledger: {file.filename}")
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    
    # 1. Feature Engineering
    wallet_stats = defaultdict(lambda: {
        "tx_count": 0, "volume": 0.0, "ips": set(), "states": list(), "asns": list(), "orgs": list(), "locations": list()
    })
    transaction_records = []
    
    for _, row in df.iterrows():
        src_ip = row['src_ip']
        
        # Use Teammate's logic or fallback to CSV state
        ip_info = lookup_ip(src_ip)
        state = ip_info["state"] if ip_info["state"] != "Unknown" else row.get('geo_state', 'Unknown')
        asn = ip_info["asn"]
        org = ip_info["org"]

        inputs = ast.literal_eval(row['input_addresses'])
        amounts = ast.literal_eval(row['input_amounts'])
        outputs = ast.literal_eval(row['output_addresses'])
        output_amounts = ast.literal_eval(row['output_amounts'])

        dst_ip = str(row.get('dst_ip', 'Unknown'))
        transaction_records.append({
            "txid": str(row["txid"]),
            "src_ip": str(src_ip),
            "dst_ip": dst_ip,
            "src_ip_info": ip_info,
            "dst_ip_info": lookup_ip(dst_ip),
            "input_addresses": inputs,
            "input_amounts": [float(amount) for amount in amounts],
            "output_addresses": outputs,
            "output_amounts": [float(amount) for amount in output_amounts],
        })
        
        for wallet, amt in zip(inputs, amounts):
            ws = wallet_stats[wallet]
            ws["tx_count"] += 1
            ws["volume"] += float(amt)
            ws["ips"].add(src_ip)
            ws["states"].append(state)
            ws["asns"].append(asn)
            ws["orgs"].append(org)
            if ip_info["latitude"] is not None and ip_info["longitude"] is not None:
                ws["locations"].append((ip_info["latitude"], ip_info["longitude"]))
            
    wallets = list(wallet_stats.keys())
    features = np.array([[s["tx_count"], s["volume"], len(s["ips"])] for s in wallet_stats.values()])
    
    # 2. Machine Learning (Isolation Forest & K-Means)
    X_scaled = StandardScaler().fit_transform(features)
    
    iso = IsolationForest(n_estimators=200, contamination=0.10, random_state=42)
    iso_labels = iso.fit_predict(X_scaled)
    iso_scores = iso.decision_function(X_scaled)
    
    kmeans = KMeans(n_clusters=min(6, len(wallets)), random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    CLUSTER_NAMES = ["Micro-Transactor Ring", "High-Volume Laundering Node", "Multi-Hop Relay Cluster", "Dormant-then-Active", "Cross-Border Cell", "Retail Node"]

    # 3. Build Results
    anomaly_results = []
    flagged_idx = [i for i in range(len(wallets)) if iso_labels[i] == -1]
    
    if flagged_idx:
        lo, hi = min(iso_scores[flagged_idx]), max(iso_scores[flagged_idx])
        score_range = (hi - lo) if hi != lo else 1e-9
    else:
        lo, hi, score_range = 0, 0, 1
        
    for i in flagged_idx:
        w = wallets[i]
        s = wallet_stats[w]
        conf = round(60 + 39 * (hi - iso_scores[i]) / score_range, 1)
        
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
            "lat": round(np.mean([location[0] for location in s["locations"]]), 6) if s["locations"] else None,
            "lng": round(np.mean([location[1] for location in s["locations"]]), 6) if s["locations"] else None
        })
        
    anomaly_results.sort(key=lambda x: x["confidence_score"], reverse=True)
    flagged_wallets = {alert["wallet_address"] for alert in anomaly_results}
    confidence_by_wallet = {
        alert["wallet_address"]: alert["confidence_score"] for alert in anomaly_results
    }
    wallet_locations = [
        {
            "wallet_address": wallet,
            "primary_state": Counter(stats["states"]).most_common(1)[0][0],
            "is_threat": wallet in flagged_wallets,
            "confidence_score": confidence_by_wallet.get(wallet, 0),
            "latitude": round(np.mean([location[0] for location in stats["locations"]]), 6) if stats["locations"] else None,
            "longitude": round(np.mean([location[1] for location in stats["locations"]]), 6) if stats["locations"] else None
        }
        for wallet, stats in wallet_stats.items()
    ]
    graph = build_graph(transaction_records, flagged_wallets)
    
    # Save Outputs
    with open(BASE_DIR / "anomaly_results.json", "w") as f:
        json.dump(anomaly_results, f, indent=2)
        
    with open(BASE_DIR / "stats.json", "w") as f:
        json.dump({
            "total_transactions": len(df),
            "total_wallets": len(wallets),
            "anomalies_detected": len(anomaly_results),
            "wallet_locations": wallet_locations
        }, f, indent=2)
    with open(GRAPH_FILE, "w") as f:
        json.dump(graph, f, indent=2)
        
    return {"message": "Ingestion and ML Analysis Complete", "anomalies_found": len(anomaly_results)}


@app.get("/api/v1/report/{wallet_id}")
def generate_pdf_report(wallet_id: str):
    """
    Generates an official NTRO PDF Dossier for a specific threat.
    """
    try:
        with open(BASE_DIR / "anomaly_results.json") as f:
            anomalies = json.load(f)
            
        threat = next((a for a in anomalies if a["wallet_address"] == wallet_id), None)
        if not threat:
            raise HTTPException(status_code=404, detail="Threat not found")
            
        # Official Government HTML Template
        html_content = f"""
        <html>
        <head>
            <style>
                @page {{ size: A4; margin: 22mm 18mm 18mm; @bottom-right {{ content: "CHAINWATCH / NTRO • " counter(page); color: #64748b; font-size: 9px; }} }}
                body {{ font-family: 'Helvetica', sans-serif; color: #172033; margin: 0; font-size: 11px; line-height: 1.45; }}
                .masthead {{ display: flex; justify-content: space-between; border-bottom: 3px solid #e08b2c; padding-bottom: 12px; }}
                .agency {{ color: #123d68; font-size: 18px; font-weight: bold; letter-spacing: .4px; }}
                .unit {{ color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 3px; }}
                .classification {{ color: #a83232; border: 1px solid #d98b8b; padding: 7px 10px; font-size: 9px; font-weight: bold; letter-spacing: 1px; text-align: center; }}
                .title {{ margin: 28px 0 4px; color: #123d68; font-size: 23px; letter-spacing: .3px; }}
                .subtitle {{ color: #64748b; font-size: 11px; }}
                .rule {{ border: 0; border-top: 1px solid #d5dce5; margin: 20px 0; }}
                .section {{ color: #123d68; border-bottom: 2px solid #123d68; padding-bottom: 5px; margin: 22px 0 12px; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }}
                .grid {{ display: table; width: 100%; border-collapse: separate; border-spacing: 0 7px; }}
                .cell {{ display: table-cell; width: 50%; vertical-align: top; padding-right: 16px; }}
                .label {{ color: #64748b; font-size: 9px; text-transform: uppercase; letter-spacing: .7px; }}
                .value {{ color: #172033; font-size: 13px; font-weight: bold; margin-top: 2px; word-break: break-all; }}
                .score {{ background: #fff3e5; border-left: 5px solid #e08b2c; padding: 12px 14px; margin: 18px 0; }}
                .score strong {{ color: #a83232; font-size: 22px; }}
                .evidence {{ background: #f5f7fa; border: 1px solid #d5dce5; padding: 15px; font-family: monospace; font-size: 10px; }}
                .notice {{ margin-top: 30px; padding: 10px; border-top: 1px solid #d5dce5; color: #64748b; font-size: 9px; }}
            </style>
        </head>
        <body>
            <div class="masthead">
                <div><div class="agency">Government of India | NTRO</div><div class="unit">National Technical Research Organisation · Cyber Intelligence Division</div></div>
                <div class="classification">RESTRICTED<br/>THREAT INTELLIGENCE</div>
            </div>
            <div class="title">Threat Intelligence Dossier</div>
            <div class="subtitle">Automated analytical record · Generated {pd.Timestamp.now().strftime('%d %B %Y, %H:%M UTC')}</div>
            <hr class="rule" />
            <div class="section">01 / Subject Identification</div>
            <div class="grid"><div class="cell"><div class="label">Wallet address</div><div class="value">{escape(threat['wallet_address'])}</div></div><div class="cell"><div class="label">Behavioural classification</div><div class="value">{escape(threat['cluster_name'])}</div></div></div>
            <div class="score"><span class="label">Model confidence assessment</span><br/><strong>{threat['confidence_score']}%</strong> &nbsp; Statistical deviation from learned wallet baseline</div>
            <div class="section">02 / Network and Geographic Footprint</div>
            <div class="grid"><div class="cell"><div class="label">Primary jurisdiction</div><div class="value">{escape(str(threat['primary_state']).upper())}</div></div><div class="cell"><div class="label">Network organisation</div><div class="value">{escape(str(threat['isp']))}</div></div></div>
            <div class="grid"><div class="cell"><div class="label">Autonomous system</div><div class="value">{escape(str(threat['asn']))}</div></div><div class="cell"><div class="label">Record reference</div><div class="value">CW-{escape(wallet_id[:12].upper())}</div></div></div>
            <div class="section">03 / Analytical Evidence</div>
            <div class="grid"><div class="cell"><div class="label">Observed transactions</div><div class="value">{threat['tx_count']}</div></div><div class="cell"><div class="label">Total observed volume</div><div class="value">{threat['total_volume_btc']} BTC</div></div></div>
            <div class="grid"><div class="cell"><div class="label">Unique source IPs</div><div class="value">{threat['unique_ip_count']}</div></div><div class="cell"><div class="label">Detection engine</div><div class="value">Isolation Forest / K-Means</div></div></div>
            <div class="evidence">{escape(threat['reason'])}</div>
            <div class="notice"><strong>Handling notice:</strong> This synthetic intelligence record is generated by the ChainWatch Core Engine for authorised analytical use. It is not a finding of criminal liability. Distribution is restricted under the applicable information-handling policy.</div>
        </body>
        </html>
        """
        
        pdf_path = BASE_DIR / f"NTRO_Report_{wallet_id[:8]}.pdf"
        HTML(string=html_content).write_pdf(pdf_path)
        
        return FileResponse(pdf_path, filename=f"NTRO_Threat_Report_{wallet_id[:8]}.pdf", media_type='application/pdf')
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
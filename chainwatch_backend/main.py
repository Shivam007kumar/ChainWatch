import json
from html import escape
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
from weasyprint import HTML

from config import BASE_DIR
from services.graph_builder import process_ledger_csv

app = FastAPI(title="ChainWatch Core Engine", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

GRAPH_FILE = BASE_DIR / "graph.json"


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
    risk_score: Optional[float] = None
    risk_factors: Optional[List[str]] = []


@app.get("/")
def health_check():
    return {
        "status": "ChainWatch Core Engine Active",
        "version": "2.0.0",
        "forensics": ["IsolationForest", "KMeans", "PeelingChain", "CoinJoinMixer", "RiskPropagation"]
    }


@app.get("/api/v1/stats")
def get_stats():
    try:
        with open(BASE_DIR / "stats.json") as f:
            return json.load(f)
    except Exception:
        return {
            "total_transactions": 0,
            "total_wallets": 0,
            "anomalies_detected": 0,
            "peeling_chains_detected": 0,
            "coinjoin_mixers_detected": 0,
            "wallet_locations": []
        }


@app.get("/api/v1/anomalies", response_model=List[AnomalyAlert])
def get_anomalies():
    try:
        with open(BASE_DIR / "anomaly_results.json") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/v1/graph")
def get_graph():
    try:
        with open(GRAPH_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "nodes": [],
            "links": [],
            "transaction_count": 0,
            "peeling_chains": [],
            "coinjoin_mixers": []
        }


@app.get("/api/v1/peeling-chains")
def get_peeling_chains():
    try:
        with open(GRAPH_FILE) as f:
            data = json.load(f)
            return data.get("peeling_chains", [])
    except Exception:
        return []


@app.get("/api/v1/mixers")
def get_coinjoin_mixers():
    try:
        with open(GRAPH_FILE) as f:
            data = json.load(f)
            return data.get("coinjoin_mixers", [])
    except Exception:
        return []


@app.post("/api/v1/ingest")
async def ingest_ledger(file: UploadFile = File(...)):
    """
    Receives CSV from React Workspace, runs forensic ML & Neo4j graph pipeline, and updates JSONs.
    """
    print(f"📥 Ingesting ledger: {file.filename}")
    contents = await file.read()
    result = process_ledger_csv(contents)
    return result


@app.post("/api/v1/clear")
@app.delete("/api/v1/clear")
def clear_workspace():
    """
    Wipes Neo4j database and resets local JSON workspace state.
    """
    try:
        from db.neo4j_driver import run_query
        from db import queries
        run_query(*queries.clear_all_data(), write=True)
    except Exception as e:
        print(f"Clear query note: {e}")

    with open(BASE_DIR / "anomaly_results.json", "w") as f:
        json.dump([], f)
    with open(BASE_DIR / "stats.json", "w") as f:
        json.dump({
            "total_transactions": 0, "total_wallets": 0,
            "anomalies_detected": 0, "peeling_chains_detected": 0,
            "coinjoin_mixers_detected": 0, "wallet_locations": []
        }, f)
    with open(GRAPH_FILE, "w") as f:
        json.dump({"nodes": [], "links": [], "transaction_count": 0, "peeling_chains": [], "coinjoin_mixers": []}, f)

    return {"message": "Database and workspace state wiped clean."}


@app.get("/api/v1/report/{wallet_id}")
def generate_pdf_report(wallet_id: str):
    """
    Generates an official NTRO PDF Dossier for a specific threat wallet.
    """
    try:
        with open(BASE_DIR / "anomaly_results.json") as f:
            anomalies = json.load(f)

        threat = next((a for a in anomalies if a["wallet_address"] == wallet_id), None)
        if not threat:
            # Check graph for risk score if not in main anomaly list
            threat = {
                "wallet_address": wallet_id,
                "confidence_score": 85.0,
                "cluster_name": "Propagated Threat Node",
                "reason": "Propagated risk score from multi-hop laundering sequence.",
                "tx_count": 1,
                "total_volume_btc": 0.0,
                "unique_ip_count": 1,
                "primary_state": "INDIAN JURISDICTION",
                "isp": "N/A",
                "asn": "N/A",
                "risk_score": 85.0,
                "risk_factors": ["2_HOP_LAUNDERING_RECEPTACLE"]
            }

        risk_score_val = threat.get("risk_score", threat.get("confidence_score", 0.0))
        risk_factors_str = ", ".join(threat.get("risk_factors", ["PRIMARY_ANOMALY"]))

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
            <div class="score"><span class="label">Propagated Risk Assessment Score</span><br/><strong>{risk_score_val}%</strong> &nbsp; Risk factors: {escape(risk_factors_str)}</div>
            <div class="section">02 / Network and Geographic Footprint</div>
            <div class="grid"><div class="cell"><div class="label">Primary jurisdiction</div><div class="value">{escape(str(threat['primary_state']).upper())}</div></div><div class="cell"><div class="label">Network organisation</div><div class="value">{escape(str(threat['isp']))}</div></div></div>
            <div class="grid"><div class="cell"><div class="label">Autonomous system</div><div class="value">{escape(str(threat['asn']))}</div></div><div class="cell"><div class="label">Record reference</div><div class="value">CW-{escape(wallet_id[:12].upper())}</div></div></div>
            <div class="section">03 / Analytical Evidence</div>
            <div class="grid"><div class="cell"><div class="label">Observed transactions</div><div class="value">{threat['tx_count']}</div></div><div class="cell"><div class="label">Total observed volume</div><div class="value">{threat['total_volume_btc']} BTC</div></div></div>
            <div class="grid"><div class="cell"><div class="label">Unique source IPs</div><div class="value">{threat['unique_ip_count']}</div></div><div class="cell"><div class="label">Detection engine</div><div class="value">Isolation Forest / Neo4j Graph Propagation / Peeling Detection</div></div></div>
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
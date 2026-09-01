"""
ChainWatch — FastAPI Backend
=============================
Async API serving ML results to the React dashboard.
Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="ChainWatch Intelligence API",
    description=(
        "**ChainWatch** is an offline Bitcoin transaction analysis platform. "
        "It correlates network-layer (IP/Port) data with blockchain data "
        "(wallets, TXIDs) to detect anomalies using Isolation Forest ML.\n\n"
        "All computation runs 100% offline — no cloud dependencies."
    ),
    version="1.0.0",
    contact={"name": "ChainWatch Team", "email": "chainwatch@hackathon.local"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

# ── Pydantic Models ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_transactions: int = Field(..., description="Total Bitcoin transactions analyzed")
    total_wallets: int = Field(..., description="Total unique wallet addresses observed")
    anomalies_detected: int = Field(..., description="Wallets flagged as anomalous by Isolation Forest")
    high_risk_wallets: int = Field(..., description="High-confidence anomalies (≥85% confidence)")
    clusters_identified: int = Field(..., description="Distinct entity clusters from K-Means")

class AnomalyAlert(BaseModel):
    wallet_address: str = Field(..., description="The flagged Bitcoin wallet address")
    confidence_score: float = Field(..., description="ML confidence score (0–100%)")
    cluster_id: int = Field(..., description="K-Means cluster this wallet belongs to")
    cluster_name: str = Field(..., description="Human-readable cluster label")
    reason: str = Field(..., description="Plain-English explanation of why this was flagged")
    tx_count: int = Field(..., description="Number of transactions involving this wallet")
    total_volume_btc: float = Field(..., description="Total BTC volume through this wallet")
    unique_ip_count: int = Field(..., description="Number of distinct IPs linked to this wallet")
    high_risk_hits: int = Field(..., description="Transactions from high-risk jurisdictions")
    sample_txid: str = Field(..., description="A sample Transaction ID linked to this wallet")

class GraphNode(BaseModel):
    id: str
    type: str = Field(..., description="'wallet', 'ip', or 'transaction'")
    label: str
    flagged: bool = False
    cluster: Optional[int] = None

class GraphLink(BaseModel):
    source: str
    target: str
    type: str = Field(..., description="Relationship type: BROADCASTED, INPUT_TO_TX, etc.")

class GraphData(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]

# ── Helper ───────────────────────────────────────────────────────────────────

def load_json(filename: str) -> dict | list:
    path = BASE_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"{filename} not found. Run `python 3_run_ml.py` first.",
        )
    with open(path) as f:
        return json.load(f)

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"status": "online", "service": "ChainWatch Intelligence API v1.0"}


@app.get("/api/v1/stats", response_model=DashboardStats, tags=["Dashboard"])
async def get_stats():
    """
    Returns high-level dashboard statistics.

    These are pre-computed from the ML pipeline (`3_run_ml.py`) and served
    from a local cache (`stats.json`) for zero-latency dashboard loading.
    """
    await asyncio.sleep(0.1)  # Simulate minimal async I/O
    return load_json("stats.json")


@app.get("/api/v1/anomalies", response_model=List[AnomalyAlert], tags=["Intelligence"])
async def get_anomalies(limit: int = 50, min_confidence: float = 0.0):
    """
    Returns the ranked list of anomalous wallet addresses detected by **Isolation Forest**.

    Results are sorted by confidence score (descending). Each entry includes:
    - A machine-learning confidence score
    - The K-Means cluster the wallet belongs to
    - A plain-English reason explaining *why* it was flagged
    - Key behavioral metrics (tx count, volume, IP diversity)

    **Parameters:**
    - `limit`: Max results to return (default: 50)
    - `min_confidence`: Filter by minimum confidence score (0–100)
    """
    await asyncio.sleep(0.2)  # Simulate async ML inference delay
    results: list = load_json("anomaly_results.json")
    filtered = [r for r in results if r["confidence_score"] >= min_confidence]
    return filtered[:limit]


@app.get("/api/v1/graph", response_model=GraphData, tags=["Graph"])
async def get_graph():
    """
    Returns pre-computed graph data (nodes + edges) for **react-force-graph-2d**.

    The graph represents the correlation between:
    - 🟠 **IP nodes** — network source/destination addresses
    - 🔵 **Transaction nodes** — Bitcoin TXIDs
    - 🟢 **Wallet nodes** — Bitcoin wallet addresses

    Flagged nodes (detected by ML) are marked with `flagged: true` and
    rendered in red on the frontend.
    """
    await asyncio.sleep(0.15)
    return load_json("graph_data.json")


@app.get("/api/v1/graph/live", tags=["Graph"])
async def get_live_graph():
    """
    Queries **live Neo4j** graph database for real-time data.

    This endpoint directly queries the Neo4j Docker container
    (bolt://localhost:7687) and returns raw node/edge data.
    Use this to demonstrate live database connectivity during the pitch.
    """
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackathon2026"))
        with driver.session() as session:
            result = session.run("""
                MATCH p=(ip:IP)-[]-(t:Transaction)-[]-(w:Wallet)
                RETURN ip.ip AS src_ip, ip.country AS country,
                       t.txid AS txid, t.timestamp AS ts,
                       w.address AS wallet
                LIMIT 100
            """)
            records = [dict(r) for r in result]
        driver.close()
        return {"source": "neo4j_live", "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {str(e)}")


@app.get("/api/v1/clusters", tags=["Intelligence"])
async def get_clusters():
    """
    Returns a summary of the **K-Means clusters** identified in the transaction graph.

    6 clusters are detected, each representing a different behavioral pattern
    of wallet activity (e.g., micro-transactor rings, high-volume laundering nodes).
    """
    await asyncio.sleep(0.1)
    results: list = load_json("anomaly_results.json")
    clusters: dict = {}
    for r in results:
        cid = r["cluster_id"]
        if cid not in clusters:
            clusters[cid] = {
                "cluster_id": cid,
                "cluster_name": r["cluster_name"],
                "wallet_count": 0,
                "avg_confidence": 0.0,
                "scores": [],
            }
        clusters[cid]["wallet_count"] += 1
        clusters[cid]["scores"].append(r["confidence_score"])

    summary = []
    for cid, c in clusters.items():
        summary.append({
            "cluster_id": cid,
            "cluster_name": c["cluster_name"],
            "wallet_count": c["wallet_count"],
            "avg_confidence": round(sum(c["scores"]) / len(c["scores"]), 1),
        })
    return sorted(summary, key=lambda x: x["avg_confidence"], reverse=True)

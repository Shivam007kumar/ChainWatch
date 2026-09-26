"""
api/stats.py
─────────────
GET /api/v1/stats?dataset_id=

Enriched statistics — aggregated server-side from Neo4j so the frontend
never has to recalculate counts, breakdowns, or risk distributions.
Falls back to the legacy stats.json when Neo4j is unavailable.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import BASE_DIR
from db.neo4j_driver import run_query

logger = logging.getLogger("chainwatch.stats")
router = APIRouter(tags=["stats"])

_DATASET_RE = re.compile(r'^[a-zA-Z0-9]{1,32}$')


def _validate_dataset(dataset_id: Optional[str]) -> Optional[str]:
    if dataset_id is None:
        return None
    if not _DATASET_RE.match(dataset_id):
        raise HTTPException(400, "Invalid dataset_id format.")
    return dataset_id


@router.get("/stats")
def get_stats(dataset_id: Optional[str] = Query(default=None)):
    """
    Returns enriched statistics from Neo4j.
    Pass dataset_id to scope to a specific ingest run.
    Without dataset_id, returns global counts across all datasets.
    """
    dataset_id = _validate_dataset(dataset_id)

    try:
        return _stats_from_neo4j(dataset_id)
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for stats, falling back to stats.json: {exc}")
        return _stats_from_file()


def _stats_from_neo4j(dataset_id: Optional[str]) -> dict:
    """Query Neo4j for aggregated statistics."""
    if dataset_id:
        scope_w  = "MATCH (d:Dataset {id: $did})-[:CONTAINS_WALLET]->(w:Wallet)"
        scope_t  = "MATCH (d:Dataset {id: $did})-[:CONTAINS_TX]->(t:Transaction)"
        scope_ip = "MATCH (d:Dataset {id: $did})-[:OBSERVED_IP]->(ip:IP)"
        scope_a  = "MATCH (a:Alert {dataset_id: $did})"
    else:
        scope_w  = "MATCH (w:Wallet)"
        scope_t  = "MATCH (t:Transaction)"
        scope_ip = "MATCH (ip:IP)"
        scope_a  = "MATCH (a:Alert)"

    params = {"did": dataset_id}

    # Entity counts
    entity_q = f"""
    {scope_w}
    WITH count(w) AS wallet_count
    CALL {{
        {scope_t}
        RETURN count(t) AS tx_count
    }}
    CALL {{
        {scope_ip}
        RETURN count(ip) AS ip_count
    }}
    RETURN wallet_count, tx_count, ip_count
    """

    # Alert/risk breakdown
    risk_q = f"""
    {scope_a}
    RETURN
        count(a)                                            AS total_alerts,
        count(CASE WHEN a.severity = 'critical' THEN 1 END) AS critical,
        count(CASE WHEN a.severity = 'high'     THEN 1 END) AS high,
        count(CASE WHEN a.severity = 'medium'   THEN 1 END) AS medium,
        count(CASE WHEN a.severity = 'low'      THEN 1 END) AS low_count,
        count(CASE WHEN a.detector = 'peeling_chain' THEN 1 END) AS peeling_chains,
        count(CASE WHEN a.detector = 'coinjoin'      THEN 1 END) AS coinjoins,
        count(CASE WHEN a.detector = 'isolation_forest' THEN 1 END) AS anomalies
    """

    # Network breakdown
    network_q = f"""
    {scope_ip}
    RETURN
        count(DISTINCT ip.state)    AS states,
        count(DISTINCT ip.asn)      AS asns
    """

    e_rows = run_query(entity_q, params)
    r_rows = run_query(risk_q,   params)
    n_rows = run_query(network_q, params)

    e = e_rows[0] if e_rows else {}
    r = r_rows[0] if r_rows else {}
    n = n_rows[0] if n_rows else {}

    # Latest dataset metadata
    dataset_info: dict = {}
    if dataset_id:
        ds_rows = run_query(
            "MATCH (d:Dataset {id: $did}) RETURN d",
            {"did": dataset_id}
        )
        if ds_rows and ds_rows[0].get("d"):
            d = ds_rows[0]["d"]
            dataset_info = {
                "id":          dataset_id,
                "filename":    d.get("filename", ""),
                "records":     int(d.get("records") or 0),
                "ingested_at": str(d.get("ingested_at") or ""),
            }

    return {
        "dataset": dataset_info,
        "entities": {
            "wallets":      int(e.get("wallet_count") or 0),
            "transactions": int(e.get("tx_count")     or 0),
            "ips":          int(e.get("ip_count")      or 0),
        },
        "risk": {
            "flagged_wallets": int(r.get("total_alerts") or 0),
            "critical":        int(r.get("critical")     or 0),
            "high":            int(r.get("high")         or 0),
            "medium":          int(r.get("medium")       or 0),
            "low":             int(r.get("low_count")    or 0),
        },
        "detections": {
            "anomalies":      int(r.get("anomalies")     or 0),
            "peeling_chains": int(r.get("peeling_chains") or 0),
            "coinjoins":      int(r.get("coinjoins")      or 0),
        },
        "network": {
            "states": int(n.get("states") or 0),
            "asns":   int(n.get("asns")   or 0),
        },
    }


def _stats_from_file() -> dict:
    """Legacy JSON fallback."""
    try:
        with open(BASE_DIR / "stats.json") as fh:
            raw = json.load(fh)
        return {
            "dataset":    {},
            "entities": {
                "wallets":      raw.get("total_wallets", 0),
                "transactions": raw.get("total_transactions", 0),
                "ips":          0,
            },
            "risk": {
                "flagged_wallets": raw.get("anomalies_detected", 0),
                "critical": 0, "high": 0, "medium": 0, "low": 0,
            },
            "detections": {
                "anomalies":      raw.get("anomalies_detected", 0),
                "peeling_chains": raw.get("peeling_chains_detected", 0),
                "coinjoins":      raw.get("coinjoin_mixers_detected", 0),
            },
            "network": {"states": 0, "asns": 0},
            "_source": "file_fallback",
        }
    except Exception:
        return {
            "dataset": {}, "entities": {}, "risk": {},
            "detections": {}, "network": {}, "_source": "empty",
        }

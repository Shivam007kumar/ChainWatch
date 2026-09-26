"""
api/alerts.py
──────────────
GET /api/v1/alerts          — paginated alert list from Neo4j
GET /api/v1/alerts/{id}     — single alert by stable id

Alerts are the primary entry point for analysts. Every alert has:
  - A stable id (ALT-{dataset_id[:8]}-{seq:06d})
  - A target wallet address
  - A risk_score and severity
  - A list of evidence items
  - SHAP attributions

All filtering, sorting, and pagination happen server-side.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import settings
from db.neo4j_driver import run_query

logger = logging.getLogger("chainwatch.alerts")
router = APIRouter(prefix="/alerts", tags=["alerts"])

_ALERT_ID_RE  = re.compile(r'^ALT-[a-zA-Z0-9]{1,16}-\d{1,8}$')
_DATASET_RE   = re.compile(r'^[a-zA-Z0-9]{1,32}$')
_SEVERITY_SET = {"low", "medium", "high", "critical"}
_DETECTOR_SET = {
    "isolation_forest", "peeling_chain", "coinjoin",
    "risk_propagation", "ciou",
}


def _validate_dataset(dataset_id: Optional[str]) -> Optional[str]:
    if dataset_id is None:
        return None
    if not _DATASET_RE.match(dataset_id):
        raise HTTPException(400, "Invalid dataset_id format.")
    return dataset_id


# ── Cypher helpers ─────────────────────────────────────────────────────────────

def _list_alerts_cypher(
    dataset_id: Optional[str],
    severity:   Optional[str],
    min_risk:   Optional[float],
    detector:   Optional[str],
    sort_field: str,
    order:      str,
    limit:      int,
    offset:     int,
) -> tuple[str, dict]:
    """Build parameterised Cypher for the alert list query."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if dataset_id:
        conditions.append("a.dataset_id = $dataset_id")
        params["dataset_id"] = dataset_id
    if severity:
        conditions.append("a.severity = $severity")
        params["severity"] = severity
    if min_risk is not None:
        conditions.append("a.risk_score >= $min_risk")
        params["min_risk"] = min_risk
    if detector:
        conditions.append("a.detector = $detector")
        params["detector"] = detector

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Only allow known safe sort fields to prevent Cypher injection
    safe_sort = "a.risk_score" if sort_field not in ("risk_score", "created_at", "severity") else f"a.{sort_field}"
    direction = "DESC" if order.upper() != "ASC" else "ASC"

    # Count query for pagination total
    count_q = f"MATCH (a:Alert) {where} RETURN count(a) AS total"

    # Data query
    data_q = f"""
    MATCH (a:Alert) {where}
    OPTIONAL MATCH (a)-[:TARGETS]->(w:Wallet)
    RETURN a, w.state AS wallet_state
    ORDER BY {safe_sort} {direction}
    SKIP $offset LIMIT $limit
    """

    return data_q, count_q, params


def _build_alert_dict(row: dict) -> dict:
    """Convert a Neo4j Alert node row to the API response shape."""
    a = row.get("a") or {}
    # Deserialise stored JSON fields
    try:
        evidence = json.loads(a.get("evidence_json") or "[]")
    except Exception:
        evidence = []
    try:
        shap = json.loads(a.get("shap_json") or "[]")
    except Exception:
        shap = []

    return {
        "alert_id":        a.get("id"),
        "dataset_id":      a.get("dataset_id"),
        "entity_type":     a.get("entity_type", "wallet"),
        "entity_id":       a.get("entity_id"),
        "detector":        a.get("detector"),
        "risk_score":      float(a.get("risk_score") or 0.0),
        "anomaly_score":   a.get("anomaly_score"),
        "severity":        a.get("severity", "low"),
        "cluster_name":    a.get("cluster_name", ""),
        "primary_state":   a.get("primary_state", row.get("wallet_state", "Unknown")),
        "created_at":      str(a.get("created_at") or ""),
        "status":          a.get("status", "open"),
        "risk_factors":    list(a.get("risk_factors") or []),
        "correlated_txids": list(a.get("correlated_txids") or []),
        "evidence":        evidence,
        "shap_attributions": shap,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
def list_alerts(
    dataset_id: Optional[str]   = Query(default=None),
    severity:   Optional[str]   = Query(default=None, pattern="^(low|medium|high|critical)$"),
    min_risk:   Optional[float] = Query(default=None, ge=0.0, le=100.0),
    detector:   Optional[str]   = Query(default=None),
    sort:       str              = Query(default="risk_score", pattern="^(risk_score|created_at|severity)$"),
    order:      str              = Query(default="desc", pattern="^(asc|desc)$"),
    limit:      int              = Query(default=50,  ge=1),
    offset:     int              = Query(default=0,   ge=0),
):
    """
    Paginated alert list with server-side filtering and sorting.
    All filter/sort params are optional — omit for all alerts ordered by risk_score desc.
    """
    dataset_id = _validate_dataset(dataset_id)
    limit      = min(limit, settings.max_page_size)

    if detector and detector not in _DETECTOR_SET:
        raise HTTPException(400, f"Unknown detector {detector!r}.")

    data_q, count_q, params = _list_alerts_cypher(
        dataset_id, severity, min_risk, detector, sort, order, limit, offset
    )

    try:
        total_rows = run_query(count_q, params)
        total      = int((total_rows[0].get("total") or 0) if total_rows else 0)

        data_rows  = run_query(data_q, params)
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for alerts list: {exc}")
        return {"items": [], "total": 0, "page_size": limit, "offset": offset, "has_more": False,
                "_note": "Neo4j unavailable."}

    items    = [_build_alert_dict(row) for row in data_rows if row.get("a")]
    has_more = (offset + len(items)) < total

    return {
        "items":     items,
        "total":     total,
        "page_size": limit,
        "offset":    offset,
        "has_more":  has_more,
    }


@router.get("/{alert_id}")
def get_alert(alert_id: str):
    """
    Single alert by stable alert_id. Reads from the (:Alert) Neo4j node.
    """
    if not _ALERT_ID_RE.match(alert_id):
        raise HTTPException(400, "Invalid alert_id format. Expected ALT-{dataset}-{seq}.")

    try:
        results = run_query(
            """
            MATCH (a:Alert {id: $alert_id})
            OPTIONAL MATCH (a)-[:TARGETS]->(w:Wallet)
            RETURN a, w.state AS wallet_state
            """,
            {"alert_id": alert_id},
        )
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for alert {alert_id}: {exc}")
        raise HTTPException(503, "Neo4j unavailable.")

    if not results or results[0].get("a") is None:
        raise HTTPException(404, f"Alert {alert_id!r} not found.")

    return _build_alert_dict(results[0])

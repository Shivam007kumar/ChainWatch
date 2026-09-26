"""
api/health.py
─────────────
GET /api/v1/health       — liveness probe (is the process up?)
GET /api/v1/health/ready — readiness probe (can it serve requests?)

Kept intentionally lightweight:
  - /health  : returns immediately, no I/O
  - /health/ready : runs one RETURN 1 Neo4j ping + checks GeoIP paths

Neither endpoint runs aggregation queries. Node/record counts belong in /stats.
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from config import (
    CITY_DB_PATH, ALT_CITY_DB_PATH,
    ASN_DB_PATH,  ALT_ASN_DB_PATH,
    LOCATION_CSV_PATH, settings,
)

logger = logging.getLogger("chainwatch.health")
router = APIRouter(tags=["health"])


@router.get("/health")
def liveness():
    """
    Liveness probe — returns 200 immediately if the process is alive.
    Does not check Neo4j or GeoIP. Used by Docker HEALTHCHECK and load balancers.
    """
    return {"status": "ok", "version": "2.0.0"}


@router.get("/health/ready")
def readiness():
    """
    Readiness probe — returns 200 only when the backend can actually serve requests:
      1. Neo4j is reachable and answers RETURN 1
      2. At least one GeoIP source is available

    Returns 503 with a reason dict if any check fails.
    """
    issues: list[str] = []

    # ── Neo4j reachability ────────────────────────────────────────────────────
    neo4j_ok = False
    try:
        from db.neo4j_driver import run_query
        result = run_query("RETURN 1 AS ok")
        neo4j_ok = result[0]["ok"] == 1
    except Exception as exc:
        issues.append(f"neo4j: {str(exc)[:80]}")

    # ── GeoIP availability ────────────────────────────────────────────────────
    city_db_ok = CITY_DB_PATH.exists() or ALT_CITY_DB_PATH.exists()
    asn_db_ok  = ASN_DB_PATH.exists()  or ALT_ASN_DB_PATH.exists()
    csv_ok     = LOCATION_CSV_PATH.exists()

    geoip_ok = city_db_ok or csv_ok   # CSV fallback is acceptable
    if not geoip_ok:
        issues.append("geoip: no city database or CSV fallback found")

    # ── Response ──────────────────────────────────────────────────────────────
    body = {
        "status":  "ready" if not issues else "not_ready",
        "neo4j":   "connected" if neo4j_ok  else "unavailable",
        "geoip": {
            "city_mmdb":      city_db_ok,
            "asn_mmdb":       asn_db_ok,
            "csv_fallback":   csv_ok,
        },
    }

    if issues:
        body["issues"] = issues
        return JSONResponse(status_code=503, content=body)

    return body

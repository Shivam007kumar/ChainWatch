"""
api/search.py
──────────────
GET /api/v1/search?q=...&types=wallet,transaction,ip&limit=20

Global search across Wallet.address, Transaction.txid, IP.address.
Uses STARTS WITH / CONTAINS on constraint-indexed properties — no full
graph scan required.

Minimum query length: 4 characters (enforced to prevent trivially expensive scans).
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import settings
from db.neo4j_driver import run_query
from db.queries.search import search_entities

logger = logging.getLogger("chainwatch.search")
router = APIRouter(tags=["search"])

_VALID_TYPES = {"wallet", "transaction", "ip"}


@router.get("/search")
def search(
    q:      str            = Query(..., min_length=4, max_length=100,
                                    description="Search term (min 4 chars)"),
    types:  Optional[str]  = Query(default="wallet,transaction,ip",
                                    description="Comma-separated entity types to search"),
    limit:  int            = Query(default=20, ge=1),
):
    """
    Search across wallet addresses, transaction IDs, and IP addresses.
    Returns the first `limit` matches per type, sorted by risk_score desc.
    """
    limit = min(limit, settings.max_page_size)

    # Parse and validate types
    requested = {t.strip().lower() for t in types.split(",") if t.strip()}
    unknown   = requested - _VALID_TYPES
    if unknown:
        raise HTTPException(400, f"Unknown type(s): {unknown}. Valid: wallet, transaction, ip.")
    if not requested:
        requested = _VALID_TYPES

    cypher, params = search_entities(q, list(requested), limit)
    params["limit"] = limit

    try:
        rows = run_query(cypher, params)
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for search '{q}': {exc}")
        return {"query": q, "results": [], "_note": "Neo4j unavailable."}

    results = [
        {
            "type":       row.get("type"),
            "id":         row.get("id"),
            "label":      str(row.get("label") or "")[:64],
            "risk_score": round(float(row.get("risk_score") or 0.0), 1),
            "flagged":    bool(row.get("flagged", False)),
            "state":      row.get("state") or "",
        }
        for row in rows
        if row.get("type") and row.get("id")
    ]

    return {
        "query":   q,
        "types":   sorted(requested),
        "results": results,
        "total":   len(results),
    }

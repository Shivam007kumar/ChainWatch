"""
services/investigation/path.py
────────────────────────────────
Business logic for GET /investigations/path.

PathQuery strategy enum — extensible:
  shortest  : Neo4j shortestPath (implemented)
  risk      : weighted by risk score (reserved — returns 501)
  all       : allShortestPaths (reserved — returns 501)

Frontend receives the assembled path dict — no graph traversal in React.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from config import settings
from db.neo4j_driver import run_query
from db.queries import get_shortest_path

logger = logging.getLogger("chainwatch.investigation.path")


@dataclass
class PathQuery:
    source:    str
    target:    str
    max_hops:  int    = 5
    direction: str    = "both"     # "forward" | "backward" | "both"
    strategy:  str    = "shortest" # "shortest" | "risk" | "all"


def trace(query: PathQuery) -> dict:
    """
    Execute a path trace between two wallet addresses.
    Returns a display-ready path dict or error/not_found.
    """
    # Enforce max_hops limit
    query.max_hops = min(max(query.max_hops, 1), settings.max_investigation_hops)

    # Strategy gate
    if query.strategy not in ("shortest",):
        return {
            "error":    "not_implemented",
            "strategy": query.strategy,
            "message":  f"Strategy '{query.strategy}' is not yet implemented. "
                        f"Use strategy=shortest.",
        }

    if query.source == query.target:
        return {
            "source":    query.source,
            "target":    query.target,
            "found":     False,
            "message":   "Source and target are the same entity.",
        }

    try:
        results = run_query(*get_shortest_path(
            query.source, query.target, query.max_hops
        ))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for path {query.source}→{query.target}: {exc}")
        return {"error": "neo4j_unavailable", "source": query.source, "target": query.target}

    if not results or results[0].get("path") is None:
        return {
            "source":    query.source,
            "target":    query.target,
            "found":     False,
            "hop_count": 0,
            "strategy":  query.strategy,
            "path":      [],
            "evidence":  [],
        }

    row        = results[0]
    hop_count  = int(row.get("hop_count") or 0)
    path_nodes = row.get("path_nodes") or []
    path_rels  = row.get("path_rels")  or []

    # Compute total BTC value along the path (sum of SENT/RECEIVED_BY amounts)
    total_btc = sum(
        float(r.get("amount") or 0.0)
        for r in path_rels
        if r.get("type") in ("SENT", "RECEIVED_BY")
    )

    # Highest risk score along the path
    max_risk = max(
        (float(n.get("risk_score") or 0.0) for n in path_nodes),
        default=0.0,
    )

    return {
        "source":         query.source,
        "target":         query.target,
        "found":          True,
        "strategy":       query.strategy,
        "hop_count":      hop_count,
        "total_value_btc": round(total_btc, 8),
        "risk_score":     round(max_risk, 1),
        "path":           [
            {
                "id":         n.get("id", ""),
                "type":       n.get("type", "unknown"),
                "risk_score": round(float(n.get("risk_score") or 0.0), 1),
                "flagged":    bool(n.get("flagged", False)),
            }
            for n in path_nodes
        ],
        "path_relationships": [
            {
                "type":       r.get("type", ""),
                "amount_btc": round(float(r.get("amount") or 0.0), 8),
            }
            for r in path_rels
        ],
        "evidence": [],
    }

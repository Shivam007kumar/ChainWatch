"""
services/investigation/wallet.py
──────────────────────────────────
Business logic for wallet investigation endpoints.

Layered architecture:
  api/investigations.py  → (HTTP routing, param validation)
        ↓
  services/investigation/wallet.py  → (business logic, response assembly)
        ↓
  db/queries/wallet.py   → (Cypher, returns raw Neo4j records)
        ↓
  models/responses/wallet.py (Pydantic contracts)

Semantic responses only — no hex color values, no UI decisions.
The frontend maps risk_level → its own visual tokens.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from config import settings
from db.neo4j_driver import run_query
from db.queries import (
    get_wallet_summary,
    get_wallet_graph_fallback,
    get_wallet_timeline,
)

logger = logging.getLogger("chainwatch.investigation.wallet")


# ── Wallet summary ─────────────────────────────────────────────────────────────

def get_summary(address: str, dataset_id: Optional[str] = None) -> dict:
    """
    Full wallet summary for GET /investigations/wallet/{address}.
    Returns entity info, statistics, risk, SHAP, evidence, and observed IPs.
    Falls back to a minimal response if Neo4j is unavailable.
    """
    try:
        results = run_query(*get_wallet_summary(address, dataset_id))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for wallet summary {address}: {exc}")
        return _fallback_summary(address)

    if not results or results[0].get("w") is None:
        return {"error": "not_found", "address": address}

    row = results[0]
    w   = row["w"]   # Neo4j node properties dict

    # Parse stored JSON fields
    shap_attributions: list = []
    risk_factors:      list = w.get("risk_factors", []) or []

    # Pull SHAP from Alert node if it was persisted there
    try:
        shap_attributions = json.loads(
            _get_alert_shap(address, dataset_id) or "[]"
        )
    except Exception:
        pass

    # Observed IPs — from the broadcast_ips collected in the Cypher
    broadcast_ips = row.get("broadcast_ips", []) or []
    observed_ips  = [
        {
            "ip":           _prop(ip, "address"),
            "state":        _prop(ip, "state", "Unknown"),
            "asn":          _prop(ip, "asn", "N/A"),
            "organization": _prop(ip, "org", "N/A"),
        }
        for ip in broadcast_ips
        if ip
    ]

    risk_score = float(w.get("risk_score") or 0.0)

    return {
        "entity": {
            "type":       "wallet",
            "address":    address,
            "risk_level": _risk_level(risk_score),
            "flagged":    bool(w.get("flagged", False)),
            "cluster":    w.get("cluster_name", ""),
            "state":      w.get("state", "Unknown"),
            "first_seen": w.get("first_seen"),
        },
        "risk": {
            "score":                risk_score,
            "anomaly_score":        w.get("anomaly_score"),
            "factors":              risk_factors,
            "propagation_distance": w.get("propagation_distance", 0),
        },
        "statistics": {
            "transaction_count": int(row.get("tx_count") or 0),
            "total_fees_btc":    round(float(sum(
                f for f in (row.get("fees") or []) if f is not None
            )), 8),
            "unique_ips":        len(set(
                _prop(ip, "address") for ip in broadcast_ips if ip
            )),
        },
        "shap":           shap_attributions,
        "evidence":       [],    # populated by evidence aggregator in pipeline
        "correlated_txids": list(row.get("correlated_txids") or []),
        "observed_ips":   observed_ips,
    }


# ── Wallet graph ───────────────────────────────────────────────────────────────

def get_graph(
    address: str,
    hops: int,
    direction: str = "both",
    dataset_id: Optional[str] = None,
) -> dict:
    """
    Semantic neighborhood graph for GET /investigations/wallet/{address}/graph.

    Returns nodes with semantic risk state (not colors), edges with type and
    risk metadata. Frontend maps risk_level → its own visual tokens.
    """
    hops = min(max(hops, 1), settings.max_investigation_hops)

    try:
        results = run_query(*get_wallet_graph_fallback(
            address, hops, settings.max_graph_nodes
        ))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for wallet graph {address}: {exc}")
        return _empty_graph(address, hops)

    nodes_map: dict[str, dict] = {}
    edges_map: dict[str, dict] = {}

    for row in results:
        raw_nodes = row.get("nodes") or []
        raw_rels  = row.get("rels") or []

        # ── Nodes — may be Neo4j node objects or dicts ────────────────────────
        for n in raw_nodes:
            if n is None:
                continue
            if isinstance(n, dict):
                ntype = "transaction" if "txid" in n else "wallet" if "address" in n else "unknown"
            else:
                labels = list(n.labels) if hasattr(n, "labels") else []
                ntype  = labels[0].lower() if labels else "unknown"
            nid = _node_id(n, ntype)
            if nid not in nodes_map:
                nodes_map[nid] = _build_node(n, ntype, nid)

        # ── Edges — the fallback query now returns clean dicts: ───────────────
        #   { source: "wallet:...", target: "tx:...", type: "SENT", amount: 50.0 }
        # No Neo4j objects in source/target — both are already prefixed id strings.
        for r in raw_rels:
            if r is None:
                continue

            if isinstance(r, dict):
                # Clean dict from the updated fallback Cypher query
                start  = str(r.get("source", ""))
                end    = str(r.get("target", ""))
                rtype  = r.get("type", "RELATED")
                amount = float(r.get("amount") or 0.0)
                eid    = f"{start}->{rtype}->{end}"
            else:
                # Fallback for raw Neo4j Relationship objects (APOC path)
                eid    = str(r.id) if hasattr(r, "id") else f"rel_{len(edges_map)}"
                rtype  = r.type if hasattr(r, "type") else "RELATED"
                start  = _node_id_from_element(r.start_node) if hasattr(r, "start_node") else ""
                end    = _node_id_from_element(r.end_node)   if hasattr(r, "end_node")   else ""
                amount = float(_prop(r, "amount", 0.0) or 0.0)

            if eid not in edges_map:
                risk_path = (
                    nodes_map.get(start, {}).get("risk", {}).get("level") in ("high", "critical") or
                    nodes_map.get(end,   {}).get("risk", {}).get("level") in ("high", "critical")
                )
                edges_map[eid] = {
                    "id":         eid,
                    "source":     start,
                    "target":     end,
                    "type":       str(rtype),
                    "amount_btc": round(amount, 8),
                    "risk":       {"is_risk_path": risk_path},
                }

    node_list = list(nodes_map.values())[:settings.max_graph_nodes]
    edge_ids  = {n["id"] for n in node_list}
    edge_list = [
        e for e in edges_map.values()
        if e["source"] in edge_ids and e["target"] in edge_ids
    ][:settings.max_graph_edges]

    truncated = (
        len(nodes_map) > settings.max_graph_nodes or
        len(edges_map) > settings.max_graph_edges
    )

    return {
        "nodes": node_list,
        "edges": edge_list,
        "meta": {
            "center":     f"wallet:{address}",
            "hops":       hops,
            "direction":  direction,
            "node_count": len(node_list),
            "edge_count": len(edge_list),
            "truncated":  truncated,
        },
    }


# ── Wallet timeline ────────────────────────────────────────────────────────────

def get_timeline(
    address: str,
    dataset_id: Optional[str] = None,
    limit: int = 100,
) -> dict:
    """
    Chronological events for GET /investigations/wallet/{address}/timeline.
    Returns outbound/inbound transactions in timestamp order.
    """
    try:
        results = run_query(*get_wallet_timeline(address, dataset_id, limit))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for wallet timeline {address}: {exc}")
        return {"address": address, "events": []}

    raw_events = []
    for row in results:
        raw_events.extend(row.get("events") or [])

    # Sort by timestamp — filter out null-timestamp entries
    valid = [e for e in raw_events if e and e.get("txid") and e.get("timestamp")]
    valid.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=False)

    events = []
    for e in valid[:limit]:
        events.append({
            "timestamp":    str(e.get("timestamp", "")),
            "type":         "transaction",
            "direction":    e.get("type", "outbound").lower(),
            "txid":         e.get("txid", ""),
            "amount_btc":   round(float(e.get("amount") or 0.0), 8),
            "fee_btc":      round(float(e.get("fee") or 0.0), 8),
        })

    return {"address": address, "events": events}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _risk_level(score: float) -> str:
    if score >= 90: return "critical"
    if score >= 70: return "high"
    if score >= 50: return "medium"
    return "low"


def _prop(node, key: str, default=None):
    """Safe property access from a Neo4j node or dict."""
    if node is None:
        return default
    if hasattr(node, "__getitem__"):
        try:
            return node[key] if node[key] is not None else default
        except (KeyError, TypeError):
            return default
    return default


def _node_id(node, ntype: str) -> str:
    if ntype == "wallet":
        return f"wallet:{_prop(node, 'address', str(id(node)))}"

    if ntype == "transaction":
        return f"tx:{_prop(node, 'txid', str(id(node)))}"

    if ntype == "ip":
        return f"ip:{_prop(node, 'address', str(id(node)))}"

    return f"entity:{id(node)}"


def _node_id_from_element(el) -> str:
    if el is None:
        return ""
    labels = list(el.labels) if hasattr(el, "labels") else []
    ntype  = labels[0].lower() if labels else "unknown"
    return _node_id(el, ntype)


def _build_node(n, ntype: str, nid: str) -> dict:
    risk_score = float(_prop(n, "risk_score") or 0.0)
    return {
        "id":    nid,
        "type":  ntype,
        "label": (
            str(_prop(n, "address") or _prop(n, "txid") or nid)[:16]
        ),
        "risk": {
            "score":   risk_score,
            "level":   _risk_level(risk_score),
            "flagged": bool(_prop(n, "flagged", False)),
        },
    }


def _empty_graph(address: str, hops: int) -> dict:
    return {
        "nodes": [], "edges": [],
        "meta": {
            "center": f"wallet:{address}", "hops": hops, "direction": "both",
            "node_count": 0, "edge_count": 0, "truncated": False,
        },
    }


def _fallback_summary(address: str) -> dict:
    return {
        "entity":     {"type": "wallet", "address": address, "risk_level": "unknown", "flagged": False},
        "risk":       {"score": 0.0, "factors": [], "propagation_distance": 0},
        "statistics": {"transaction_count": 0, "total_fees_btc": 0.0, "unique_ips": 0},
        "shap":       [],
        "evidence":   [],
        "correlated_txids": [],
        "observed_ips":     [],
        "_note": "Neo4j unavailable — data may be stale.",
    }


def _get_alert_shap(address: str, dataset_id: Optional[str]) -> Optional[str]:
    """Fetch shap_json from the most recent Alert for this wallet."""
    try:
        q = """
        MATCH (a:Alert {entity_id: $address})
        WHERE $dataset_id IS NULL OR a.dataset_id = $dataset_id
        RETURN a.shap_json AS shap_json
        ORDER BY a.created_at DESC
        LIMIT 1
        """
        res = run_query(q, {"address": address, "dataset_id": dataset_id})
        return res[0]["shap_json"] if res else None
    except Exception:
        return None

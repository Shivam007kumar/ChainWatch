"""
api/investigations.py
──────────────────────
HTTP routing for investigation endpoints.
This file: param validation + service delegation only — no Cypher, no business logic.

Endpoints (all read-only, no API key required):
  GET /api/v1/investigations/wallet/{address}
  GET /api/v1/investigations/wallet/{address}/graph
  GET /api/v1/investigations/wallet/{address}/timeline
  GET /api/v1/investigations/transaction/{txid}
  GET /api/v1/investigations/ip/{ip}
  GET /api/v1/investigations/path
"""
from __future__ import annotations

import ipaddress
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config import settings

router = APIRouter(prefix="/investigations", tags=["investigations"])

# ── Input validation patterns ──────────────────────────────────────────────────
_WALLET_RE   = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')
_TXID_RE     = re.compile(r'^[a-zA-Z0-9_\-]{1,80}$')
_DATASET_RE  = re.compile(r'^[a-zA-Z0-9]{1,32}$')


def _validate_wallet(address: str) -> str:
    if not _WALLET_RE.match(address):
        raise HTTPException(400, "Invalid wallet address format.")
    return address


def _validate_txid(txid: str) -> str:
    if not _TXID_RE.match(txid):
        raise HTTPException(400, "Invalid transaction ID format.")
    return txid


def _validate_ip(ip: str) -> str:
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        raise HTTPException(400, f"Invalid IP address: {ip!r}")


def _validate_hops(hops: int) -> int:
    if not (1 <= hops <= settings.max_investigation_hops):
        raise HTTPException(400, f"hops must be between 1 and {settings.max_investigation_hops}.")
    return hops


def _validate_dataset(dataset_id: Optional[str]) -> Optional[str]:
    if dataset_id is None:
        return None
    if not _DATASET_RE.match(dataset_id):
        raise HTTPException(400, "Invalid dataset_id format.")
    return dataset_id


# ── Wallet endpoints ───────────────────────────────────────────────────────────

@router.get("/wallet/{address}")
def wallet_summary(
    address:    str,
    dataset_id: Optional[str] = Query(default=None, description="Scope to a specific ingest dataset"),
):
    """
    Full wallet investigation summary.
    Returns entity info, risk, statistics, SHAP attributions, evidence, and observed IPs.
    """
    address    = _validate_wallet(address)
    dataset_id = _validate_dataset(dataset_id)

    from services.investigation.wallet import get_summary
    result = get_summary(address, dataset_id)
    if result.get("error") == "not_found":
        raise HTTPException(404, f"Wallet {address!r} not found.")
    return result


@router.get("/wallet/{address}/graph")
def wallet_graph(
    address:    str,
    hops:       int           = Query(default=2, ge=1, le=5),
    direction:  str           = Query(default="both", pattern="^(forward|backward|both)$"),
    dataset_id: Optional[str] = Query(default=None),
):
    """
    Semantic neighborhood graph — nodes carry risk_level, edges carry type and risk metadata.
    No color values in response; frontend maps semantic state to visual tokens.
    """
    address    = _validate_wallet(address)
    hops       = _validate_hops(hops)
    dataset_id = _validate_dataset(dataset_id)

    from services.investigation.wallet import get_graph
    return get_graph(address, hops, direction, dataset_id)


@router.get("/wallet/{address}/timeline")
def wallet_timeline(
    address:    str,
    dataset_id: Optional[str] = Query(default=None),
    limit:      int           = Query(default=100, ge=1, le=500),
):
    """
    Chronological transaction and IP observation events for a wallet.
    """
    address    = _validate_wallet(address)
    dataset_id = _validate_dataset(dataset_id)
    limit      = min(limit, settings.max_page_size * 5)  # allow up to 500 for timelines

    from services.investigation.wallet import get_timeline
    return get_timeline(address, dataset_id, limit)


# ── Transaction endpoint ───────────────────────────────────────────────────────

@router.get("/transaction/{txid}")
def transaction_detail(
    txid:       str,
    dataset_id: Optional[str] = Query(default=None),
):
    """
    Full transaction detail — inputs, outputs (with risk scores), broadcast IPs
    with confidence scores, and destination IP observations.
    Fee ratio and volumes are computed server-side.
    """
    txid       = _validate_txid(txid)
    dataset_id = _validate_dataset(dataset_id)

    from services.investigation.transaction import get_detail
    result = get_detail(txid, dataset_id)
    if result.get("error") == "not_found":
        raise HTTPException(404, f"Transaction {txid!r} not found.")
    return result


# ── IP endpoint ────────────────────────────────────────────────────────────────

@router.get("/ip/{ip_address:path}")
def ip_detail(
    ip_address: str,
    dataset_id: Optional[str] = Query(default=None),
):
    """
    IP investigation — GeoIP with provenance, ASN, broadcast observation history,
    and linked wallets / transactions.
    """
    ip_address = _validate_ip(ip_address)
    dataset_id = _validate_dataset(dataset_id)

    from services.investigation.ip import get_detail
    return get_detail(ip_address, dataset_id)


# ── Path endpoint ──────────────────────────────────────────────────────────────

@router.get("/path")
def path_trace(
    source:    str           = Query(..., description="Source wallet address"),
    target:    str           = Query(..., description="Target wallet address"),
    max_hops:  int           = Query(default=5, ge=1, le=8),
    direction: str           = Query(default="both", pattern="^(forward|backward|both)$"),
    strategy:  str           = Query(default="shortest", pattern="^(shortest|risk|all)$"),
):
    """
    Trace path between two wallet addresses.
    strategy=shortest is implemented; risk/all return 501 (reserved for future).
    """
    source    = _validate_wallet(source)
    target    = _validate_wallet(target)
    max_hops  = min(max_hops, settings.max_investigation_hops)

    from services.investigation.path import PathQuery, trace
    result = trace(PathQuery(
        source=source, target=target,
        max_hops=max_hops, direction=direction, strategy=strategy,
    ))

    if result.get("error") == "not_implemented":
        raise HTTPException(501, result["message"])
    return result

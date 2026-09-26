"""
ingestion/validator.py
──────────────────────
Validates and coerces a parsed row into a CanonicalTransaction.

Returns (valid, rejected) tuple — never raises.
Every rejection produces a RejectedRow with a human-readable reason.

Validated constraints:
  - txid:               non-empty string
  - timestamp:          parseable as datetime (ISO or unix)
  - src_ip / dst_ip:    valid IPv4/IPv6 or "Unknown" (Unknown is allowed)
  - src_port/dst_port:  0 ≤ port ≤ 65535
  - amounts:            all values ≥ 0, no NaN
  - fee:                ≥ 0
  - address lists:      len(addresses) == len(amounts) — mismatch is silent corruption
  - list fields:        must be non-empty lists after parsing
"""
from __future__ import annotations

import ipaddress
import math
from datetime import datetime
from typing import Any

from models.domain.transaction import CanonicalTransaction, GeoInfo, RejectedRow


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_valid_ip(ip: str) -> bool:
    """Returns True for valid IPv4/IPv6, or for the sentinel 'Unknown'."""
    if not ip or ip == "Unknown":
        return True   # Unknown is acceptable — enrichment will skip it
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _is_valid_port(port: Any) -> bool:
    try:
        p = int(port)
        return 0 <= p <= 65535
    except (ValueError, TypeError):
        return False


def _is_valid_amount(v: Any) -> bool:
    try:
        f = float(v)
        return not math.isnan(f) and f >= 0
    except (ValueError, TypeError):
        return False


def _parse_timestamp(raw: Any) -> datetime | None:
    """
    Tries ISO-format string first, then unix timestamp (int/float).
    Returns None on failure.
    """
    if isinstance(raw, (int, float)):
        try:
            return datetime.utcfromtimestamp(float(raw))
        except (OSError, OverflowError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


# ── Main entry point ───────────────────────────────────────────────────────────

def validate_rows(
    raw_rows: list[dict],
    dataset_id: str = "",
) -> tuple[list[CanonicalTransaction], list[RejectedRow]]:
    """
    Validate a list of parsed row dicts (as produced by ingestion/parser.py).

    Parameters
    ----------
    raw_rows   : list of dicts with keys matching the canonical schema
    dataset_id : propagated to every CanonicalTransaction

    Returns
    -------
    (valid, rejected)
      valid    — list[CanonicalTransaction], ready for enrichment
      rejected — list[RejectedRow], one per rejected row with reason
    """
    valid:    list[CanonicalTransaction] = []
    rejected: list[RejectedRow]         = []

    for idx, row in enumerate(raw_rows):
        txid = str(row.get("txid", "")).strip()

        # Build a snippet for debugging
        snippet = str(row)[:120]

        def reject(reason: str) -> None:
            rejected.append(RejectedRow(
                row_index=idx, txid=txid or f"row_{idx}",
                reason=reason, raw_snippet=snippet,
            ))

        # ── txid ──────────────────────────────────────────────────────────────
        if not txid:
            reject("txid is empty")
            continue

        # ── timestamp ─────────────────────────────────────────────────────────
        ts = _parse_timestamp(row.get("timestamp"))
        if ts is None:
            reject(f"unparseable timestamp: {str(row.get('timestamp', ''))[:40]!r}")
            continue

        # ── IP addresses ──────────────────────────────────────────────────────
        src_ip = str(row.get("src_ip", "Unknown")).strip()
        dst_ip = str(row.get("dst_ip", "Unknown")).strip()

        if not _is_valid_ip(src_ip):
            reject(f"invalid src_ip: {src_ip!r}")
            continue
        if not _is_valid_ip(dst_ip):
            reject(f"invalid dst_ip: {dst_ip!r}")
            continue

        # ── Ports ─────────────────────────────────────────────────────────────
        src_port_raw = row.get("src_port", 0)
        dst_port_raw = row.get("dst_port", 8333)

        if not _is_valid_port(src_port_raw):
            reject(f"invalid src_port: {src_port_raw!r}")
            continue
        if not _is_valid_port(dst_port_raw):
            reject(f"invalid dst_port: {dst_port_raw!r}")
            continue

        src_port = int(src_port_raw)
        dst_port = int(dst_port_raw)

        # ── Addresses + amounts ───────────────────────────────────────────────
        input_addresses  = row.get("input_addresses",  [])
        output_addresses = row.get("output_addresses", [])
        input_amounts    = row.get("input_amounts",    [])
        output_amounts   = row.get("output_amounts",   [])

        if not isinstance(input_addresses, list) or len(input_addresses) == 0:
            reject("input_addresses must be a non-empty list")
            continue
        if not isinstance(output_addresses, list) or len(output_addresses) == 0:
            reject("output_addresses must be a non-empty list")
            continue
        if not isinstance(input_amounts, list) or len(input_amounts) == 0:
            reject("input_amounts must be a non-empty list")
            continue
        if not isinstance(output_amounts, list) or len(output_amounts) == 0:
            reject("output_amounts must be a non-empty list")
            continue

        # Address/amount length parity — mismatch is silent data corruption
        if len(input_addresses) != len(input_amounts):
            reject(
                f"input_addresses ({len(input_addresses)}) and "
                f"input_amounts ({len(input_amounts)}) length mismatch"
            )
            continue
        if len(output_addresses) != len(output_amounts):
            reject(
                f"output_addresses ({len(output_addresses)}) and "
                f"output_amounts ({len(output_amounts)}) length mismatch"
            )
            continue

        # Amount validity
        bad_inputs  = [v for v in input_amounts  if not _is_valid_amount(v)]
        bad_outputs = [v for v in output_amounts if not _is_valid_amount(v)]
        if bad_inputs:
            reject(f"invalid input_amounts: {bad_inputs[:3]}")
            continue
        if bad_outputs:
            reject(f"invalid output_amounts: {bad_outputs[:3]}")
            continue

        # ── Fee ───────────────────────────────────────────────────────────────
        fee_raw = row.get("fee", 0.0)
        if not _is_valid_amount(fee_raw):
            reject(f"invalid fee: {fee_raw!r}")
            continue
        fee = float(fee_raw)

        # ── Script type ───────────────────────────────────────────────────────
        script_type = str(row.get("script_type", "P2PKH")).strip() or "P2PKH"

        # ── Build CanonicalTransaction ────────────────────────────────────────
        tx = CanonicalTransaction(
            txid             = txid,
            timestamp        = ts,
            dataset_id       = dataset_id,
            input_addresses  = [str(a) for a in input_addresses],
            output_addresses = [str(a) for a in output_addresses],
            input_amounts    = [float(a) for a in input_amounts],
            output_amounts   = [float(a) for a in output_amounts],
            fee              = fee,
            script_type      = script_type,
            src_ip           = src_ip,
            dst_ip           = dst_ip,
            src_port         = src_port,
            dst_port         = dst_port,
        )
        tx.compute_balance_delta()
        valid.append(tx)

    return valid, rejected

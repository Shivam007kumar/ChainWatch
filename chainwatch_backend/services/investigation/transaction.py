"""
services/investigation/transaction.py
────────────────────────────────────────
Business logic for GET /investigations/transaction/{txid}.
"""
from __future__ import annotations

import logging
from typing import Optional

from db.neo4j_driver import run_query
from db.queries import get_transaction_detail

logger = logging.getLogger("chainwatch.investigation.transaction")


def get_detail(txid: str, dataset_id: Optional[str] = None) -> dict:
    """
    Full transaction detail including inputs, outputs, broadcast observations,
    and destination IP observations. All volumes computed server-side.
    """
    try:
        results = run_query(*get_transaction_detail(txid, dataset_id))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for tx {txid}: {exc}")
        return {"error": "neo4j_unavailable", "txid": txid}

    if not results or results[0].get("t") is None:
        return {"error": "not_found", "txid": txid}

    row = results[0]
    t   = row["t"]

    inputs   = [i for i in (row.get("inputs")   or []) if i and i.get("address")]
    outputs  = [o for o in (row.get("outputs")  or []) if o and o.get("address")]
    bcast    = [b for b in (row.get("broadcasts") or []) if b and b.get("ip")]
    dst      = [d for d in (row.get("destinations") or []) if d and d.get("ip")]

    input_vol  = sum(float(i.get("amount") or 0.0) for i in inputs)
    output_vol = sum(float(o.get("amount") or 0.0) for o in outputs)
    fee        = float(t.get("fee") or 0.0)
    fee_ratio  = round(fee / input_vol, 8) if input_vol > 0 else 0.0

    return {
        "transaction": {
            "txid":             txid,
            "timestamp":        str(t.get("timestamp") or ""),
            "fee_btc":          round(fee, 8),
            "fee_ratio":        fee_ratio,
            "script_type":      t.get("script_type", "P2PKH"),
            "input_count":      len(inputs),
            "output_count":     len(outputs),
            "input_volume_btc": round(input_vol, 8),
            "output_volume_btc": round(output_vol, 8),
            "balance_delta":    round(input_vol - output_vol - fee, 8),
        },
        "inputs":  [
            {
                "address":    i["address"],
                "amount_btc": round(float(i.get("amount") or 0.0), 8),
                "risk_score": float(i.get("risk_score") or 0.0),
                "flagged":    bool(i.get("flagged", False)),
            } for i in inputs
        ],
        "outputs": [
            {
                "address":    o["address"],
                "amount_btc": round(float(o.get("amount") or 0.0), 8),
                "risk_score": float(o.get("risk_score") or 0.0),
                "flagged":    bool(o.get("flagged", False)),
            } for o in outputs
        ],
        "broadcasts": [
            {
                "ip":         b["ip"],
                "state":      b.get("state", "Unknown"),
                "asn":        b.get("asn", "N/A"),
                "org":        b.get("org", "N/A"),
                "confidence": round(float(b.get("confidence") or 1.0), 4),
            } for b in sorted(bcast, key=lambda x: float(x.get("confidence") or 0), reverse=True)
        ],
        "destinations": [
            {
                "ip":       d["ip"],
                "state":    d.get("state", "Unknown"),
                "asn":      d.get("asn", "N/A"),
                "src_port": int(d.get("src_port") or 0),
                "dst_port": int(d.get("dst_port") or 8333),
            } for d in dst
        ],
    }

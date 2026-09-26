"""
db/queries/search.py
──────────────────────
Full-text / prefix search across Wallet, Transaction, IP.

Uses STARTS WITH on the unique indexed properties — hits the constraint index
so no full graph scan is required.
"""
from __future__ import annotations


def search_entities(query: str, types: list[str], limit: int = 20):
    """
    Search across Wallet.address, Transaction.txid, IP.address using prefix match.

    Parameters
    ----------
    query  : search string (minimum 4 characters enforced by the caller)
    types  : subset of ["wallet", "transaction", "ip"]
    limit  : max results per type (total results ≤ limit * len(types))
    """
    parts = []
    params: dict = {"q": query, "limit": limit}

    if "wallet" in types:
        parts.append(
            """
            MATCH (w:Wallet)
            WHERE w.address STARTS WITH $q
               OR w.address CONTAINS $q
            RETURN 'wallet'       AS type,
                   w.address      AS id,
                   w.address      AS label,
                   w.risk_score   AS risk_score,
                   w.flagged      AS flagged,
                   w.state        AS state
            ORDER BY w.risk_score DESC
            LIMIT $limit
            """
        )

    if "transaction" in types:
        parts.append(
            """
            MATCH (t:Transaction)
            WHERE t.txid STARTS WITH $q
               OR t.txid CONTAINS $q
            RETURN 'transaction'  AS type,
                   t.txid         AS id,
                   t.txid         AS label,
                   0.0            AS risk_score,
                   false          AS flagged,
                   ''             AS state
            LIMIT $limit
            """
        )

    if "ip" in types:
        parts.append(
            """
            MATCH (ip:IP)
            WHERE ip.address STARTS WITH $q
               OR ip.address CONTAINS $q
            RETURN 'ip'           AS type,
                   ip.address     AS id,
                   ip.address     AS label,
                   0.0            AS risk_score,
                   false          AS flagged,
                   ip.state       AS state
            LIMIT $limit
            """
        )

    if not parts:
        # No valid types requested — return nothing
        return "RETURN null AS type, null AS id, null AS label, 0.0 AS risk_score, false AS flagged, null AS state LIMIT 0", params

    cypher = "\nUNION ALL\n".join(parts)
    return cypher, params

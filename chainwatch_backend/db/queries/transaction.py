"""
db/queries/transaction.py
──────────────────────────
Cypher queries for :Transaction nodes.
"""
from __future__ import annotations


# ── Transaction MERGE writes ───────────────────────────────────────────────────

def merge_transaction(txid: str, timestamp: str, fee: float = None):
    return (
        """
        MERGE (t:Transaction {txid: $txid})
        ON CREATE SET t.timestamp = $timestamp, t.fee = $fee
        RETURN t
        """,
        {"txid": txid, "timestamp": str(timestamp), "fee": fee},
    )


def batch_merge_transactions(txs: list[dict]):
    return (
        """
        UNWIND $txs AS row
        MERGE (t:Transaction {txid: row.txid})
        ON CREATE SET t.timestamp   = row.timestamp,
                      t.fee         = row.fee,
                      t.script_type = coalesce(row.script_type, 'P2PKH')
        ON MATCH SET  t.fee         = coalesce(row.fee, t.fee)
        """,
        {"txs": txs},
    )


# ── Investigation read queries ─────────────────────────────────────────────────

def get_transaction_detail(txid: str, dataset_id: str | None = None):
    """
    Full transaction detail for GET /investigations/transaction/{txid}.
    Returns tx properties, input wallets, output wallets, and broadcast IPs.
    """
    return (
        """
        MATCH (t:Transaction {txid: $txid})
        OPTIONAL MATCH (w_in:Wallet)-[s:SENT]->(t)
        OPTIONAL MATCH (t)-[r_out:RECEIVED_BY]->(w_out:Wallet)
        OPTIONAL MATCH (ip_src:IP)-[b:BROADCAST]->(t)
        OPTIONAL MATCH (t)-[od:OBSERVED_DESTINATION]->(ip_dst:IP)
        RETURN t,
               collect(DISTINCT {address: w_in.address,  amount: s.amount,
                                  risk_score: w_in.risk_score, flagged: w_in.flagged})
                   AS inputs,
               collect(DISTINCT {address: w_out.address, amount: r_out.amount,
                                  risk_score: w_out.risk_score, flagged: w_out.flagged})
                   AS outputs,
               collect(DISTINCT {ip:         ip_src.address,
                                  state:      ip_src.state,
                                  asn:        ip_src.asn,
                                  org:        ip_src.org,
                                  confidence: b.confidence})
                   AS broadcasts,
               collect(DISTINCT {ip:       ip_dst.address,
                                  state:   ip_dst.state,
                                  asn:     ip_dst.asn,
                                  src_port: od.src_port,
                                  dst_port: od.dst_port})
                   AS destinations
        """,
        {"txid": txid, "dataset_id": dataset_id},
    )

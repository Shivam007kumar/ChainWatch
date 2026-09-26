"""
db/queries/common.py
─────────────────────
Shared / cross-cutting Cypher:
  - clear_all_data
  - Dataset node management
  - Dataset isolation relationship writes (B5)
"""


def clear_all_data():
    return "MATCH (n) DETACH DELETE n", {}


# ── Dataset node ───────────────────────────────────────────────────────────────

def merge_dataset(dataset_id: str, filename: str, record_count: int):
    return (
        """
        MERGE (d:Dataset {id: $dataset_id})
        ON CREATE SET
            d.filename    = $filename,
            d.records     = $record_count,
            d.ingested_at = datetime(),
            d.status      = 'completed'
        ON MATCH SET
            d.records  = $record_count,
            d.status   = 'completed'
        """,
        {"dataset_id": dataset_id, "filename": filename, "record_count": record_count},
    )


# ── Dataset isolation relationships (B5) ──────────────────────────────────────
# Each ingest links all entities back to their originating Dataset node.
# This allows /stats, /alerts, and /investigations to be scoped per dataset.

def batch_link_dataset_wallets(dataset_id: str, wallet_addresses: list[str]):
    """CONTAINS_WALLET: Dataset → Wallet (one per distinct address in this ingest)."""
    return (
        """
        UNWIND $addresses AS addr
        MATCH (d:Dataset {id: $dataset_id})
        MATCH (w:Wallet  {address: addr})
        MERGE (d)-[:CONTAINS_WALLET]->(w)
        """,
        {"dataset_id": dataset_id, "addresses": wallet_addresses},
    )


def batch_link_dataset_txs(dataset_id: str, txids: list[str]):
    """CONTAINS_TX: Dataset → Transaction."""
    return (
        """
        UNWIND $txids AS txid
        MATCH (d:Dataset      {id:   $dataset_id})
        MATCH (t:Transaction  {txid: txid})
        MERGE (d)-[:CONTAINS_TX]->(t)
        """,
        {"dataset_id": dataset_id, "txids": txids},
    )


def batch_link_dataset_ips(dataset_id: str, ip_addresses: list[str]):
    """OBSERVED_IP: Dataset → IP."""
    return (
        """
        UNWIND $ips AS ip
        MATCH (d:Dataset {id:      $dataset_id})
        MATCH (n:IP      {address: ip})
        MERGE (d)-[:OBSERVED_IP]->(n)
        """,
        {"dataset_id": dataset_id, "ips": ip_addresses},
    )

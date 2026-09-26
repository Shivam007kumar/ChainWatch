"""
db/queries/ip.py
──────────────────
Cypher queries for :IP nodes and their relationships:
  - BROADCAST (src IP → Transaction)
  - OBSERVED_DESTINATION (Transaction → dst IP)  [D2 — new]
  - Investigation read queries for GET /investigations/ip/{ip}
"""
from __future__ import annotations


# ── IP MERGE writes ────────────────────────────────────────────────────────────

def merge_ip(address: str, asn: str = None, org: str = None,
             state: str = None, lat: float = None, lon: float = None):
    return (
        """
        MERGE (ip:IP {address: $address})
        ON CREATE SET ip.asn   = $asn,   ip.org   = $org,
                      ip.state = $state, ip.lat   = $lat, ip.lon = $lon
        ON MATCH SET  ip.asn   = coalesce($asn,   ip.asn),
                      ip.org   = coalesce($org,   ip.org),
                      ip.state = coalesce($state, ip.state)
        RETURN ip
        """,
        {"address": address, "asn": asn, "org": org,
         "state": state, "lat": lat, "lon": lon},
    )


def batch_merge_ips(ips: list[dict]):
    return (
        """
        UNWIND $ips AS row
        MERGE (ip:IP {address: row.address})
        ON CREATE SET ip.asn   = row.asn,   ip.org   = row.org,
                      ip.state = row.state, ip.lat   = row.lat, ip.lon = row.lon
        ON MATCH SET  ip.asn   = coalesce(row.asn,   ip.asn),
                      ip.org   = coalesce(row.org,   ip.org),
                      ip.state = coalesce(row.state, ip.state)
        """,
        {"ips": ips},
    )


# ── BROADCAST relationship (src_ip → Transaction) ─────────────────────────────

def merge_broadcast_relationship(ip_address: str, txid: str, confidence: float):
    return (
        """
        MATCH (ip:IP         {address: $ip_address})
        MATCH (t:Transaction {txid:    $txid})
        MERGE (ip)-[r:BROADCAST]->(t)
        ON CREATE SET r.confidence = $confidence
        ON MATCH SET  r.confidence = CASE
            WHEN $confidence > r.confidence THEN $confidence
            ELSE r.confidence END
        RETURN r.confidence AS confidence
        """,
        {"ip_address": ip_address, "txid": txid, "confidence": float(confidence)},
    )


def batch_merge_broadcast_relationships(broadcasts: list[dict]):
    return (
        """
        UNWIND $broadcasts AS row
        MATCH (ip:IP         {address: row.ip_address})
        MATCH (t:Transaction {txid:    row.txid})
        MERGE (ip)-[r:BROADCAST]->(t)
        ON CREATE SET r.confidence = row.confidence
        ON MATCH SET  r.confidence = CASE
            WHEN row.confidence > r.confidence THEN row.confidence
            ELSE r.confidence END
        """,
        {"broadcasts": broadcasts},
    )


# ── OBSERVED_DESTINATION relationship (Transaction → dst_ip) [D2] ────────────

def merge_observed_destination(txid: str, dst_ip: str,
                                src_port: int, dst_port: int, timestamp: str):
    """
    Records that a transaction was observed to communicate with dst_ip.
    Named OBSERVED_DESTINATION rather than RECEIVED_BY_IP — the system records
    network-layer observations, not proven physical receipt.
    """
    return (
        """
        MATCH (t:Transaction {txid:    $txid})
        MATCH (dst:IP        {address: $dst_ip})
        MERGE (t)-[r:OBSERVED_DESTINATION]->(dst)
        ON CREATE SET r.src_port    = $src_port,
                      r.dst_port    = $dst_port,
                      r.observed_at = $timestamp
        ON MATCH SET  r.src_port    = coalesce($src_port, r.src_port),
                      r.dst_port    = coalesce($dst_port, r.dst_port)
        """,
        {"txid": txid, "dst_ip": dst_ip, "src_port": src_port,
         "dst_port": dst_port, "timestamp": timestamp},
    )


def batch_merge_observed_destinations(records: list[dict]):
    """
    Batch OBSERVED_DESTINATION writes.
    Each record: {txid, dst_ip, dst_asn, dst_state, src_port, dst_port, timestamp}
    """
    return (
        """
        UNWIND $records AS row
        MERGE (dst:IP {address: row.dst_ip})
        ON CREATE SET dst.asn   = row.dst_asn,
                      dst.state = row.dst_state
        ON MATCH SET  dst.asn   = coalesce(row.dst_asn,   dst.asn),
                      dst.state = coalesce(row.dst_state, dst.state)
        WITH dst, row
        MATCH (t:Transaction {txid: row.txid})
        MERGE (t)-[r:OBSERVED_DESTINATION]->(dst)
        ON CREATE SET r.src_port    = row.src_port,
                      r.dst_port    = row.dst_port,
                      r.observed_at = row.timestamp
        ON MATCH SET  r.src_port    = coalesce(row.src_port, r.src_port),
                      r.dst_port    = coalesce(row.dst_port, r.dst_port)
        """,
        {"records": records},
    )


# ── Investigation read queries ─────────────────────────────────────────────────

def get_ip_detail(ip_address: str, dataset_id: str | None = None, limit: int = 100):
    """
    Full IP detail for GET /investigations/ip/{ip}.
    Returns geo/ASN, broadcast observations, and linked wallets/transactions.
    """
    return (
        """
        MATCH (ip:IP {address: $ip_address})
        OPTIONAL MATCH (ip)-[b:BROADCAST]->(t:Transaction)
        OPTIONAL MATCH (w:Wallet)-[:SENT]->(t)
        RETURN ip,
               collect(DISTINCT {
                   txid:        t.txid,
                   timestamp:   t.timestamp,
                   confidence:  b.confidence
               })[..100]  AS observations,
               collect(DISTINCT w.address)[..50] AS linked_wallets,
               collect(DISTINCT t.txid)[..50]     AS linked_txids
        """,
        {"ip_address": ip_address, "dataset_id": dataset_id},
    )

def merge_wallet(address: str, state: str = "Unknown"):
    return """
    MERGE (w:Wallet {address: $address})
    ON CREATE SET w.first_seen = timestamp(), w.state = $state, w.risk_score = 0.0, w.flagged = false
    ON MATCH SET w.state = CASE WHEN $state <> 'Unknown' THEN $state ELSE w.state END
    RETURN w
    """, {"address": address, "state": state}


def batch_merge_wallets(wallets: list[dict]):
    return """
    UNWIND $wallets AS row
    MERGE (w:Wallet {address: row.address})
    ON CREATE SET w.first_seen = timestamp(), w.state = row.state, w.risk_score = 0.0, w.flagged = false
    ON MATCH SET w.state = CASE WHEN row.state <> 'Unknown' THEN row.state ELSE w.state END
    """, {"wallets": wallets}


def merge_transaction(txid: str, timestamp: str, fee: float = None):
    return """
    MERGE (t:Transaction {txid: $txid})
    ON CREATE SET t.timestamp = $timestamp, t.fee = $fee
    RETURN t
    """, {"txid": txid, "timestamp": str(timestamp), "fee": fee}


def batch_merge_transactions(txs: list[dict]):
    return """
    UNWIND $txs AS row
    MERGE (t:Transaction {txid: row.txid})
    ON CREATE SET t.timestamp = row.timestamp, t.fee = row.fee
    """, {"txs": txs}


def merge_ip(address: str, asn: str = None, org: str = None, state: str = None, lat: float = None, lon: float = None):
    return """
    MERGE (ip:IP {address: $address})
    ON CREATE SET ip.asn = $asn, ip.org = $org, ip.state = $state, ip.lat = $lat, ip.lon = $lon
    ON MATCH SET ip.asn = coalesce($asn, ip.asn), ip.org = coalesce($org, ip.org), ip.state = coalesce($state, ip.state)
    RETURN ip
    """, {"address": address, "asn": asn, "org": org, "state": state, "lat": lat, "lon": lon}


def batch_merge_ips(ips: list[dict]):
    return """
    UNWIND $ips AS row
    MERGE (ip:IP {address: row.address})
    ON CREATE SET ip.asn = row.asn, ip.org = row.org, ip.state = row.state, ip.lat = row.lat, ip.lon = row.lon
    ON MATCH SET ip.asn = coalesce(row.asn, ip.asn), ip.org = coalesce(row.org, ip.org), ip.state = coalesce(row.state, ip.state)
    """, {"ips": ips}


def merge_sent_relationship(wallet_address: str, txid: str, amount: float):
    return """
    MATCH (w:Wallet {address: $wallet_address})
    MATCH (t:Transaction {txid: $txid})
    MERGE (w)-[r:SENT]->(t)
    ON CREATE SET r.amount = $amount
    RETURN r
    """, {"wallet_address": wallet_address, "txid": txid, "amount": float(amount)}


def batch_merge_sent_relationships(sent: list[dict]):
    return """
    UNWIND $sent AS row
    MATCH (w:Wallet {address: row.wallet_address})
    MATCH (t:Transaction {txid: row.txid})
    MERGE (w)-[r:SENT]->(t)
    ON CREATE SET r.amount = row.amount
    """, {"sent": sent}


def merge_received_relationship(txid: str, wallet_address: str, amount: float):
    return """
    MATCH (t:Transaction {txid: $txid})
    MATCH (w:Wallet {address: $wallet_address})
    MERGE (t)-[r:RECEIVED_BY]->(w)
    ON CREATE SET r.amount = $amount
    RETURN r
    """, {"txid": txid, "wallet_address": wallet_address, "amount": float(amount)}


def batch_merge_received_relationships(rec: list[dict]):
    return """
    UNWIND $rec AS row
    MATCH (t:Transaction {txid: row.txid})
    MATCH (w:Wallet {address: row.wallet_address})
    MERGE (t)-[r:RECEIVED_BY]->(w)
    ON CREATE SET r.amount = row.amount
    """, {"rec": rec}


def merge_broadcast_relationship(ip_address: str, txid: str, confidence: float):
    return """
    MATCH (ip:IP {address: $ip_address})
    MATCH (t:Transaction {txid: $txid})
    MERGE (ip)-[r:BROADCAST]->(t)
    ON CREATE SET r.confidence = $confidence
    ON MATCH SET r.confidence = CASE WHEN $confidence > r.confidence THEN $confidence ELSE r.confidence END
    RETURN r.confidence AS confidence
    """, {"ip_address": ip_address, "txid": txid, "confidence": float(confidence)}


def batch_merge_broadcast_relationships(broadcasts: list[dict]):
    return """
    UNWIND $broadcasts AS row
    MATCH (ip:IP {address: row.ip_address})
    MATCH (t:Transaction {txid: row.txid})
    MERGE (ip)-[r:BROADCAST]->(t)
    ON CREATE SET r.confidence = row.confidence
    ON MATCH SET r.confidence = CASE WHEN row.confidence > r.confidence THEN row.confidence ELSE r.confidence END
    """, {"broadcasts": broadcasts}


def merge_same_entity_relationship(address_a: str, address_b: str, reason: str = "CIOU"):
    a, b = sorted([address_a, address_b])
    return """
    MATCH (w1:Wallet {address: $a})
    MATCH (w2:Wallet {address: $b})
    MERGE (w1)-[r:SAME_ENTITY_AS]-(w2)
    ON CREATE SET r.reason = $reason
    RETURN r
    """, {"a": a, "b": b, "reason": reason}


def batch_merge_same_entity_relationships(ciou: list[dict]):
    return """
    UNWIND $ciou AS row
    MATCH (w1:Wallet {address: row.a})
    MATCH (w2:Wallet {address: row.b})
    MERGE (w1)-[r:SAME_ENTITY_AS]-(w2)
    ON CREATE SET r.reason = row.reason
    """, {"ciou": ciou}


def update_wallet_risk(address: str, risk_score: float, risk_factors: list = None, flagged: bool = False):
    return """
    MATCH (w:Wallet {address: $address})
    SET w.risk_score = $risk_score,
        w.risk_factors = $risk_factors,
        w.flagged = CASE WHEN $flagged THEN true ELSE w.flagged END
    RETURN w
    """, {"address": address, "risk_score": float(risk_score), "risk_factors": risk_factors or [], "flagged": flagged}


def batch_update_wallet_risks(risks: list[dict]):
    return """
    UNWIND $risks AS row
    MATCH (w:Wallet {address: row.address})
    SET w.risk_score = row.risk_score,
        w.risk_factors = row.risk_factors,
        w.flagged = CASE WHEN row.flagged THEN true ELSE w.flagged END
    """, {"risks": risks}


def get_wallet_neighborhood(address: str, hops: int = 2):
    return f"""
    MATCH path = (w:Wallet {{address: $address}})-[*1..{hops}]-(connected)
    RETURN path
    LIMIT 100
    """, {"address": address}


def get_full_graph_data():
    return """
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    """, {}


def clear_all_data():
    return "MATCH (n) DETACH DELETE n", {}

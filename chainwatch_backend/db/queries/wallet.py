"""
db/queries/wallet.py
──────────────────────
Cypher queries for :Wallet nodes and their relationships:
  - MERGE writes (ingestion)
  - Risk score updates
  - SENT / RECEIVED_BY edges
  - SAME_ENTITY_AS (CIOU) edges
  - Alert node writes (D1)
  - Investigation read queries (E1, E2, E3)

Design rule: every read query begins from (w:Wallet {address: $address})
which hits the wallet_address_unique constraint index — no full graph scans.
"""
from __future__ import annotations


# ── Wallet MERGE writes ────────────────────────────────────────────────────────

def merge_wallet(address: str, state: str = "Unknown"):
    return (
        """
        MERGE (w:Wallet {address: $address})
        ON CREATE SET w.first_seen = timestamp(), w.state = $state,
                      w.risk_score = 0.0, w.flagged = false
        ON MATCH SET  w.state = CASE WHEN $state <> 'Unknown' THEN $state ELSE w.state END
        RETURN w
        """,
        {"address": address, "state": state},
    )


def batch_merge_wallets(wallets: list[dict]):
    return (
        """
        UNWIND $wallets AS row
        MERGE (w:Wallet {address: row.address})
        ON CREATE SET w.first_seen = timestamp(), w.state = row.state,
                      w.risk_score = 0.0, w.flagged = false
        ON MATCH SET  w.state = CASE WHEN row.state <> 'Unknown' THEN row.state ELSE w.state END
        """,
        {"wallets": wallets},
    )


def update_wallet_risk(address: str, risk_score: float, risk_factors: list = None, flagged: bool = False):
    return (
        """
        MATCH (w:Wallet {address: $address})
        SET w.risk_score   = $risk_score,
            w.risk_factors = $risk_factors,
            w.flagged      = CASE WHEN $flagged THEN true ELSE w.flagged END
        RETURN w
        """,
        {"address": address, "risk_score": float(risk_score),
         "risk_factors": risk_factors or [], "flagged": flagged},
    )


def batch_update_wallet_risks(risks: list[dict]):
    return (
        """
        UNWIND $risks AS row
        MATCH (w:Wallet {address: row.address})
        SET w.risk_score   = row.risk_score,
            w.risk_factors = row.risk_factors,
            w.flagged      = CASE WHEN row.flagged THEN true ELSE w.flagged END
        """,
        {"risks": risks},
    )


# ── SENT / RECEIVED_BY edges ───────────────────────────────────────────────────

def merge_sent_relationship(wallet_address: str, txid: str, amount: float):
    return (
        """
        MATCH (w:Wallet      {address: $wallet_address})
        MATCH (t:Transaction {txid:    $txid})
        MERGE (w)-[r:SENT]->(t)
        ON CREATE SET r.amount = $amount
        RETURN r
        """,
        {"wallet_address": wallet_address, "txid": txid, "amount": float(amount)},
    )


def batch_merge_sent_relationships(sent: list[dict]):
    return (
        """
        UNWIND $sent AS row
        MATCH (w:Wallet      {address: row.wallet_address})
        MATCH (t:Transaction {txid:    row.txid})
        MERGE (w)-[r:SENT]->(t)
        ON CREATE SET r.amount = row.amount
        """,
        {"sent": sent},
    )


def merge_received_relationship(txid: str, wallet_address: str, amount: float):
    return (
        """
        MATCH (t:Transaction {txid:    $txid})
        MATCH (w:Wallet      {address: $wallet_address})
        MERGE (t)-[r:RECEIVED_BY]->(w)
        ON CREATE SET r.amount = $amount
        RETURN r
        """,
        {"txid": txid, "wallet_address": wallet_address, "amount": float(amount)},
    )


def batch_merge_received_relationships(rec: list[dict]):
    return (
        """
        UNWIND $rec AS row
        MATCH (t:Transaction {txid:    row.txid})
        MATCH (w:Wallet      {address: row.wallet_address})
        MERGE (t)-[r:RECEIVED_BY]->(w)
        ON CREATE SET r.amount = row.amount
        """,
        {"rec": rec},
    )


# ── SAME_ENTITY_AS (CIOU) edges ───────────────────────────────────────────────

def merge_same_entity_relationship(address_a: str, address_b: str, reason: str = "CIOU"):
    a, b = sorted([address_a, address_b])
    return (
        """
        MATCH (w1:Wallet {address: $a})
        MATCH (w2:Wallet {address: $b})
        MERGE (w1)-[r:SAME_ENTITY_AS]-(w2)
        ON CREATE SET r.reason = $reason
        RETURN r
        """,
        {"a": a, "b": b, "reason": reason},
    )


def batch_merge_same_entity_relationships(ciou: list[dict]):
    return (
        """
        UNWIND $ciou AS row
        MATCH (w1:Wallet {address: row.a})
        MATCH (w2:Wallet {address: row.b})
        MERGE (w1)-[r:SAME_ENTITY_AS]-(w2)
        ON CREATE SET r.reason = row.reason
        """,
        {"ciou": ciou},
    )


# ── Alert node writes (D1) ────────────────────────────────────────────────────

def merge_alert(props: dict):
    """
    Persist a single Alert to Neo4j and link it to its target Wallet.
    props must come from Alert.to_neo4j_props().
    """
    return (
        """
        MERGE (a:Alert {id: $props.id})
        ON CREATE SET
            a.dataset_id       = $props.dataset_id,
            a.entity_type      = $props.entity_type,
            a.entity_id        = $props.entity_id,
            a.detector         = $props.detector,
            a.risk_score       = $props.risk_score,
            a.anomaly_score    = $props.anomaly_score,
            a.severity         = $props.severity,
            a.cluster_name     = $props.cluster_name,
            a.primary_state    = $props.primary_state,
            a.created_at       = $props.created_at,
            a.status           = $props.status,
            a.evidence_json    = $props.evidence_json,
            a.shap_json        = $props.shap_json,
            a.risk_factors     = $props.risk_factors,
            a.correlated_txids = $props.correlated_txids
        WITH a
        MATCH (w:Wallet {address: $props.entity_id})
        MERGE (a)-[:TARGETS]->(w)
        """,
        {"props": props},
    )


def batch_merge_alerts(alerts: list[dict]):
    """Batch version — props list from [alert.to_neo4j_props() for alert in alerts]."""
    return (
        """
        UNWIND $alerts AS props
        MERGE (a:Alert {id: props.id})
        ON CREATE SET
            a.dataset_id       = props.dataset_id,
            a.entity_type      = props.entity_type,
            a.entity_id        = props.entity_id,
            a.detector         = props.detector,
            a.risk_score       = props.risk_score,
            a.anomaly_score    = props.anomaly_score,
            a.severity         = props.severity,
            a.cluster_name     = props.cluster_name,
            a.primary_state    = props.primary_state,
            a.created_at       = props.created_at,
            a.status           = props.status,
            a.evidence_json    = props.evidence_json,
            a.shap_json        = props.shap_json,
            a.risk_factors     = props.risk_factors,
            a.correlated_txids = props.correlated_txids
        WITH a, props
        MATCH (w:Wallet {address: props.entity_id})
        MERGE (a)-[:TARGETS]->(w)
        """,
        {"alerts": alerts},
    )


# ── Investigation read queries ─────────────────────────────────────────────────

def get_wallet_summary(address: str, dataset_id: str | None = None):
    """
    Full wallet summary for GET /investigations/wallet/{address}.
    Returns wallet properties, aggregated statistics, and related IP list.
    Optional dataset_id scopes to a specific ingest run.
    """
    if dataset_id:
        cypher = """
        MATCH (d:Dataset {id: $dataset_id})-[:CONTAINS_WALLET]->(w:Wallet {address: $address})
        OPTIONAL MATCH (w)-[:SENT]->(t:Transaction)
        OPTIONAL MATCH (t)<-[:BROADCAST]-(ip:IP)
        RETURN w,
               count(DISTINCT t) AS tx_count,
               collect(DISTINCT t.fee)       AS fees,
               collect(DISTINCT ip)           AS broadcast_ips,
               collect(DISTINCT t.txid)[..20] AS correlated_txids
        """
    else:
        cypher = """
        MATCH (w:Wallet {address: $address})
        OPTIONAL MATCH (w)-[:SENT]->(t:Transaction)
        OPTIONAL MATCH (t)<-[:BROADCAST]-(ip:IP)
        RETURN w,
               count(DISTINCT t) AS tx_count,
               collect(DISTINCT t.fee)       AS fees,
               collect(DISTINCT ip)           AS broadcast_ips,
               collect(DISTINCT t.txid)[..20] AS correlated_txids
        """
    return cypher, {"address": address, "dataset_id": dataset_id}


def get_wallet_graph(address: str, hops: int = 2, max_nodes: int = 500):
    """
    Returns neighborhood subgraph for GET /investigations/wallet/{address}/graph.
    Bounded by hops and max_nodes to prevent graph explosions.
    """
    return (
        f"""
        MATCH (center:Wallet {{address: $address}})
        CALL apoc.path.subgraphNodes(center, {{
            maxLevel: {hops},
            limit: {max_nodes}
        }}) YIELD node
        WITH collect(node) AS nodes
        UNWIND nodes AS n
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE m IN nodes
        RETURN n, r, m
        """,
        {"address": address},
    )


def get_wallet_graph_fallback(address: str, hops: int = 2, max_nodes: int = 500):
    """
    Pure Cypher fallback for get_wallet_graph when APOC is not available.

    Returns a clean, serializable shape — no raw Neo4j node objects in edges.
    Each relationship is projected as:
        { source: <id_str>, target: <id_str>, type: <str>, amount: <float> }
    where id_str is "wallet:{address}" or "tx:{txid}" etc.
    """
    return (
        f"""
        MATCH path = (w:Wallet {{address: $address}})
                     -[:SENT|RECEIVED_BY|SAME_ENTITY_AS*1..{min(hops, 3)}]-
                     (connected)

        WITH collect(DISTINCT path) AS paths

        UNWIND paths AS p
        UNWIND nodes(p) AS n
        WITH collect(DISTINCT n) AS nodes, paths

        UNWIND paths AS p2
        UNWIND relationships(p2) AS r
        WITH nodes,
             collect(DISTINCT {{
                 source: CASE
                     WHEN 'Wallet'      IN labels(startNode(r)) THEN 'wallet:'      + startNode(r).address
                     WHEN 'Transaction' IN labels(startNode(r)) THEN 'tx:'          + startNode(r).txid
                     WHEN 'IP'          IN labels(startNode(r)) THEN 'ip:'          + startNode(r).address
                     ELSE 'node:' + toString(id(startNode(r)))
                 END,
                 target: CASE
                     WHEN 'Wallet'      IN labels(endNode(r)) THEN 'wallet:'      + endNode(r).address
                     WHEN 'Transaction' IN labels(endNode(r)) THEN 'tx:'          + endNode(r).txid
                     WHEN 'IP'          IN labels(endNode(r)) THEN 'ip:'          + endNode(r).address
                     ELSE 'node:' + toString(id(endNode(r)))
                 END,
                 type:   type(r),
                 amount: coalesce(r.amount, 0.0)
             }}) AS rels

        RETURN nodes, rels
        LIMIT {max_nodes}
        """,
        {"address": address},
    )


def get_wallet_neighborhood(address: str, hops: int = 2):
    """Legacy neighborhood query — kept for backwards compatibility."""
    return (
        f"""
        MATCH path = (w:Wallet {{address: $address}})-[*1..{hops}]-(connected)
        RETURN path
        LIMIT 100
        """,
        {"address": address},
    )


def get_wallet_timeline(address: str, dataset_id: str | None = None, limit: int = 100):
    """
    Chronological events for GET /investigations/wallet/{address}/timeline.
    Returns SENT + RECEIVED_BY transactions ordered by timestamp.
    """
    dataset_filter = "MATCH (d:Dataset {id: $dataset_id})-[:CONTAINS_WALLET]->(w)" if dataset_id else ""
    return (
        f"""
        MATCH (w:Wallet {{address: $address}})
        {dataset_filter}
        OPTIONAL MATCH (w)-[s:SENT]->(t_out:Transaction)
        OPTIONAL MATCH (t_in:Transaction)-[r_in:RECEIVED_BY]->(w)
        WITH w,
             collect(DISTINCT {{
                 type:        'outbound',
                 txid:        t_out.txid,
                 amount:      s.amount,
                 timestamp:   t_out.timestamp,
                 fee:         t_out.fee
             }}) AS sent_events,
             collect(DISTINCT {{
                 type:        'inbound',
                 txid:        t_in.txid,
                 amount:      r_in.amount,
                 timestamp:   t_in.timestamp
             }}) AS recv_events
        RETURN sent_events + recv_events AS events
        LIMIT {limit}
        """,
        {"address": address, "dataset_id": dataset_id},
    )

"""
db/queries/path.py
───────────────────
Cypher queries for path tracing between entities.

Strategy enum (extensible — only "shortest" implemented now):
  shortest — Neo4j shortestPath
  risk     — (501 Not Implemented — reserved for future weighted path)
  all      — (501 Not Implemented — reserved for future allShortestPaths)
"""
from __future__ import annotations


def get_shortest_path(source_address: str, target_address: str, max_hops: int = 5):
    """
    Finds the shortest path between two wallet addresses in the graph.
    Traverses only investigative relationship types:
    SENT, RECEIVED_BY, SAME_ENTITY_AS. Dataset membership relationships are excluded.
    max_hops is validated by the caller against settings.max_investigation_hops.
    """
    return (
        f"""
        MATCH
          (src:Wallet {{address: $source}}),
          (tgt:Wallet {{address: $target}})
        MATCH path = shortestPath(
            (src)-[:SENT|RECEIVED_BY|SAME_ENTITY_AS*1..{max_hops}]-(tgt)
)
        RETURN path,
               length(path) AS hop_count,
               [n IN nodes(path) | {{
                   id:         CASE labels(n)[0]
                                   WHEN 'Wallet'      THEN 'wallet:'      + n.address
                                   WHEN 'Transaction' THEN 'tx:'         + n.txid
                                   WHEN 'IP'          THEN 'ip:'         + n.address
                                   ELSE 'entity:' + toString(id(n))
                               END,
                   type:       toLower(labels(n)[0]),
                   risk_score: coalesce(n.risk_score, 0.0),
                   flagged:    coalesce(n.flagged, false)
               }}] AS path_nodes,
               [r IN relationships(path) | {{
                   type:   type(r),
                   amount: coalesce(r.amount, 0.0)
               }}] AS path_rels
        LIMIT 1
        """,
        {"source": source_address, "target": target_address},
    )

"""
db/schema.py
────────────
Neo4j schema initialization — constraints and indexes.

Called once on FastAPI startup via the lifespan event.
All statements use IF NOT EXISTS so they are fully idempotent.

Node labels:
  :Wallet        — Bitcoin wallet address
  :Transaction   — on-chain transaction
  :IP            — observed network IP address
  :Dataset       — metadata for each ingest job
  :Alert         — persisted forensic alert (stable identity)

Relationship types (for reference, not enforced here):
  SENT            Wallet → Transaction
  RECEIVED_BY     Transaction → Wallet
  BROADCAST       IP → Transaction  (src_ip, with confidence)
  OBSERVED_DESTINATION  Transaction → IP  (dst_ip, with port metadata)
  SAME_ENTITY_AS  Wallet ↔ Wallet  (CIOU co-spending heuristic)
  CONTAINS_WALLET Dataset → Wallet
  CONTAINS_TX     Dataset → Transaction
  OBSERVED_IP     Dataset → IP
  TARGETS         Alert → Wallet
"""
import logging

logger = logging.getLogger("chainwatch.schema")

# ── Uniqueness constraints ─────────────────────────────────────────────────────
_CONSTRAINTS = [
    # Entity uniqueness
    ("wallet_address_unique",
     "CREATE CONSTRAINT wallet_address_unique IF NOT EXISTS "
     "FOR (w:Wallet) REQUIRE w.address IS UNIQUE"),

    ("transaction_txid_unique",
     "CREATE CONSTRAINT transaction_txid_unique IF NOT EXISTS "
     "FOR (t:Transaction) REQUIRE t.txid IS UNIQUE"),

    ("ip_address_unique",
     "CREATE CONSTRAINT ip_address_unique IF NOT EXISTS "
     "FOR (ip:IP) REQUIRE ip.address IS UNIQUE"),

    ("dataset_id_unique",
     "CREATE CONSTRAINT dataset_id_unique IF NOT EXISTS "
     "FOR (d:Dataset) REQUIRE d.id IS UNIQUE"),

    ("alert_id_unique",
     "CREATE CONSTRAINT alert_id_unique IF NOT EXISTS "
     "FOR (a:Alert) REQUIRE a.id IS UNIQUE"),
]

# ── Performance indexes ────────────────────────────────────────────────────────
_INDEXES = [
    # Wallet investigation queries
    ("wallet_risk_score_idx",
     "CREATE INDEX wallet_risk_score_idx IF NOT EXISTS "
     "FOR (w:Wallet) ON (w.risk_score)"),

    ("wallet_flagged_idx",
     "CREATE INDEX wallet_flagged_idx IF NOT EXISTS "
     "FOR (w:Wallet) ON (w.flagged)"),

    ("wallet_state_idx",
     "CREATE INDEX wallet_state_idx IF NOT EXISTS "
     "FOR (w:Wallet) ON (w.state)"),

    # Transaction investigation queries
    ("tx_timestamp_idx",
     "CREATE INDEX tx_timestamp_idx IF NOT EXISTS "
     "FOR (t:Transaction) ON (t.timestamp)"),

    # IP investigation queries
    ("ip_state_idx",
     "CREATE INDEX ip_state_idx IF NOT EXISTS "
     "FOR (ip:IP) ON (ip.state)"),

    ("ip_asn_idx",
     "CREATE INDEX ip_asn_idx IF NOT EXISTS "
     "FOR (ip:IP) ON (ip.asn)"),

    # Alert queries
    ("alert_dataset_idx",
     "CREATE INDEX alert_dataset_idx IF NOT EXISTS "
     "FOR (a:Alert) ON (a.dataset_id)"),

    ("alert_severity_idx",
     "CREATE INDEX alert_severity_idx IF NOT EXISTS "
     "FOR (a:Alert) ON (a.severity)"),

    ("alert_risk_score_idx",
     "CREATE INDEX alert_risk_score_idx IF NOT EXISTS "
     "FOR (a:Alert) ON (a.risk_score)"),

    # Dataset queries
    ("dataset_ingested_at_idx",
     "CREATE INDEX dataset_ingested_at_idx IF NOT EXISTS "
     "FOR (d:Dataset) ON (d.ingested_at)"),
]


def init_schema() -> None:
    """
    Create all constraints and indexes. Safe to call on every startup.
    Logs each statement; swallows individual errors so partial failures
    don't block startup (Neo4j 5.x can raise on already-exists in older formats).
    """
    from db.neo4j_driver import run_query

    for name, cypher in _CONSTRAINTS:
        try:
            run_query(cypher, write=True)
            logger.debug(f"Schema constraint ready: {name}")
        except Exception as exc:
            logger.warning(f"Constraint {name} skipped: {exc}")

    for name, cypher in _INDEXES:
        try:
            run_query(cypher, write=True)
            logger.debug(f"Schema index ready: {name}")
        except Exception as exc:
            logger.warning(f"Index {name} skipped: {exc}")

    logger.info("Neo4j schema initialization complete.")

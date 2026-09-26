"""
db/queries — split Cypher query modules.

Importing from here re-exports all query functions so existing code
that does `from db import queries; queries.batch_merge_wallets(...)` keeps working.
"""
from db.queries.common import clear_all_data, merge_dataset, batch_link_dataset_wallets, batch_link_dataset_txs, batch_link_dataset_ips
from db.queries.wallet import (
    merge_wallet, batch_merge_wallets,
    update_wallet_risk, batch_update_wallet_risks,
    merge_sent_relationship, batch_merge_sent_relationships,
    merge_received_relationship, batch_merge_received_relationships,
    merge_same_entity_relationship, batch_merge_same_entity_relationships,
    merge_alert, batch_merge_alerts,
    get_wallet_summary, get_wallet_neighborhood,
    get_wallet_timeline, get_wallet_graph, get_wallet_graph_fallback,
)
from db.queries.transaction import (
    merge_transaction, batch_merge_transactions,
    get_transaction_detail,
)
from db.queries.ip import (
    merge_ip, batch_merge_ips,
    merge_broadcast_relationship, batch_merge_broadcast_relationships,
    merge_observed_destination, batch_merge_observed_destinations,
    get_ip_detail,
)
from db.queries.path import get_shortest_path
from db.queries.search import search_entities

__all__ = [
    # common
    "clear_all_data", "merge_dataset",
    "batch_link_dataset_wallets", "batch_link_dataset_txs", "batch_link_dataset_ips",
    # wallet
    "merge_wallet", "batch_merge_wallets",
    "update_wallet_risk", "batch_update_wallet_risks",
    "merge_sent_relationship", "batch_merge_sent_relationships",
    "merge_received_relationship", "batch_merge_received_relationships",
    "merge_same_entity_relationship", "batch_merge_same_entity_relationships",
    "merge_alert", "batch_merge_alerts",
    "get_wallet_summary", "get_wallet_neighborhood",
    "get_wallet_timeline", "get_wallet_graph", "get_wallet_graph_fallback",
    # transaction
    "merge_transaction", "batch_merge_transactions", "get_transaction_detail",
    # ip
    "merge_ip", "batch_merge_ips",
    "merge_broadcast_relationship", "batch_merge_broadcast_relationships",
    "merge_observed_destination", "batch_merge_observed_destinations",
    "get_ip_detail",
    # path
    "get_shortest_path",
    # search
    "search_entities",
]

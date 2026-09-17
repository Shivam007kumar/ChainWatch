import networkx as nx
from collections import defaultdict

def propagate_risk_scores(
    transaction_records: list[dict],
    seed_threat_wallets: dict[str, float],
    decay_factor: float = 0.70,
    max_hops: int = 4
) -> dict[str, dict]:
    """
    Propagates Risk Scores across transaction edges starting from seed threat wallets.

    Input:
      - transaction_records: list of transaction records
      - seed_threat_wallets: dict of {wallet_address: initial_risk_score} (e.g. 95.0)
      - decay_factor: risk decay per transaction hop (default 0.70)
      - max_hops: maximum propagation distance

    Output:
      - dict of {wallet_address: {"risk_score": float, "risk_factors": list, "distance": int}}
    """
    if not seed_threat_wallets:
        return {}

    # Build directed wallet transaction graph (Wallet A -> Wallet B if A sent to tx and tx sent to B)
    G = nx.DiGraph()
    for tx in transaction_records:
        inputs = tx["input_addresses"]
        outputs = tx["output_addresses"]
        for inp in inputs:
            for out in outputs:
                if inp != out:
                    G.add_edge(inp, out, txid=tx["txid"])

    risk_results = {}

    # Initialize seed scores
    for seed, score in seed_threat_wallets.items():
        risk_results[seed] = {
            "risk_score": float(score),
            "risk_factors": ["DIRECT_FLAGGED_SEED_THREAT"],
            "distance": 0,
            "seed_source": seed
        }

    # BFS Traversal from seeds
    for seed, base_score in seed_threat_wallets.items():
        if seed not in G:
            continue
        
        # Calculate shortest paths from seed up to max_hops
        lengths = nx.single_source_shortest_path_length(G, seed, cutoff=max_hops)
        
        for node, dist in lengths.items():
            if dist == 0:
                continue

            propagated_score = round(base_score * (decay_factor ** dist), 1)

            if node not in risk_results or propagated_score > risk_results[node]["risk_score"]:
                factors = []
                if dist == 1:
                    factors.append("DIRECT_PAYMENT_FROM_THREAT_WALLET")
                elif dist == 2:
                    factors.append("2_HOP_LAUNDERING_RECEPTACLE")
                elif dist == 3:
                    factors.append("3_HOP_DOWNSTREAM_RECEPTACLE")
                else:
                    factors.append(f"{dist}_HOP_DOWNSTREAM_RECEPTACLE")

                risk_results[node] = {
                    "risk_score": propagated_score,
                    "risk_factors": factors,
                    "distance": dist,
                    "seed_source": seed
                }

    return risk_results

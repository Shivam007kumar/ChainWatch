import logging

import networkx as nx
from collections import defaultdict

logger = logging.getLogger("chainwatch.peeling_chain")

def detect_peeling_chains(transaction_records: list[dict], min_hops: int = 3) -> list[dict]:
    """
    Detects peeling chain laundering sequences.
    A peeling chain occurs when a transaction takes 1 input (or change input)
    and splits it into 2 outputs:
      1. A small "peeled" output (< 15% of output volume) sent to a cashout/retail wallet.
      2. A large "change" output (> 85% of output volume) sent to a new wallet,
         which immediately acts as input in the next transaction.
    """
    # 1. Identify potential peeling steps
    peel_steps = []
    wallet_out_txs = defaultdict(list)
    tx_map = {}

    for tx in transaction_records:
        txid = tx["txid"]
        tx_map[txid] = tx
        inputs = tx["input_addresses"]
        outputs = tx["output_addresses"]
        amounts = tx["output_amounts"]

        for inp in inputs:
            wallet_out_txs[inp].append(txid)

        # Check for 1 input (or main input) and 2 outputs structure
        if len(outputs) == 2 and sum(amounts) > 0:
            total_out = sum(amounts)
            amt1, amt2 = amounts[0], amounts[1]
            out1, out2 = outputs[0], outputs[1]

            # Determine peel vs change
            ratio1 = amt1 / total_out
            ratio2 = amt2 / total_out

            if ratio1 > 0.80 and ratio2 < 0.20:
                change_wallet, peel_wallet = out1, out2
                change_amt, peel_amt = amt1, amt2
            elif ratio2 > 0.80 and ratio1 < 0.20:
                change_wallet, peel_wallet = out2, out1
                change_amt, peel_amt = amt2, amt1
            else:
                continue

            src_wallet = inputs[0] if len(inputs) == 1 else None
            peel_steps.append({
                "txid": txid,
                "src_wallet": src_wallet,
                "change_wallet": change_wallet,
                "peel_wallet": peel_wallet,
                "change_amount": change_amt,
                "peel_amount": peel_amt,
                "total_amount": total_out
            })

    # 2. Build directed graph of change wallet progressions
    G = nx.DiGraph()
    step_dict = {}
    for step in peel_steps:
        txid = step["txid"]
        step_dict[txid] = step
        if step["src_wallet"] and step["change_wallet"]:
            G.add_edge(step["src_wallet"], step["change_wallet"], txid=txid, step=step)

    # 3. Find paths of length >= min_hops
    peeling_chains = []
    chain_counter = 1
    MAX_PATH_ITERATIONS = 10_000   # hard cap — prevents hang on large graphs

    # Find root nodes (nodes with in-degree 0 or multiple inputs)
    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    for root in roots:
        if chain_counter > MAX_PATH_ITERATIONS:
            logger.warning(f"Peeling chain search capped at {MAX_PATH_ITERATIONS} paths.")
            break
        for target in G.nodes():
            if root == target:
                continue
            if chain_counter > MAX_PATH_ITERATIONS:
                break
            for path in nx.all_simple_paths(G, source=root, target=target, cutoff=min_hops + 3):
                if chain_counter > MAX_PATH_ITERATIONS:
                    break
                if len(path) - 1 >= min_hops:
                    tx_sequence = []
                    peeled_wallets = []
                    total_peeled_btc = 0.0

                    for i in range(len(path) - 1):
                        u, v = path[i], path[i + 1]
                        edge_data = G.get_edge_data(u, v)
                        step = edge_data["step"]
                        tx_sequence.append(step["txid"])
                        peeled_wallets.append(step["peel_wallet"])
                        total_peeled_btc += step["peel_amount"]

                    peeling_chains.append({
                        "chain_id": f"PEEL-{chain_counter:03d}",
                        "start_wallet": root,
                        "end_wallet": target,
                        "hop_count": len(path) - 1,
                        "total_peeled_volume_btc": round(total_peeled_btc, 4),
                        "wallets_involved": path,
                        "peeled_cashout_wallets": list(set(peeled_wallets)),
                        "transactions_involved": tx_sequence,
                        "risk_score": min(95.0, 70.0 + (len(path) - 1) * 5.0)
                    })
                    chain_counter += 1

    return peeling_chains


def detect_coinjoin_mixing(transaction_records: list[dict]) -> list[dict]:
    """
    Detects CoinJoin / Mixing transactions.
    Characteristics of a CoinJoin mix:
      - 3 or more distinct input addresses
      - 3 or more distinct output addresses
      - Uniform output amounts (low variance)
    """
    mixing_txs = []
    for tx in transaction_records:
        inputs = set(tx["input_addresses"])
        outputs = set(tx["output_addresses"])
        amounts = tx["output_amounts"]

        if len(inputs) >= 3 and len(outputs) >= 3:
            # Check for uniform output amounts
            if len(amounts) > 0:
                mean_amt = sum(amounts) / len(amounts)
                if mean_amt > 0:
                    max_diff = max(abs(a - mean_amt) for a in amounts)
                    if max_diff / mean_amt < 0.02:  # Less than 2% variance
                        mixing_txs.append({
                            "txid": tx["txid"],
                            "input_count": len(inputs),
                            "output_count": len(outputs),
                            "denominated_amount_btc": round(mean_amt, 4),
                            "total_volume_btc": round(sum(amounts), 4),
                            "input_wallets": list(inputs),
                            "output_wallets": list(outputs),
                            "risk_score": 85.0,
                            "type": "COINJOIN_MIXER"
                        })
    return mixing_txs

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.correlation import correlate_captures
from analytics.peeling_chain import detect_peeling_chains, detect_coinjoin_mixing
from analytics.risk_propagation import propagate_risk_scores


def test_exponential_correlation():
    captures = [
        {"txid": "tx1", "src_ip": "1.1.1.1", "timestamp": "2026-09-17T10:00:00"},
        {"txid": "tx1", "src_ip": "2.2.2.2", "timestamp": "2026-09-17T10:00:07"},
        {"txid": "tx1", "src_ip": "3.3.3.3", "timestamp": "2026-09-17T10:01:00"},  # > 30s away
    ]
    results = correlate_captures(captures)
    assert len(results) == 2, f"Expected 2 correlated captures within window, got {len(results)}"
    
    c1 = next(r for r in results if r["src_ip"] == "1.1.1.1")
    c2 = next(r for r in results if r["src_ip"] == "2.2.2.2")
    
    assert c1["confidence"] == 1.0
    assert abs(c2["confidence"] - round(math.exp(-7.0 / 8.0), 4)) < 0.001
    print("✅ Exponential decay IP correlation test passed.")


def test_peeling_chain_detection():
    txs = [
        {
            "txid": "tx_p1", "input_addresses": ["wallet_root"], "input_amounts": [50.0],
            "output_addresses": ["wallet_change_1", "wallet_peel_1"], "output_amounts": [49.5, 0.5]
        },
        {
            "txid": "tx_p2", "input_addresses": ["wallet_change_1"], "input_amounts": [49.5],
            "output_addresses": ["wallet_change_2", "wallet_peel_2"], "output_amounts": [49.0, 0.5]
        },
        {
            "txid": "tx_p3", "input_addresses": ["wallet_change_2"], "input_amounts": [49.0],
            "output_addresses": ["wallet_change_3", "wallet_peel_3"], "output_amounts": [48.5, 0.5]
        },
    ]
    chains = detect_peeling_chains(txs, min_hops=3)
    assert len(chains) >= 1, f"Expected peeling chain detected, got {len(chains)}"
    chain = chains[0]
    assert chain["start_wallet"] == "wallet_root"
    assert chain["end_wallet"] == "wallet_change_3"
    assert chain["hop_count"] == 3
    print("✅ Peeling Chain detection test passed.")


def test_coinjoin_mixing_detection():
    txs = [
        {
            "txid": "tx_mix",
            "input_addresses": ["w_in1", "w_in2", "w_in3"],
            "input_amounts": [10.0, 10.0, 10.0],
            "output_addresses": ["w_out1", "w_out2", "w_out3"],
            "output_amounts": [9.99, 9.99, 9.99]
        }
    ]
    mixers = detect_coinjoin_mixing(txs)
    assert len(mixers) == 1
    assert mixers[0]["txid"] == "tx_mix"
    print("✅ CoinJoin Mixing detection test passed.")


def test_risk_propagation():
    txs = [
        {
            "txid": "t1",
            "input_addresses": ["bad_seed"], "input_amounts": [10.0],
            "output_addresses": ["w_hop1"], "output_amounts": [10.0]
        },
        {
            "txid": "t2",
            "input_addresses": ["w_hop1"], "input_amounts": [10.0],
            "output_addresses": ["w_hop2"], "output_amounts": [10.0]
        }
    ]
    seeds = {"bad_seed": 100.0}
    risks = propagate_risk_scores(txs, seeds, decay_factor=0.70)
    
    assert "w_hop1" in risks
    assert risks["w_hop1"]["risk_score"] == 70.0
    assert "w_hop2" in risks
    assert risks["w_hop2"]["risk_score"] == 49.0
    print("✅ Risk score propagation test passed.")


if __name__ == "__main__":
    test_exponential_correlation()
    test_peeling_chain_detection()
    test_coinjoin_mixing_detection()
    test_risk_propagation()
    print("🎉 All analytics forensic unit tests passed!")

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.correlation import correlate_captures
from analytics.peeling_chain import detect_coinjoin_mixing, detect_peeling_chains
from analytics.risk_propagation import propagate_risk_scores


# ── existing tests ────────────────────────────────────────────────────────────

def test_exponential_correlation():
    captures = [
        {"txid": "tx1", "src_ip": "1.1.1.1", "timestamp": "2026-09-17T10:00:00"},
        {"txid": "tx1", "src_ip": "2.2.2.2", "timestamp": "2026-09-17T10:00:07"},
        {"txid": "tx1", "src_ip": "3.3.3.3", "timestamp": "2026-09-17T10:01:00"},  # > 30 s — dropped
    ]
    results = correlate_captures(captures)
    assert len(results) == 2, f"Expected 2 captures within window, got {len(results)}"

    c1 = next(r for r in results if r["src_ip"] == "1.1.1.1")
    c2 = next(r for r in results if r["src_ip"] == "2.2.2.2")

    assert c1["confidence"] == 1.0
    assert abs(c2["confidence"] - round(math.exp(-7.0 / 8.0), 4)) < 0.001
    print("✅ Exponential decay IP correlation test passed.")


def test_peeling_chain_detection():
    txs = [
        {
            "txid": "tx_p1",
            "input_addresses": ["wallet_root"], "input_amounts": [50.0],
            "output_addresses": ["wallet_change_1", "wallet_peel_1"],
            "output_amounts": [49.5, 0.5],
        },
        {
            "txid": "tx_p2",
            "input_addresses": ["wallet_change_1"], "input_amounts": [49.5],
            "output_addresses": ["wallet_change_2", "wallet_peel_2"],
            "output_amounts": [49.0, 0.5],
        },
        {
            "txid": "tx_p3",
            "input_addresses": ["wallet_change_2"], "input_amounts": [49.0],
            "output_addresses": ["wallet_change_3", "wallet_peel_3"],
            "output_amounts": [48.5, 0.5],
        },
    ]
    chains = detect_peeling_chains(txs, min_hops=3)
    assert len(chains) >= 1, f"Expected peeling chain detected, got {len(chains)}"
    chain = chains[0]
    assert chain["start_wallet"] == "wallet_root"
    assert chain["end_wallet"]   == "wallet_change_3"
    assert chain["hop_count"]    == 3
    print("✅ Peeling chain detection test passed.")


def test_coinjoin_mixing_detection():
    txs = [
        {
            "txid": "tx_mix",
            "input_addresses":  ["w_in1", "w_in2", "w_in3"],
            "input_amounts":    [10.0, 10.0, 10.0],
            "output_addresses": ["w_out1", "w_out2", "w_out3"],
            "output_amounts":   [9.99, 9.99, 9.99],
        }
    ]
    mixers = detect_coinjoin_mixing(txs)
    assert len(mixers) == 1
    assert mixers[0]["txid"] == "tx_mix"
    print("✅ CoinJoin mixing detection test passed.")


def test_risk_propagation():
    txs = [
        {
            "txid": "t1",
            "input_addresses":  ["bad_seed"], "input_amounts":  [10.0],
            "output_addresses": ["w_hop1"],   "output_amounts": [10.0],
        },
        {
            "txid": "t2",
            "input_addresses":  ["w_hop1"],  "input_amounts":  [10.0],
            "output_addresses": ["w_hop2"],  "output_amounts": [10.0],
        },
    ]
    seeds = {"bad_seed": 100.0}
    risks = propagate_risk_scores(txs, seeds, decay_factor=0.70)

    assert "w_hop1" in risks
    assert risks["w_hop1"]["risk_score"] == 70.0
    assert "w_hop2" in risks
    assert risks["w_hop2"]["risk_score"] == 49.0
    print("✅ Risk score propagation test passed.")


# ── SHAP unit tests ───────────────────────────────────────────────────────────

def test_shap_explainer_output_structure():
    """
    Verify that explain_anomalies returns well-formed attribution dicts
    with the correct keys, correct top_k count, and descending pct_contribution.
    Uses 14 features to match the production feature matrix.
    """
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    from analytics.shap_explainer import FEATURE_NAMES, explain_anomalies

    rng = np.random.default_rng(42)
    X_raw = rng.random((60, 14)).astype(float)
    # Make index 0 a clear outlier — extreme values across all 14 features
    X_raw[0] = [50.0, 1000.0, 12.0, 250.0, 6.5, 9.0, 0.95, 7.0,
                45000.0, 8333.0, 0.9, 0.8, 0.4, 0.2]

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    model.fit(X_scaled)

    results = explain_anomalies(
        iso_model=model,
        X_scaled=X_scaled,
        X_raw=X_raw,
        scaler=scaler,
        wallet_indices=[0],
        feature_names=FEATURE_NAMES,
        top_k=3,
    )

    assert 0 in results, "No result for wallet index 0"

    entry = results[0]
    assert "reason"            in entry, "Missing 'reason' key"
    assert "shap_attributions" in entry, "Missing 'shap_attributions' key"
    assert isinstance(entry["reason"], str) and len(entry["reason"]) > 0, "reason must be non-empty string"

    attrs = entry["shap_attributions"]
    assert len(attrs) == 3, f"Expected top_k=3 attributions, got {len(attrs)}"

    required_keys = {"feature", "label", "shap_value", "feature_value", "sigma", "direction", "pct_contribution"}
    for attr in attrs:
        missing = required_keys - attr.keys()
        assert not missing, f"Attribution missing keys: {missing}"
        assert attr["direction"] in ("positive", "negative"), f"Invalid direction: {attr['direction']}"
        assert 0 <= attr["pct_contribution"] <= 100, f"pct_contribution out of range: {attr['pct_contribution']}"

    pcts = [a["pct_contribution"] for a in attrs]
    assert pcts == sorted(pcts, reverse=True), f"Attributions not sorted descending: {pcts}"

    print("✅ SHAP explainer structure test passed.")


def test_shap_reason_string_format():
    """
    Verify the reason string produced by the formatter contains
    percentage markers and sigma values. Uses 14 features.
    """
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    from analytics.shap_explainer import FEATURE_NAMES, explain_anomalies

    rng = np.random.default_rng(7)
    X_raw = rng.random((40, 14)).astype(float)
    X_raw[0] = [30.0, 500.0, 8.0, 120.0, 4.0, 6.0, 0.8, 5.0,
                40000.0, 8333.0, 0.7, 0.6, 0.2, 0.3]

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    model.fit(X_scaled)

    results = explain_anomalies(
        iso_model=model,
        X_scaled=X_scaled,
        X_raw=X_raw,
        scaler=scaler,
        wallet_indices=[0],
        feature_names=FEATURE_NAMES,
        top_k=3,
    )

    reason = results[0]["reason"]
    assert "%" in reason,  "reason string must contain percentage markers"
    assert "σ" in reason,  "reason string must contain sigma deviation marker"
    assert reason.endswith("."), "reason string must end with a period"
    print("✅ SHAP reason string format test passed.")


def test_shap_empty_indices():
    """
    explain_anomalies with an empty wallet_indices list must return {}.
    """
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    from analytics.shap_explainer import explain_anomalies

    X_raw    = np.random.rand(20, 14)
    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)
    model    = IsolationForest(n_estimators=50, random_state=42)
    model.fit(X_scaled)

    results = explain_anomalies(model, X_scaled, X_raw, scaler, wallet_indices=[])
    assert results == {}, f"Expected empty dict, got {results}"
    print("✅ SHAP empty indices test passed.")


def test_shap_feature_names_match():
    """
    FEATURE_NAMES must have exactly 14 entries matching the 14-feature
    vector built by graph_builder. Every feature must have a human label.
    """
    from analytics.shap_explainer import FEATURE_NAMES, FEATURE_LABELS

    assert len(FEATURE_NAMES) == 14, f"Expected 14 features, got {len(FEATURE_NAMES)}"

    expected = [
        "tx_count", "total_volume_btc", "unique_ip_count",
        "tx_velocity", "amount_variance", "unique_asn_count",
        "cross_state_ip_ratio", "avg_output_count",
        "avg_src_port", "avg_dst_port", "dst_src_state_match",
        "script_type_risk_ratio", "balance_violation_ratio", "avg_broadcast_confidence",
    ]
    assert FEATURE_NAMES == expected, (
        f"FEATURE_NAMES mismatch:\n  got:      {FEATURE_NAMES}\n  expected: {expected}"
    )

    for name in FEATURE_NAMES:
        assert name in FEATURE_LABELS, f"No human label for feature '{name}'"

    print("✅ SHAP feature registry (14 features) test passed.")


def test_ciou_risk_merging():
    """
    merge_ciou_risks must elevate a co-spending wallet's risk score
    to seed_score * boost_factor when it shares inputs with a flagged seed.
    """
    from analytics.risk_propagation import merge_ciou_risks

    txs = [
        {
            "txid": "tx_ciou",
            "input_addresses":  ["flagged_wallet", "clean_peer"],
            "output_addresses": ["output_wallet"],
            "input_amounts":    [10.0, 10.0],
            "output_amounts":   [19.9],
        }
    ]
    risk_results = {
        "flagged_wallet": {"risk_score": 90.0, "risk_factors": ["DIRECT_FLAGGED_SEED_THREAT"], "distance": 0, "seed_source": "flagged_wallet"}
    }

    merged = merge_ciou_risks(risk_results, txs, boost_factor=0.85)

    assert "clean_peer" in merged, "Co-spending peer must appear in merged results"
    assert merged["clean_peer"]["risk_score"] == round(90.0 * 0.85, 1), (
        f"Expected {round(90.0 * 0.85, 1)}, got {merged['clean_peer']['risk_score']}"
    )
    assert "CIOU_CO_SPENDER_WITH_THREAT_WALLET" in merged["clean_peer"]["risk_factors"]
    print("✅ CIOU risk merging test passed.")


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_exponential_correlation()
    test_peeling_chain_detection()
    test_coinjoin_mixing_detection()
    test_risk_propagation()
    test_shap_explainer_output_structure()
    test_shap_reason_string_format()
    test_shap_empty_indices()
    test_shap_feature_names_match()
    test_ciou_risk_merging()
    print("\n🎉 All analytics + SHAP forensic unit tests passed!")

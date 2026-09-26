"""
analytics/anomaly.py
─────────────────────
IsolationForest anomaly detection — extracted from graph_builder.py.

Provides a clean run() interface that returns a list of DetectionResult,
one per flagged wallet. graph_builder.py continues to run its own inline
version until test_integration.py confirms equivalent output, at which
point graph_builder.py's inline ML block is removed.

Key design decisions (from architecture review):
  - risk_score: rescaled 60–99 from IF decision_function range of flagged wallets
  - anomaly_score: the raw signed decision_function value (preserved, not discarded)
  - confidence: None — IsolationForest contamination=0.10 always flags 10% of
    wallets regardless of actual anomaly density. That is not a calibrated
    probability and must not be presented as one.
  - confidence_method: None for the same reason.
"""
from __future__ import annotations

import logging
from collections import Counter

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from analytics.shap_explainer import FEATURE_NAMES, explain_anomalies
from models.domain.alert import DetectionResult, Evidence

logger = logging.getLogger("chainwatch.anomaly")


def run(
    wallets:      list[str],
    features:     np.ndarray,
    wallet_stats: dict,
    scaler:       StandardScaler,
    n_estimators: int   = 200,
    contamination: float = 0.10,
    random_state: int   = 42,
    top_k_shap:   int   = 3,
) -> tuple[list[DetectionResult], IsolationForest, np.ndarray]:
    """
    Fit IsolationForest on the feature matrix and return DetectionResult objects
    for each flagged wallet.

    Parameters
    ----------
    wallets       : ordered list of wallet addresses (matches rows in features)
    features      : (n_wallets × 14) raw feature matrix from _build_feature_matrix()
    wallet_stats  : per-wallet aggregation dict (for primary_state, etc.)
    scaler        : already-fitted StandardScaler (features already scaled externally)
    n_estimators  : IsolationForest trees
    contamination : fraction of wallets to flag (0.10 = 10%)
    random_state  : for reproducibility
    top_k_shap    : number of SHAP features to include in Evidence

    Returns
    -------
    (results, iso_model, X_scaled)
      results   — list[DetectionResult], one per flagged wallet, sorted risk_score desc
      iso_model — fitted IsolationForest (passed to clustering for KMeans)
      X_scaled  — StandardScaler-normalised feature matrix
    """
    if len(wallets) == 0 or len(features) == 0:
        return [], None, np.array([])

    X_scaled   = scaler.transform(features)
    iso        = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    iso_labels = iso.fit_predict(X_scaled)
    iso_scores = iso.decision_function(X_scaled)   # more negative = more anomalous

    flagged_idx = [i for i, lbl in enumerate(iso_labels) if lbl == -1]

    if not flagged_idx:
        return [], iso, X_scaled

    flagged_scores = iso_scores[flagged_idx]
    lo   = float(flagged_scores.min())
    hi   = float(flagged_scores.max())
    span = (hi - lo) if hi != lo else 1e-9

    # SHAP attributions for flagged wallets
    shap_results = explain_anomalies(
        iso_model=iso,
        X_scaled=X_scaled,
        X_raw=features,
        scaler=scaler,
        wallet_indices=flagged_idx,
        feature_names=FEATURE_NAMES,
        top_k=top_k_shap,
    )

    results: list[DetectionResult] = []

    for i in flagged_idx:
        wallet = wallets[i]
        s      = wallet_stats[wallet]

        # Rescale decision_function to [60, 99]
        raw_score  = float(iso_scores[i])
        risk_score = round(60 + 39 * (hi - raw_score) / span, 1)

        shap_data         = shap_results.get(i, {})
        shap_attributions = shap_data.get("shap_attributions", [])
        reason            = shap_data.get("reason") or (
            f"AI anomaly: {s['tx_count']} TXNs, {s['volume']:.4f} BTC, {len(s['ips'])} IPs."
        )

        # Build Evidence items from SHAP attributions
        evidence_items: list[Evidence] = []
        if shap_attributions:
            evidence_items.append(Evidence(
                type              = "shap",
                title             = f"SHAP top-{top_k_shap} feature contributions",
                confidence        = None,
                risk_contribution = risk_score,
                details           = {"attributions": shap_attributions, "reason": reason},
            ))

        results.append(DetectionResult(
            detector      = "isolation_forest",
            entity_type   = "wallet",
            entity_id     = wallet,
            risk_score    = risk_score,
            anomaly_score = raw_score,   # raw signed value, preserved
            confidence    = None,        # not calibrated — see module docstring
            confidence_method = None,
            evidence      = [e.to_dict() for e in evidence_items],
            metadata      = {
                "tx_count":         s["tx_count"],
                "total_volume_btc": round(s["volume"], 4),
                "unique_ip_count":  len(s["ips"]),
                "primary_state":    Counter(s["states"]).most_common(1)[0][0] if s["states"] else "Unknown",
                "shap_attributions": shap_attributions,
                "reason":           reason,
            },
        ))

    results.sort(key=lambda r: r.risk_score, reverse=True)
    return results, iso, X_scaled

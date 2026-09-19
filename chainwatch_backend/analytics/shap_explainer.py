"""
shap_explainer.py
-----------------
SHAP TreeExplainer wrapper for ChainWatch IsolationForest anomaly detection.

Takes a fitted IsolationForest model and its training data, computes exact
Shapley values via shap.TreeExplainer, and formats per-wallet attribution
strings for the alert API and PDF dossier.

Output per flagged wallet:
  {
    "reason": "<human-readable top-3 attribution string>",
    "shap_attributions": [
      {
        "feature": "tx_velocity",
        "label": "transaction velocity (tx/hr)",
        "shap_value": 0.412,
        "feature_value": 18.3,
        "sigma": 2.4,
        "direction": "positive",
        "pct_contribution": 41
      },
      ...  (top_k entries, sorted by |shap_value| descending)
    ]
  }
"""

import logging
import numpy as np

logger = logging.getLogger("chainwatch.shap_explainer")

# ── Feature registry ──────────────────────────────────────────────────────────

FEATURE_NAMES = [
    "tx_count",
    "total_volume_btc",
    "unique_ip_count",
    "tx_velocity",
    "amount_variance",
    "unique_asn_count",
    "cross_state_ip_ratio",
    "avg_output_count",
    "avg_src_port",
    "avg_dst_port",
    "dst_src_state_match",
    "script_type_risk_ratio",
    "balance_violation_ratio",
    "avg_broadcast_confidence",
]

FEATURE_LABELS = {
    "tx_count":                 "transaction count",
    "total_volume_btc":         "total BTC volume",
    "unique_ip_count":          "distinct broadcast IPs",
    "tx_velocity":              "transaction velocity (tx/hr)",
    "amount_variance":          "output amount variance",
    "unique_asn_count":         "distinct ISP/ASN providers",
    "cross_state_ip_ratio":     "cross-state IP routing ratio",
    "avg_output_count":         "average outputs per transaction",
    "avg_src_port":             "average source port",
    "avg_dst_port":             "average destination port",
    "dst_src_state_match":      "cross-state routing ratio",
    "script_type_risk_ratio":   "high-risk script type ratio (P2SH/P2WSH)",
    "balance_violation_ratio":  "transaction balance discrepancy ratio",
    "avg_broadcast_confidence": "average broadcast IP confidence score",
}

# Plain-English phrase snippets used in the reason string
_POSITIVE_CONTEXT = {
    "tx_count":                 "high transaction frequency",
    "total_volume_btc":         "large BTC volume",
    "unique_ip_count":          "many distinct broadcast IPs",
    "tx_velocity":              "rapid transaction burst",
    "amount_variance":          "irregular output sizing",
    "unique_asn_count":         "multi-provider ISP routing",
    "cross_state_ip_ratio":     "cross-jurisdiction IP routing",
    "avg_output_count":         "high fan-out per transaction",
    "avg_src_port":             "unusual source port pattern",
    "avg_dst_port":             "non-standard destination port",
    "dst_src_state_match":      "cross-state IP routing",
    "script_type_risk_ratio":   "predominant use of high-risk script types",
    "balance_violation_ratio":  "repeated input/output balance violations",
    "avg_broadcast_confidence": "high-confidence direct broadcaster",
}

_NEGATIVE_CONTEXT = {
    "tx_count":                 "low transaction count (within normal range)",
    "total_volume_btc":         "modest BTC volume",
    "unique_ip_count":          "concentrated broadcast IPs",
    "tx_velocity":              "slow transaction cadence",
    "amount_variance":          "uniform output amounts",
    "unique_asn_count":         "single-provider routing",
    "cross_state_ip_ratio":     "single-state IP origin",
    "avg_output_count":         "low output fan-out",
    "avg_src_port":             "standard source port range",
    "avg_dst_port":             "standard P2P port (8333)",
    "dst_src_state_match":      "same-state routing",
    "script_type_risk_ratio":   "standard P2PKH scripts",
    "balance_violation_ratio":  "clean balance accounting",
    "avg_broadcast_confidence": "low-confidence relay (weak IP link)",
}


# ── Core explainer ────────────────────────────────────────────────────────────

def explain_anomalies(
    iso_model,
    X_scaled: np.ndarray,
    X_raw: np.ndarray,
    scaler,
    wallet_indices: list,
    feature_names: list = None,
    top_k: int = 3,
) -> dict:
    """
    Compute SHAP attributions for flagged wallet indices.

    Parameters
    ----------
    iso_model      : fitted sklearn IsolationForest
    X_scaled       : StandardScaler-normalized feature matrix (n_wallets × n_features)
    X_raw          : raw (unscaled) feature matrix — same shape
    scaler         : the fitted StandardScaler (for sigma computation)
    wallet_indices : list of row indices in X_scaled that were flagged as anomalies
    feature_names  : list of feature name strings (defaults to FEATURE_NAMES)
    top_k          : number of top features to include in attribution output

    Returns
    -------
    dict keyed by wallet index:
      { idx: { "reason": str, "shap_attributions": list } }
    """
    if not wallet_indices:
        return {}

    names = feature_names or FEATURE_NAMES

    # Attempt TreeExplainer — fastest and exact for tree ensembles
    shap_matrix = _compute_shap_values(iso_model, X_scaled)
    if shap_matrix is None:
        logger.warning("SHAP computation failed — falling back to empty attributions.")
        return {idx: {"reason": "", "shap_attributions": []} for idx in wallet_indices}

    results = {}
    for idx in wallet_indices:
        if idx >= len(shap_matrix):
            results[idx] = {"reason": "", "shap_attributions": []}
            continue

        shap_row = shap_matrix[idx]          # shape: (n_features,)
        raw_row  = X_raw[idx]                # raw feature values for this wallet

        attributions = _build_attributions(shap_row, raw_row, names, scaler, top_k)
        reason       = _format_reason(attributions)

        results[idx] = {
            "reason":            reason,
            "shap_attributions": attributions,
        }

    return results


def _compute_shap_values(iso_model, X_scaled: np.ndarray):
    """
    Run shap.TreeExplainer on the fitted IsolationForest.
    Returns the shap_values matrix (n_samples × n_features) or None on failure.

    IsolationForest.decision_function output is negated inside SHAP so that
    positive SHAP values push toward anomaly (higher risk).
    We negate the final matrix so the sign convention is:
        positive shap_value = feature pushed this wallet TOWARD being an anomaly.
        negative shap_value = feature pushed this wallet TOWARD being normal.
    """
    try:
        import shap  # imported here so the rest of the module works if shap is missing

        # check_additivity=False suppresses a floating-point warning that fires
        # on IsolationForest because the base value doesn't sum cleanly
        explainer   = shap.TreeExplainer(iso_model)
        shap_values = explainer.shap_values(X_scaled, check_additivity=False)

        # shap_values may be a list (one array per class) for some sklearn versions
        if isinstance(shap_values, list):
            shap_values = shap_values[0]

        # IsolationForest decision_function: more negative = more anomalous.
        # SHAP reflects that convention, so we negate so positive = more anomalous.
        return -np.array(shap_values)

    except ImportError:
        logger.error("shap package not installed. Run: pip install shap==0.46.0")
        return None
    except Exception as exc:
        logger.error(f"SHAP TreeExplainer error: {exc}")
        return None


def _build_attributions(
    shap_row: np.ndarray,
    raw_row: np.ndarray,
    feature_names: list,
    scaler,
    top_k: int,
) -> list:
    """
    Build the sorted list of top_k attribution dicts for one wallet.
    """
    n = len(feature_names)
    total_abs = float(np.sum(np.abs(shap_row))) or 1e-9

    entries = []
    for j in range(min(n, len(shap_row))):
        sv          = float(shap_row[j])
        raw_val     = float(raw_row[j]) if j < len(raw_row) else 0.0
        feature     = feature_names[j]

        # sigma deviation: how many std-devs above/below population mean
        if scaler is not None and hasattr(scaler, "mean_") and j < len(scaler.mean_):
            sigma = (raw_val - float(scaler.mean_[j])) / (float(scaler.scale_[j]) + 1e-9)
        else:
            sigma = 0.0

        entries.append({
            "feature":         feature,
            "label":           FEATURE_LABELS.get(feature, feature),
            "shap_value":      round(sv, 4),
            "feature_value":   round(raw_val, 4),
            "sigma":           round(sigma, 2),
            "direction":       "positive" if sv >= 0 else "negative",
            "pct_contribution": int(round(abs(sv) / total_abs * 100)),
            "_abs_shap":       abs(sv),   # used for sorting, removed before output
        })

    # Sort by absolute SHAP value descending, keep top_k
    entries.sort(key=lambda e: e["_abs_shap"], reverse=True)
    top = entries[:top_k]

    # Remove internal sorting key
    for entry in top:
        entry.pop("_abs_shap", None)

    return top


def _format_reason(attributions: list) -> str:
    """
    Convert top-k attribution list into a single human-readable reason string.

    Example output:
        "+41% risk: transaction velocity (tx/hr)=18.3 (2.4σ above mean, rapid transaction burst).
         +29% risk: distinct ISP/ASN providers=5.0 (1.9σ above mean, multi-provider ISP routing).
         +19% risk: output amount variance=0.87 (1.6σ above mean, irregular output sizing)."
    """
    if not attributions:
        return "Anomaly detected by IsolationForest."

    parts = []
    for attr in attributions:
        direction   = "+" if attr["direction"] == "positive" else "-"
        pct         = attr["pct_contribution"]
        label       = attr["label"]
        val         = attr["feature_value"]
        sigma       = attr["sigma"]
        sigma_dir   = "above" if sigma >= 0 else "below"
        abs_sigma   = abs(sigma)
        feature_key = attr["feature"]

        if attr["direction"] == "positive":
            context = _POSITIVE_CONTEXT.get(feature_key, "elevated activity")
        else:
            context = _NEGATIVE_CONTEXT.get(feature_key, "within normal range")

        parts.append(
            f"{direction}{pct}% risk: {label}={val} "
            f"({abs_sigma:.1f}σ {sigma_dir} mean, {context})"
        )

    return ". ".join(parts) + "."

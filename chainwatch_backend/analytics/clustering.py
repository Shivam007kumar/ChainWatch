"""
analytics/clustering.py
────────────────────────
KMeans wallet clustering — extracted from graph_builder.py.

Generates dynamic, data-derived cluster labels by inspecting centroid
z-scores against the population mean. Labels are built from _FEATURE_DESCRIPTORS
and reflect the dominant behavioural signal in each cluster.

This is separate from anomaly detection: KMeans assigns every wallet to a
cluster; IsolationForest flags a subset as anomalous. The cluster label on
a flagged wallet answers "what type of actor is this?" while the IF detection
answers "is this actor unusual?"
"""
from __future__ import annotations

import logging

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("chainwatch.clustering")

# ── Feature descriptors — ordered to match FEATURE_NAMES (14 features) ────────
_FEATURE_DESCRIPTORS = [
    ("tx_count",                "high-frequency"),
    ("total_volume_btc",        "high-volume"),
    ("unique_ip_count",         "multi-IP"),
    ("tx_velocity",             "burst-velocity"),
    ("amount_variance",         "irregular-amounts"),
    ("unique_asn_count",        "multi-ASN"),
    ("cross_state_ip_ratio",    "cross-jurisdiction"),
    ("avg_output_count",        "high-fan-out"),
    ("avg_src_port",            "high-src-port"),
    ("avg_dst_port",            "non-standard-port"),
    ("dst_src_state_match",     "cross-state-routing"),
    ("script_type_risk_ratio",  "high-risk-scripts"),
    ("balance_violation_ratio", "balance-violations"),
    ("avg_broadcast_confidence","low-confidence-broadcast"),
]


def _label_from_centroid(centroid: np.ndarray, scaler: StandardScaler) -> str:
    """
    Derive a human-readable cluster label from a KMeans centroid.

    Un-scales the centroid to raw feature space, computes z-scores against
    the population mean, and returns a compound label from the top-2 features
    with z > 0.5. Falls back to "Baseline Activity Cluster" if nothing stands out.
    """
    if scaler is None or not hasattr(scaler, "mean_"):
        return "General Activity Cluster"

    raw = scaler.inverse_transform(centroid.reshape(1, -1))[0]
    z   = (raw - scaler.mean_) / (scaler.scale_ + 1e-9)

    ranked = sorted(range(len(z)), key=lambda i: z[i], reverse=True)
    top = [
        _FEATURE_DESCRIPTORS[i][1]
        for i in ranked[:2]
        if i < len(_FEATURE_DESCRIPTORS) and z[i] > 0.5
    ]

    if not top:
        return "Baseline Activity Cluster"
    return " / ".join(top).title() + " Cluster"


def run(
    wallets:   list[str],
    X_scaled:  np.ndarray,
    scaler:    StandardScaler,
    n_clusters: int = 6,
    random_state: int = 42,
    n_init:    int = 10,
) -> dict[str, str]:
    """
    Fit KMeans and return a wallet → cluster_name mapping.

    Parameters
    ----------
    wallets      : ordered wallet addresses (matches rows in X_scaled)
    X_scaled     : StandardScaler-normalised feature matrix
    scaler       : the fitted StandardScaler (for centroid label derivation)
    n_clusters   : number of clusters (capped at len(wallets))
    random_state : reproducibility seed
    n_init       : KMeans initializations

    Returns
    -------
    dict[wallet_address, cluster_label_string]
    """
    if len(wallets) == 0:
        return {}

    k = min(n_clusters, len(wallets))

    kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=n_init)
    labels = kmeans.fit_predict(X_scaled)

    # Build name map from centroids — one label per cluster id
    cluster_name_map = {
        cid: _label_from_centroid(kmeans.cluster_centers_[cid], scaler)
        for cid in range(k)
    }

    return {
        wallets[i]: cluster_name_map[int(labels[i])]
        for i in range(len(wallets))
    }

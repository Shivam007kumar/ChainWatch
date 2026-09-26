"""
services/evidence.py
──────────────────────
Aggregates multiple DetectionResult objects for a single entity into a
ranked Evidence list and a final Alert.

Pipeline position:
  analytics/* → list[DetectionResult]
       ↓
  evidence.py → aggregate_evidence()
       ↓
  list[Evidence] + Alert (ready for Neo4j persistence)

The aggregation logic:
  1. Collect all DetectionResults targeting the same entity_id
  2. Take the max risk_score across all detectors (an entity flagged by
     both IsolationForest AND peeling chain is more suspicious than one
     flagged by either alone)
  3. Build one Evidence item per detector that contributed
  4. Construct a single Alert with stable id and the full evidence list
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from models.domain.alert import Alert, DetectionResult, Evidence, risk_to_severity

logger = logging.getLogger("chainwatch.evidence")


def aggregate_evidence(
    detection_results: list[DetectionResult],
    dataset_id: str,
    sequence_start: int = 1,
) -> list[Alert]:
    """
    Group DetectionResults by entity_id, merge into Alerts.

    Parameters
    ----------
    detection_results : all results from all detectors for one ingest run
    dataset_id        : propagated to every Alert
    sequence_start    : starting sequence number for alert_id generation

    Returns
    -------
    list[Alert] — one per unique entity_id, sorted by risk_score desc
    """
    if not detection_results:
        return []

    # Group by entity_id
    by_entity: dict[str, list[DetectionResult]] = defaultdict(list)
    for dr in detection_results:
        by_entity[dr.entity_id].append(dr)

    alerts: list[Alert] = []
    seq = sequence_start

    for entity_id, detections in by_entity.items():
        # Aggregate risk — take the maximum across all detectors
        max_risk    = max(d.risk_score for d in detections)
        # Primary detector = the one that produced the highest risk_score
        primary     = max(detections, key=lambda d: d.risk_score)
        # Anomaly score from IsolationForest if present
        anomaly_score = next(
            (d.anomaly_score for d in detections if d.anomaly_score is not None),
            None,
        )

        # Build one Evidence item per distinct detector
        seen_detectors: set[str] = set()
        evidence_items: list[Evidence] = []

        for dr in sorted(detections, key=lambda d: d.risk_score, reverse=True):
            if dr.detector in seen_detectors:
                continue
            seen_detectors.add(dr.detector)

            # Extract human-readable title
            title = _detector_title(dr)

            evidence_items.append(Evidence(
                type               = dr.detector,
                title              = title,
                confidence         = dr.confidence,
                risk_contribution  = round(dr.risk_score / max_risk * 100, 1) if max_risk > 0 else 0.0,
                related_entity_ids = [dr.entity_id],
                related_tx_ids     = dr.metadata.get("correlated_txids", []),
                details            = dr.metadata,
            ))

        # Gather risk_factors and SHAP attributions from the primary detector's metadata
        risk_factors      = primary.metadata.get("risk_factors", [])
        shap_attributions = primary.metadata.get("shap_attributions", [])
        correlated_txids  = primary.metadata.get("correlated_txids", [])
        cluster_name      = primary.metadata.get("cluster_name", "")
        primary_state     = primary.metadata.get("primary_state", "Unknown")

        alert = Alert(
            id            = f"ALT-{dataset_id[:8]}-{seq:06d}",
            dataset_id    = dataset_id,
            entity_type   = primary.entity_type,
            entity_id     = entity_id,
            detector      = primary.detector,
            risk_score    = round(max_risk, 1),
            anomaly_score = anomaly_score,
            severity      = risk_to_severity(max_risk),
            evidence      = evidence_items,
            created_at    = datetime.now(timezone.utc).isoformat(),
            status        = "open",
            cluster_name  = cluster_name,
            primary_state = primary_state,
            shap_attributions = shap_attributions,
            risk_factors      = risk_factors,
            correlated_txids  = correlated_txids,
        )
        alerts.append(alert)
        seq += 1

    alerts.sort(key=lambda a: a.risk_score, reverse=True)
    return alerts


def _detector_title(dr: DetectionResult) -> str:
    """Human-readable title for an Evidence item."""
    titles = {
        "isolation_forest": "Isolation Forest anomaly detection",
        "peeling_chain":    f"Peeling chain ({dr.metadata.get('hop_count', '?')}-hop sequence)",
        "coinjoin":         "CoinJoin / mixing transaction",
        "risk_propagation": f"Risk propagation ({dr.metadata.get('distance', '?')}-hop downstream)",
        "ciou":             "Co-spending entity (CIOU heuristic)",
    }
    return titles.get(dr.detector, f"Detection: {dr.detector}")

"""
models/domain/alert.py
────────────────────────
Three distinct domain types in the alert lifecycle:

  DetectionResult — transient, produced per detector run, not persisted directly.
  Evidence        — structured item that supports an alert.
  Alert           — persisted to Neo4j with stable identity; backing store for
                    GET /alerts/{alert_id}.

Key design decisions:
  - risk_score and confidence are SEPARATE fields.
    risk_score  = "how dangerous is this entity?" (0–100)
    anomaly_score = raw IsolationForest decision_function (signed float)
    confidence  = "how certain is the detection?" — only set when
                  mathematically defensible (e.g. broadcast correlation exp(-Δt/τ)).
                  Left None for heuristic detectors (peeling chain, CoinJoin).

  - severity is derived from risk_score:
    critical  ≥ 90
    high      ≥ 70
    medium    ≥ 50
    low       < 50

  - alert_id is deterministic: ALT-{dataset_id[:8]}-{sequence:06d}
    Stable across re-queries; human-readable in logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Risk level helper ──────────────────────────────────────────────────────────

def risk_to_severity(score: float) -> str:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


# ── DetectionResult ────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    """
    Transient output from a single detector run.

    Produced by:
      - analytics/anomaly.py      → detector="isolation_forest"
      - analytics/peeling_chain.py → detector="peeling_chain"
      - analytics/peeling_chain.py → detector="coinjoin"
      - analytics/risk_propagation.py → detector="risk_propagation"
      - analytics/risk_propagation.py → detector="ciou"

    Not persisted directly — fed to services/evidence.py which aggregates
    multiple DetectionResults per wallet into an Alert.
    """
    detector:    str   # "isolation_forest" | "peeling_chain" | "coinjoin" |
                       #  "risk_propagation" | "ciou"
    entity_type: str   # "wallet" | "transaction"
    entity_id:   str   # wallet address, txid, etc.

    risk_score:   float         # 0–100 rescaled
    anomaly_score: Optional[float] = None   # raw IF decision_function; None for rule-based
    confidence:    Optional[float] = None   # only when defensibly computable
    confidence_method: Optional[str] = None # e.g. "broadcast_correlation_exp_decay"

    evidence:  list[dict] = field(default_factory=list)
    metadata:  dict       = field(default_factory=dict)

    @property
    def severity(self) -> str:
        return risk_to_severity(self.risk_score)


# ── Evidence ───────────────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """
    A single structured evidence item supporting an Alert.

    One Alert can have multiple Evidence items from different detectors.
    Persisted as a JSON array property on the (:Alert) node in Neo4j.
    """
    type:              str    # "isolation_forest" | "peeling_chain" | "shap" |
                               # "ciou" | "coinjoin" | "risk_propagation"
    title:             str    # Human-readable summary: "6-hop peeling sequence"
    confidence:        Optional[float] = None
    risk_contribution: float = 0.0

    # IDs of related entities / transactions for drill-down
    related_entity_ids: list[str] = field(default_factory=list)
    related_tx_ids:     list[str] = field(default_factory=list)

    # Free-form structured payload — detector-specific extras
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type":               self.type,
            "title":              self.title,
            "confidence":         self.confidence,
            "risk_contribution":  self.risk_contribution,
            "related_entity_ids": self.related_entity_ids,
            "related_tx_ids":     self.related_tx_ids,
            "details":            self.details,
        }


# ── Alert ──────────────────────────────────────────────────────────────────────

@dataclass
class Alert:
    """
    A persisted forensic alert with stable identity.

    Persisted to Neo4j as a (:Alert) node after each ingest.
    Read back by GET /alerts/{alert_id}.

    alert_id format: ALT-{dataset_id[:8]}-{sequence:06d}
    Example:         ALT-59ef5e16-000001
    """
    id:           str           # ALT-{dataset_id[:8]}-{seq:06d}
    dataset_id:   str

    entity_type:  str           # "wallet" | "transaction"
    entity_id:    str           # wallet address, txid

    detector:     str           # primary triggering detector
    risk_score:   float         # 0–100
    anomaly_score: Optional[float] = None
    severity:     str           = "low"

    evidence:     list[Evidence] = field(default_factory=list)
    created_at:   str            = ""
    status:       str            = "open"   # "open" | "reviewed" | "closed"

    # Additional context copied from the detection
    cluster_name:      str            = ""
    primary_state:     str            = "Unknown"
    shap_attributions: list[dict]     = field(default_factory=list)
    risk_factors:      list[str]      = field(default_factory=list)
    correlated_txids:  list[str]      = field(default_factory=list)

    def to_neo4j_props(self) -> dict:
        """Properties to write to the (:Alert) node."""
        return {
            "id":            self.id,
            "dataset_id":    self.dataset_id,
            "entity_type":   self.entity_type,
            "entity_id":     self.entity_id,
            "detector":      self.detector,
            "risk_score":    self.risk_score,
            "anomaly_score": self.anomaly_score,
            "severity":      self.severity,
            "cluster_name":  self.cluster_name,
            "primary_state": self.primary_state,
            "created_at":    self.created_at,
            "status":        self.status,
            # Store lists as JSON strings since Neo4j doesn't support nested objects
            "evidence_json":     __import__("json").dumps([e.to_dict() for e in self.evidence]),
            "shap_json":         __import__("json").dumps(self.shap_attributions),
            "risk_factors":      self.risk_factors,
            "correlated_txids":  self.correlated_txids,
        }

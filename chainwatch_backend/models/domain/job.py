"""
models/domain/job.py
─────────────────────
IngestionJob and PipelineStage — the domain model for background ingest runs.

LIMITATIONS OF CURRENT IMPLEMENTATION (in-memory JobStore):
  - Job state is lost when the backend restarts.
  - Not safe with uvicorn --workers > 1 (each worker has its own dict).
  - Not horizontally scalable.

The JobStore abstraction (get/set/update_stage) allows replacing the backing
store with Redis or a database later without changing ingestion/pipeline.py
or the API router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PipelineStage(str, Enum):
    QUEUED                = "QUEUED"
    VALIDATING            = "VALIDATING"
    GEOIP_ENRICHMENT      = "GEOIP_ENRICHMENT"
    BROADCAST_CORRELATION = "BROADCAST_CORRELATION"
    FEATURE_ENGINEERING   = "FEATURE_ENGINEERING"
    ANOMALY_DETECTION     = "ANOMALY_DETECTION"
    SHAP                  = "SHAP"
    CLUSTERING            = "CLUSTERING"
    PEELING_DETECTION     = "PEELING_DETECTION"
    COINJOIN_DETECTION    = "COINJOIN_DETECTION"
    RISK_PROPAGATION      = "RISK_PROPAGATION"
    NEO4J_PERSISTENCE     = "NEO4J_PERSISTENCE"
    FINALIZING            = "FINALIZING"
    COMPLETED             = "COMPLETED"
    FAILED                = "FAILED"


# Ordered list used to compute progress percentage
_STAGE_ORDER = [
    PipelineStage.QUEUED,
    PipelineStage.VALIDATING,
    PipelineStage.GEOIP_ENRICHMENT,
    PipelineStage.BROADCAST_CORRELATION,
    PipelineStage.FEATURE_ENGINEERING,
    PipelineStage.ANOMALY_DETECTION,
    PipelineStage.SHAP,
    PipelineStage.CLUSTERING,
    PipelineStage.PEELING_DETECTION,
    PipelineStage.COINJOIN_DETECTION,
    PipelineStage.RISK_PROPAGATION,
    PipelineStage.NEO4J_PERSISTENCE,
    PipelineStage.FINALIZING,
    PipelineStage.COMPLETED,
]


@dataclass
class IngestionJob:
    job_id:            str
    dataset_id:        str
    filename:          str
    status:            PipelineStage = PipelineStage.QUEUED

    records_total:     int = 0
    records_processed: int = 0
    records_skipped:   int = 0

    anomalies_found:          int = 0
    peeling_chains_found:     int = 0
    coinjoin_mixers_found:    int = 0
    propagated_risk_wallets:  int = 0

    started_at:    str = ""
    completed_at:  str = ""
    elapsed_seconds: float = 0.0

    error_message: Optional[str] = None
    warnings:      list[str]     = field(default_factory=list)

    # Track whether the same CSV hash was already ingested
    duplicate: bool = False

    @property
    def progress_pct(self) -> int:
        """0–100 based on stage position in the ordered pipeline."""
        try:
            pos   = _STAGE_ORDER.index(self.status)
            total = len(_STAGE_ORDER) - 1   # exclude COMPLETED from denominator
            return min(int(pos / total * 100), 99)   # never show 100 until COMPLETED
        except ValueError:
            return 0

    def to_dict(self) -> dict:
        return {
            "job_id":                   self.job_id,
            "dataset_id":               self.dataset_id,
            "filename":                 self.filename,
            "status":                   self.status.value,
            "stage":                    self.status.value,
            "progress":                 100 if self.status == PipelineStage.COMPLETED else self.progress_pct,
            "records_total":            self.records_total,
            "records_processed":        self.records_processed,
            "records_skipped":          self.records_skipped,
            "anomalies_found":          self.anomalies_found,
            "peeling_chains_found":     self.peeling_chains_found,
            "coinjoin_mixers_found":    self.coinjoin_mixers_found,
            "propagated_risk_wallets":  self.propagated_risk_wallets,
            "started_at":               self.started_at,
            "completed_at":             self.completed_at,
            "elapsed_seconds":          round(self.elapsed_seconds, 2),
            "error_message":            self.error_message,
            "warnings":                 self.warnings,
            "duplicate":                self.duplicate,
        }

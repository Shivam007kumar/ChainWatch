"""
ingestion/jobs.py
──────────────────
JobStore — in-memory job registry for the single-process demo deployment.

LIMITATIONS (documented explicitly per plan):
  - Job state lost on backend restart.
  - Not safe with uvicorn --workers > 1.
  - Not horizontally scalable.

The get/set/update_stage interface is intentionally thin so it can be
replaced with a Redis or SQLite backing store later without touching
ingestion/pipeline.py or the API router.
"""
from __future__ import annotations

import threading
from typing import Optional

from models.domain.job import IngestionJob, PipelineStage

# ── Module-level singleton ─────────────────────────────────────────────────────
_store:  dict[str, IngestionJob] = {}
_lock:   threading.Lock          = threading.Lock()

# Recent dataset hashes — used to detect duplicate uploads
_seen_dataset_ids: set[str] = set()


class JobStore:
    """
    Thin abstraction over the in-memory job dict.
    Instantiate once and inject wherever needed, or use the module-level
    singleton `job_store` defined at the bottom of this file.
    """

    def create(self, job: IngestionJob) -> str:
        """Register a new job. Returns the job_id."""
        with _lock:
            _store[job.job_id] = job
        return job.job_id

    def get(self, job_id: str) -> Optional[IngestionJob]:
        return _store.get(job_id)

    def update(self, job: IngestionJob) -> None:
        with _lock:
            _store[job.job_id] = job

    def update_stage(
        self,
        job_id: str,
        stage: PipelineStage,
        **kwargs,
    ) -> None:
        """
        Atomically update a job's stage and any additional scalar fields.
        kwargs keys must match IngestionJob field names.
        """
        with _lock:
            job = _store.get(job_id)
            if job is None:
                return
            job.status = stage
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

    def list_recent(self, limit: int = 20) -> list[IngestionJob]:
        """Returns the most recently created jobs (insertion order, newest last)."""
        jobs = list(_store.values())
        return jobs[-limit:]

    def mark_dataset_seen(self, dataset_id: str) -> bool:
        """
        Returns True if this dataset_id was already ingested (duplicate),
        False if it is new. Always records the dataset_id.
        """
        with _lock:
            if dataset_id in _seen_dataset_ids:
                return True
            _seen_dataset_ids.add(dataset_id)
            return False


# ── Module-level singleton used by pipeline.py and api/ingestion.py ───────────
job_store = JobStore()

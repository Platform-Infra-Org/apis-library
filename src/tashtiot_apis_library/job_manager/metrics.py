"""Prometheus metrics for the job manager (on the default registry, exposed via ``/metrics``)."""

from prometheus_client import Counter, Gauge, Histogram

__all__ = ["JOBS_TOTAL", "JOBS_INFLIGHT", "JOB_DURATION"]

JOBS_TOTAL = Counter("jm_jobs_total", "Jobs by terminal status.", ["status"])
JOBS_INFLIGHT = Gauge("jm_jobs_inflight", "Jobs currently executing in this worker.")
JOB_DURATION = Histogram("jm_job_duration_seconds", "Job execution time (lock-to-terminal).")

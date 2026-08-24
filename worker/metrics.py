import os
import logging
from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger("worker.metrics")

# --- Worker Metrics ---
WORKER_JOBS_CLAIMED_TOTAL = Counter(
    "worker_jobs_claimed_total",
    "Total jobs claimed by this worker process"
)

WORKER_JOBS_STARTED_TOTAL = Counter(
    "worker_jobs_started_total",
    "Total jobs started execution by this worker process"
)

WORKER_JOBS_COMPLETED_TOTAL = Counter(
    "worker_jobs_completed_total",
    "Total jobs successfully completed by this worker process"
)

WORKER_JOBS_FAILED_TOTAL = Counter(
    "worker_jobs_failed_total",
    "Total jobs failed during execution by this worker process"
)

WORKER_JOBS_EXECUTION_DURATION_SECONDS = Histogram(
    "worker_jobs_execution_duration_seconds",
    "Worker task execution processing duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

WORKER_ACTIVE_JOBS = Gauge(
    "worker_active_jobs",
    "Current active jobs executing in worker process"
)

WORKER_CONCURRENCY_LIMIT = Gauge(
    "worker_concurrency_limit",
    "Configured maximum concurrency limit of this worker process"
)

WORKER_CAPACITY_RATIO = Gauge(
    "worker_capacity_ratio",
    "Active tasks / max concurrency capacity ratio"
)

WORKER_HEARTBEAT_TOTAL = Counter(
    "worker_heartbeat_total",
    "Total heartbeats sent from worker to backend"
)

WORKER_POLL_REQUESTS_TOTAL = Counter(
    "worker_poll_requests_total",
    "Total polling attempts made to backend"
)

WORKER_POLL_EMPTY_TOTAL = Counter(
    "worker_poll_empty_total",
    "Total poll attempts that returned no job"
)

WORKER_SHUTDOWNS_TOTAL = Counter(
    "worker_shutdowns_total",
    "Total graceful worker shutdowns"
)


def start_worker_prometheus_server(port: int | None = None) -> None:
    """Starts the Prometheus HTTP server for worker metrics scraping."""
    if port is None:
        port = int(os.getenv("PROMETHEUS_METRICS_PORT", "9100"))
    try:
        start_http_server(port)
        logger.info(f"Worker Prometheus metrics server started on port {port}")
    except Exception as e:
        logger.warning(f"Could not start worker Prometheus metrics server on port {port}: {e}")

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("prometheus")

# --- HTTP Request Metrics ---
HTTP_REQUESTS_TOTAL = Counter(
    "scheduler_http_requests_total",
    "Total HTTP requests handled by FastAPI backend",
    ["method", "route", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "scheduler_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# --- Job Lifecycle Counters ---
JOBS_SUBMITTED_TOTAL = Counter(
    "scheduler_jobs_submitted_total",
    "Total jobs submitted to the scheduler"
)

JOBS_CLAIMED_TOTAL = Counter(
    "scheduler_jobs_claimed_total",
    "Total jobs successfully claimed by worker processes"
)

JOBS_STARTED_TOTAL = Counter(
    "scheduler_jobs_started_total",
    "Total jobs started execution on workers"
)

JOBS_COMPLETED_TOTAL = Counter(
    "scheduler_jobs_completed_total",
    "Total jobs successfully completed"
)

JOBS_FAILED_TOTAL = Counter(
    "scheduler_jobs_failed_total",
    "Total job execution attempts failed"
)

JOBS_RETRIED_TOTAL = Counter(
    "scheduler_jobs_retried_total",
    "Total job failures that resulted in a retry attempt"
)

JOBS_DEAD_LETTERED_TOTAL = Counter(
    "scheduler_jobs_dead_lettered_total",
    "Total jobs moved to dead letter queue after retry exhaustion"
)

JOBS_RECOVERED_TOTAL = Counter(
    "scheduler_jobs_recovered_total",
    "Total expired job leases recovered by reaper"
)

JOBS_SCHEDULED_TOTAL = Counter(
    "scheduler_jobs_scheduled_total",
    "Total cron or scheduled jobs generated/promoted"
)

# --- Job Execution Duration Histogram ---
JOBS_EXECUTION_DURATION_SECONDS = Histogram(
    "scheduler_jobs_execution_duration_seconds",
    "Job execution processing duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

# --- Job State Gauges (reconstructed from DB) ---
JOBS_CURRENT = Gauge(
    "scheduler_jobs_current",
    "Current count of jobs in PostgreSQL by status",
    ["status"]
)

QUEUE_JOBS = Gauge(
    "scheduler_queue_jobs",
    "Current count of jobs per queue and status",
    ["queue", "status"]
)

QUEUE_UTILIZATION_RATIO = Gauge(
    "scheduler_queue_utilization_ratio",
    "Queue active jobs / concurrency limit ratio",
    ["queue"]
)

QUEUE_CAPACITY = Gauge(
    "scheduler_queue_capacity",
    "Queue concurrency limit capacity",
    ["queue"]
)

# --- Worker Gauges ---
WORKERS_TOTAL = Gauge(
    "scheduler_workers_total",
    "Total registered worker nodes in database"
)

WORKERS_ACTIVE = Gauge(
    "scheduler_workers_active",
    "Current active worker nodes based on heartbeat"
)

WORKER_HEARTBEAT_AGE_SECONDS = Gauge(
    "scheduler_worker_heartbeat_age_seconds",
    "Seconds since last heartbeat per worker",
    ["worker"]
)

WORKER_JOBS_ACTIVE = Gauge(
    "scheduler_worker_jobs_active",
    "Current active running/claimed jobs per worker",
    ["worker"]
)

WORKER_CAPACITY_RATIO = Gauge(
    "scheduler_worker_capacity_ratio",
    "Worker utilization ratio (active / max concurrency)",
    ["worker"]
)

# --- Retry & DLQ Metrics ---
JOB_RETRY_ATTEMPTS_TOTAL = Counter(
    "scheduler_job_retry_attempts_total",
    "Total retry attempts grouped by retry strategy",
    ["strategy"]
)

JOB_RETRY_WAITING = Gauge(
    "scheduler_job_retry_waiting",
    "Current jobs waiting in RETRY_WAITING status"
)

JOB_RETRY_DELAY_SECONDS = Histogram(
    "scheduler_job_retry_delay_seconds",
    "Calculated retry backoff delay in seconds",
    buckets=(1, 5, 15, 30, 60, 300, 900, 3600)
)

DEAD_LETTER_JOBS_TOTAL = Counter(
    "scheduler_dead_letter_jobs_total",
    "Total dead letter jobs created"
)

DEAD_LETTER_CURRENT = Gauge(
    "scheduler_dead_letter_current",
    "Current count of dead letter jobs in database"
)

# --- Scheduler & Reaper Operational Metrics ---
SCHEDULED_JOBS_PROCESSED_TOTAL = Counter(
    "scheduler_scheduled_jobs_processed_total",
    "Total scheduled jobs promoted to QUEUED"
)

SCHEDULER_RUNS_TOTAL = Counter(
    "scheduler_scheduler_runs_total",
    "Total scheduler evaluation runs"
)

SCHEDULER_ERRORS_TOTAL = Counter(
    "scheduler_scheduler_errors_total",
    "Total scheduler errors encountered"
)

REAPER_RUNS_TOTAL = Counter(
    "scheduler_reaper_runs_total",
    "Total reaper evaluation runs"
)

REAPER_JOBS_RECOVERED_TOTAL = Counter(
    "scheduler_reaper_jobs_recovered_total",
    "Total expired job leases recovered by reaper"
)

REAPER_WORKERS_MARKED_INACTIVE_TOTAL = Counter(
    "scheduler_reaper_workers_marked_inactive_total",
    "Total stale worker nodes marked INACTIVE by reaper"
)

REAPER_ERRORS_TOTAL = Counter(
    "scheduler_reaper_errors_total",
    "Total reaper loop errors encountered"
)

# --- Platform Operations Metrics ---
BATCH_SUBMISSIONS_TOTAL = Counter(
    "scheduler_batch_submissions_total",
    "Total batch job submissions created"
)

BATCH_JOBS_TOTAL = Counter(
    "scheduler_batch_jobs_total",
    "Total jobs created as part of batch submissions"
)

BATCH_FAILURES_TOTAL = Counter(
    "scheduler_batch_failures_total",
    "Total batch job failures"
)

DEPENDENCY_BLOCKS_TOTAL = Counter(
    "scheduler_dependency_blocks_total",
    "Total job dependency block constraints created"
)

DEPENDENCY_CYCLES_REJECTED_TOTAL = Counter(
    "scheduler_dependency_cycles_rejected_total",
    "Total job dependency cycles rejected by DAG validation"
)

RATE_LIMIT_ALLOWED_TOTAL = Counter(
    "scheduler_rate_limit_allowed_total",
    "Total API requests allowed by rate limiter"
)

RATE_LIMIT_REJECTED_TOTAL = Counter(
    "scheduler_rate_limit_rejected_total",
    "Total API requests rejected by rate limiter",
    ["endpoint"]
)

FAILURE_ANALYSES_GENERATED_TOTAL = Counter(
    "scheduler_failure_analyses_generated_total",
    "Total failure diagnostic summaries generated"
)


def update_db_state_gauges(db: Session) -> None:
    """
    Queries PostgreSQL for current job states, queue capacity/utilization, worker readiness,
    and dead letter count, updating Prometheus gauges so state remains fully accurate across restarts.
    """
    try:
        from backend.app.models import Job, Queue, Worker, DeadLetterJob
        now = datetime.now(timezone.utc)

        # 1. Job counts by status
        status_counts = dict(
            db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
        )
        all_statuses = ["QUEUED", "CLAIMED", "RUNNING", "COMPLETED", "FAILED", "RETRY_WAITING", "SCHEDULED", "DEAD_LETTER"]
        for st in all_statuses:
            JOBS_CURRENT.labels(status=st).set(status_counts.get(st, 0))

        JOB_RETRY_WAITING.set(status_counts.get("RETRY_WAITING", 0))

        # 2. Dead Letter Count
        dlq_count = db.query(func.count(DeadLetterJob.id)).scalar() or 0
        DEAD_LETTER_CURRENT.set(dlq_count)

        # 3. Queues utilization
        queues = db.query(Queue).all()
        for q in queues:
            q_name = q.name
            cap = q.concurrency_limit or 1
            QUEUE_CAPACITY.labels(queue=q_name).set(cap)

            # Count queued & running for this queue
            q_status_counts = dict(
                db.query(Job.status, func.count(Job.id))
                .filter(Job.queue_id == q.id)
                .group_by(Job.status)
                .all()
            )
            for st in ["QUEUED", "RUNNING", "CLAIMED", "COMPLETED", "FAILED"]:
                QUEUE_JOBS.labels(queue=q_name, status=st).set(q_status_counts.get(st, 0))

            active_q_jobs = q_status_counts.get("RUNNING", 0) + q_status_counts.get("CLAIMED", 0)
            util_ratio = round(active_q_jobs / cap, 4) if cap > 0 else 0.0
            QUEUE_UTILIZATION_RATIO.labels(queue=q_name).set(util_ratio)

        # 4. Workers readiness
        workers = db.query(Worker).all()
        WORKERS_TOTAL.set(len(workers))
        active_count = 0

        for w in workers:
            w_name = w.hostname or str(w.id)[:8]
            hb = w.last_heartbeat_at
            if hb and hb.tzinfo is None:
                hb = hb.replace(tzinfo=timezone.utc)
            age = (now - hb).total_seconds() if hb else 9999.0
            WORKER_HEARTBEAT_AGE_SECONDS.labels(worker=w_name).set(round(age, 1))

            if w.status == "ACTIVE" and age <= 60.0:
                active_count += 1

            # Worker active jobs
            w_active_jobs = db.query(func.count(Job.id)).filter(
                Job.claimed_by_worker_id == w.id,
                Job.status.in_(["CLAIMED", "RUNNING"])
            ).scalar() or 0
            WORKER_JOBS_ACTIVE.labels(worker=w_name).set(w_active_jobs)

            max_conc = getattr(w, "max_concurrency", 5) or 5
            w_ratio = round(w_active_jobs / max_conc, 4) if max_conc > 0 else 0.0
            WORKER_CAPACITY_RATIO.labels(worker=w_name).set(w_ratio)


        WORKERS_ACTIVE.set(active_count)

    except Exception as e:
        logger.warning(f"Error updating DB state gauges: {e}")


def get_prometheus_metrics(db: Session) -> bytes:
    """Updates database gauges and returns standard Prometheus text format payload."""
    update_db_state_gauges(db)
    return generate_latest()

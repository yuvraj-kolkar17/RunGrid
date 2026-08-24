import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.app.models import Worker, Job, JobExecution, JobLog, DeadLetterJob, RetryPolicy
from backend.app.services.retry import calculate_delay

def reap_stale_workers_and_jobs(db: Session, heartbeat_timeout_seconds: int = 30) -> tuple[int, int]:
    """Reaps dead workers and recovers their expired leases."""
    from backend.app.core.prometheus_metrics import (
        REAPER_RUNS_TOTAL, REAPER_ERRORS_TOTAL, REAPER_JOBS_RECOVERED_TOTAL,
        REAPER_WORKERS_MARKED_INACTIVE_TOTAL, JOBS_RECOVERED_TOTAL
    )
    REAPER_RUNS_TOTAL.inc()
    
    try:
        now = datetime.now(timezone.utc)
        timeout_limit = now - timedelta(seconds=heartbeat_timeout_seconds)
        
        # 1. Identify and mark stale workers as INACTIVE
        stale_workers = db.query(Worker).filter(
            Worker.status == "ACTIVE",
            Worker.last_heartbeat_at < timeout_limit
        ).with_for_update().all()
        
        num_workers_reaped = len(stale_workers)
        for worker in stale_workers:
            worker.status = "INACTIVE"
            worker.updated_at = now
        db.flush()
        
        # Get active/inactive worker ids for identification
        inactive_worker_ids = [w_id for (w_id,) in db.query(Worker.id).filter(Worker.status == "INACTIVE").all()]
        
        # 2. Identify expired job leases
        expired_jobs = db.query(Job).filter(
            Job.status.in_(["CLAIMED", "RUNNING"]),
            (Job.lease_expires_at < now) | Job.claimed_by_worker_id.in_(inactive_worker_ids)
        ).with_for_update().all()
        
        num_jobs_reaped = len(expired_jobs)
        for job in expired_jobs:
            # Case 1: Expired in CLAIMED state (never actually started executing)
            if job.status == "CLAIMED":
                job.status = "QUEUED"
                job.claimed_by_worker_id = None
                job.claimed_at = None
                job.lease_expires_at = None
                job.available_at = now
                job.updated_at = now
                
                log = JobLog(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    log_level="WARNING",
                    message="Worker lease expired in CLAIMED state. Job requeued with attempt count preserved."
                )
                db.add(log)
                
            # Case 2: Expired in RUNNING state (worker crashed during execution)
            elif job.status == "RUNNING":
                # Close latest RUNNING execution
                execution = db.query(JobExecution).filter(
                    JobExecution.job_id == job.id,
                    JobExecution.status == "RUNNING"
                ).order_by(JobExecution.started_at.desc()).first()
                
                if execution:
                    execution.status = "FAILED"
                    execution.error = "Worker lease expired (heartbeat timeout/crash)"
                    execution.finished_at = now
                    
                # If attempt exceeds or equals max_retries, dead letter it
                if job.attempt >= job.max_retries:
                    job.status = "DEAD_LETTER"
                    job.claimed_by_worker_id = None
                    job.lease_expires_at = None
                    job.updated_at = now
                    
                    dlq_job = DeadLetterJob(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        queue_id=job.queue_id,
                        original_payload=job.payload,
                        failure_reason="Execution lease expired and max retries reached.",
                        moved_at=now
                    )
                    db.add(dlq_job)
                    
                    log = JobLog(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        execution_id=execution.id if execution else None,
                        log_level="ERROR",
                        message=f"Lease expired in RUNNING state. Max retries reached ({job.attempt}/{job.max_retries}). Moved to Dead Letter Queue."
                    )
                    db.add(log)
                else:
                    # Calculate backoff delay
                    delay = 5  # Fallback
                    if job.retry_policy_id:
                        policy = db.query(RetryPolicy).filter(RetryPolicy.id == job.retry_policy_id).first()
                        if policy:
                            delay = calculate_delay(policy.strategy, policy.base_delay, job.attempt)
                            
                    job.status = "RETRY_WAITING"
                    job.available_at = now + timedelta(seconds=delay)
                    job.claimed_by_worker_id = None
                    job.lease_expires_at = None
                    job.updated_at = now
                    
                    log = JobLog(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        execution_id=execution.id if execution else None,
                        log_level="WARNING",
                        message=f"Lease expired in RUNNING state. Scheduled for retry in {delay}s. Attempt {job.attempt}/{job.max_retries} preserved."
                    )
                    db.add(log)
                    
        db.flush()

        if num_workers_reaped > 0:
            REAPER_WORKERS_MARKED_INACTIVE_TOTAL.inc(num_workers_reaped)
        if num_jobs_reaped > 0:
            REAPER_JOBS_RECOVERED_TOTAL.inc(num_jobs_reaped)
            JOBS_RECOVERED_TOTAL.inc(num_jobs_reaped)

        return num_workers_reaped, num_jobs_reaped
    except Exception as e:
        REAPER_ERRORS_TOTAL.inc()
        raise e


import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models import Job, JobExecution, JobLog, DeadLetterJob, RetryPolicy
from backend.app.services.retry import calculate_delay

def start_job(db: Session, job_id: uuid.UUID, worker_id: uuid.UUID, lease_duration_seconds: int = 30) -> Job:
    """Transition a job from CLAIMED or QUEUED to RUNNING, incrementing attempts and setting started times."""
    job = db.query(Job).filter(Job.id == job_id).with_for_update().first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    if job.status not in ("CLAIMED", "QUEUED"):
        if job.status == "RUNNING":
            raise ValueError(f"Already started: Job {job_id} is in state RUNNING.")
        raise ValueError(f"Cannot start job {job_id} in state {job.status}. Expected CLAIMED or QUEUED.")

    if job.claimed_by_worker_id is not None and job.claimed_by_worker_id != worker_id:
        raise ValueError(f"Worker mismatch: worker {worker_id} does not own claimed job {job_id}")

    job.claimed_by_worker_id = worker_id


        
    now = datetime.now(timezone.utc)
    job.status = "RUNNING"
    job.attempt += 1
    job.started_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
    job.updated_at = now
    
    # Track the execution
    execution = JobExecution(
        id=uuid.uuid4(),
        job_id=job.id,
        worker_id=worker_id,
        status="RUNNING",
        attempt=job.attempt,
        started_at=now
    )
    db.add(execution)
    db.flush()
    
    # Audit log
    log = JobLog(
        id=uuid.uuid4(),
        job_id=job.id,
        execution_id=execution.id,
        log_level="INFO",
        message=f"Job started execution on worker {worker_id}. Attempt {job.attempt}."
    )
    db.add(log)

    from backend.app.core.prometheus_metrics import JOBS_STARTED_TOTAL
    JOBS_STARTED_TOTAL.inc()
    
    return job


def complete_job(db: Session, job_id: uuid.UUID, worker_id: Optional[uuid.UUID] = None, result: Optional[dict] = None) -> Job:
    """Transition a job from RUNNING/CLAIMED to COMPLETED."""
    job = db.query(Job).filter(Job.id == job_id).with_for_update().first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    if job.status not in ("CLAIMED", "RUNNING"):
        if job.status == "COMPLETED":
            raise ValueError(f"Already completed: Job {job_id} is in state COMPLETED.")
        raise ValueError(f"Cannot complete job {job_id} in state {job.status}. Expected CLAIMED or RUNNING.")
    if worker_id is not None and job.claimed_by_worker_id != worker_id:
        raise ValueError(f"Worker mismatch: worker {worker_id} does not own job {job_id}")


        
    now = datetime.now(timezone.utc)
    job.status = "COMPLETED"
    job.completed_at = now
    job.result = result
    job.updated_at = now
    job.claimed_by_worker_id = None
    job.lease_expires_at = None
    
    # Close latest RUNNING execution
    execution = db.query(JobExecution).filter(
        JobExecution.job_id == job.id,
        JobExecution.status == "RUNNING"
    ).order_by(JobExecution.started_at.desc()).first()
    
    if execution:
        execution.status = "COMPLETED"
        execution.finished_at = now
        st = execution.started_at
        if st:
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            duration = max(0.0, (now - st).total_seconds())
            from backend.app.core.prometheus_metrics import JOBS_EXECUTION_DURATION_SECONDS
            JOBS_EXECUTION_DURATION_SECONDS.observe(duration)
        
    # Audit log
    log = JobLog(
        id=uuid.uuid4(),
        job_id=job.id,
        execution_id=execution.id if execution else None,
        log_level="INFO",
        message="Job completed successfully."
    )
    db.add(log)

    from backend.app.core.prometheus_metrics import JOBS_COMPLETED_TOTAL
    JOBS_COMPLETED_TOTAL.inc()
    
    return job

def fail_job(db: Session, job_id: uuid.UUID, error_message: str, worker_id: Optional[uuid.UUID] = None) -> Job:
    """Fail a job from RUNNING/CLAIMED, triggering retry backoffs or dead-letter queueing."""
    job = db.query(Job).filter(Job.id == job_id).with_for_update().first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    if job.status not in ("CLAIMED", "RUNNING"):
        if job.status in ("FAILED", "RETRY_WAITING", "DEAD_LETTER"):
            raise ValueError(f"Already failed: Job {job_id} is in state {job.status}.")
        raise ValueError(f"Cannot fail job {job_id} in state {job.status}. Expected CLAIMED or RUNNING.")
    if worker_id is not None and job.claimed_by_worker_id != worker_id:
        raise ValueError(f"Worker mismatch: worker {worker_id} does not own job {job_id}")

    now = datetime.now(timezone.utc)
    job.failed_at = now
    job.error = error_message
    job.updated_at = now
    
    # Close latest RUNNING execution if any
    execution = db.query(JobExecution).filter(
        JobExecution.job_id == job.id,
        JobExecution.status == "RUNNING"
    ).order_by(JobExecution.started_at.desc()).first()
    
    if execution:
        execution.status = "FAILED"
        execution.error = error_message
        execution.finished_at = now
        st = execution.started_at
        if st:
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            duration = max(0.0, (now - st).total_seconds())
            from backend.app.core.prometheus_metrics import JOBS_EXECUTION_DURATION_SECONDS
            JOBS_EXECUTION_DURATION_SECONDS.observe(duration)
        
    from backend.app.core.prometheus_metrics import (
        JOBS_FAILED_TOTAL, JOBS_DEAD_LETTERED_TOTAL, DEAD_LETTER_JOBS_TOTAL,
        JOBS_RETRIED_TOTAL, JOB_RETRY_ATTEMPTS_TOTAL, JOB_RETRY_DELAY_SECONDS
    )
    JOBS_FAILED_TOTAL.inc()

    # Determine next state
    if job.attempt >= job.max_retries:
        job.status = "DEAD_LETTER"
        job.claimed_by_worker_id = None
        job.lease_expires_at = None
        
        # Move to Dead Letter
        dlq_job = DeadLetterJob(
            id=uuid.uuid4(),
            job_id=job.id,
            queue_id=job.queue_id,
            original_payload=job.payload,
            failure_reason=error_message,
            moved_at=now
        )
        db.add(dlq_job)
        
        # Audit log
        log = JobLog(
            id=uuid.uuid4(),
            job_id=job.id,
            execution_id=execution.id if execution else None,
            log_level="ERROR",
            message=f"Job failed and moved to Dead Letter Queue. Attempt {job.attempt}/{job.max_retries}. Error: {error_message}"
        )
        db.add(log)

        JOBS_DEAD_LETTERED_TOTAL.inc()
        DEAD_LETTER_JOBS_TOTAL.inc()
    else:
        # Calculate backoff delay
        delay = 5  # Default fallback
        strategy_name = "default"
        if job.retry_policy_id:
            policy = db.query(RetryPolicy).filter(RetryPolicy.id == job.retry_policy_id).first()
            if policy:
                strategy_name = policy.strategy
                delay = calculate_delay(policy.strategy, policy.base_delay, job.attempt)
                
        job.status = "RETRY_WAITING"
        job.available_at = now + timedelta(seconds=delay)
        job.claimed_by_worker_id = None
        job.lease_expires_at = None
        
        # Audit log
        log = JobLog(
            id=uuid.uuid4(),
            job_id=job.id,
            execution_id=execution.id if execution else None,
            log_level="WARNING",
            message=f"Job execution failed. Scheduled for retry in {delay}s. Attempt {job.attempt}/{job.max_retries}. Error: {error_message}"
        )
        db.add(log)

        JOBS_RETRIED_TOTAL.inc()
        JOB_RETRY_ATTEMPTS_TOTAL.labels(strategy=strategy_name).inc()
        JOB_RETRY_DELAY_SECONDS.observe(delay)
        
    return job


def retry_job(db: Session, job_id: uuid.UUID) -> Job:
    """Transition a job from FAILED/DEAD_LETTER back to QUEUED for manual retry."""
    job = db.query(Job).filter(Job.id == job_id).with_for_update().first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
        
    if job.status not in ("FAILED", "DEAD_LETTER"):
        raise ValueError(f"Cannot retry job {job_id} in state {job.status}. Expected FAILED or DEAD_LETTER.")
        
    now = datetime.now(timezone.utc)
    
    # If it was in dead letter queue, remove it
    if job.status == "DEAD_LETTER":
        db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job.id).delete()
        
    job.status = "QUEUED"
    job.attempt = 0
    job.available_at = now
    job.error = None
    job.failed_at = None
    job.result = None
    job.claimed_by_worker_id = None
    job.claimed_at = None
    job.started_at = None
    job.completed_at = None
    job.lease_expires_at = None
    job.updated_at = now
    
    # Audit log
    log = JobLog(
        id=uuid.uuid4(),
        job_id=job.id,
        log_level="INFO",
        message="Job manually reset and queued for execution."
    )
    db.add(log)
    
    return job


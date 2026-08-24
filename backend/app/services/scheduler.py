import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from croniter import croniter  # type: ignore[import-untyped]
from backend.app.models import ScheduledJob, Job, JobLog

def initialize_scheduled_job(sj: ScheduledJob, start_time: Optional[datetime] = None) -> None:
    """Initialize next_run_at for a scheduled job based on its cron expression."""
    if not start_time:
        start_time = datetime.now(timezone.utc)
    try:
        # croniter expects start_time, let's make sure it's timezone-aware if possible,
        # but croniter works best with naive or aware datetimes.
        # We ensure it's timezone-aware.
        itr = croniter(sj.cron_expression, start_time)
        sj.next_run_at = itr.get_next(datetime).replace(tzinfo=timezone.utc)
    except Exception:
        sj.is_active = False
        raise ValueError(f"Invalid cron expression: {sj.cron_expression}")

def run_scheduler_cycle(db: Session) -> int:
    """Processes due recurring cron jobs and creates concrete job instances.
    
    Returns the number of jobs generated.
    """
    from backend.app.core.prometheus_metrics import (
        SCHEDULER_RUNS_TOTAL, SCHEDULER_ERRORS_TOTAL,
        SCHEDULED_JOBS_PROCESSED_TOTAL, JOBS_SCHEDULED_TOTAL
    )
    SCHEDULER_RUNS_TOTAL.inc()
    
    try:
        now = datetime.now(timezone.utc)
        
        # Query active scheduled jobs that are due, locking them to prevent concurrent double-scheduling
        due_jobs = db.query(ScheduledJob).filter(
            ScheduledJob.is_active == True,
            (ScheduledJob.next_run_at <= now) | (ScheduledJob.next_run_at == None)
        ).with_for_update(skip_locked=True).all()
        
        jobs_created = 0
        for sj in due_jobs:
            # Determine the run time
            run_time = sj.next_run_at or now
            
            # Create the concrete job
            job = Job(
                id=uuid.uuid4(),
                queue_id=sj.queue_id,
                status="QUEUED",
                payload=sj.payload,
                scheduled_at=run_time,
                available_at=run_time,
                created_at=now,
                updated_at=now
            )
            db.add(job)
            
            # Calculate next execution time using croniter
            try:
                base_time = max(run_time, now)
                itr = croniter(sj.cron_expression, base_time)
                next_run = itr.get_next(datetime).replace(tzinfo=timezone.utc)
                sj.last_run_at = run_time
                sj.next_run_at = next_run
                sj.updated_at = now
                
                db.flush()
                
                # Log the schedule execution
                log = JobLog(
                    id=uuid.uuid4(),
                    job_id=job.id,
                    log_level="INFO",
                    message=f"Concrete job generated from recurring schedule '{sj.name}' (cron: {sj.cron_expression})."
                )
                db.add(log)
                jobs_created += 1
            except Exception:
                # If cron calculation fails, disable the recurring job
                sj.is_active = False
                db.flush()
                
        if jobs_created > 0:
            SCHEDULED_JOBS_PROCESSED_TOTAL.inc(jobs_created)
            JOBS_SCHEDULED_TOTAL.inc(jobs_created)
            
        return jobs_created
    except Exception as e:
        SCHEDULER_ERRORS_TOTAL.inc()
        raise e

def process_delayed_jobs(db: Session) -> int:
    """Finds all SCHEDULED and RETRY_WAITING jobs that have become available and moves them to QUEUED status.
    
    Returns the number of jobs transitioned.
    """
    now = datetime.now(timezone.utc)
    
    # Query due scheduled/retry jobs and lock them
    due_jobs = db.query(Job).filter(
        Job.status.in_(["SCHEDULED", "RETRY_WAITING"]),
        Job.available_at <= now
    ).with_for_update(skip_locked=True).all()
    
    moved_count = 0
    for job in due_jobs:
        old_status = job.status
        job.status = "QUEUED"
        job.updated_at = now
        
        log = JobLog(
            id=uuid.uuid4(),
            job_id=job.id,
            log_level="INFO",
            message=f"Job became due and was moved from {old_status} to QUEUED."
        )
        db.add(log)
        moved_count += 1
        
    db.flush()
    return moved_count




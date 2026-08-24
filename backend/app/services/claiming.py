import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models import Queue, Job, JobLog, Worker, JobDependency

def would_create_cycle(db: Session, job_id: uuid.UUID, depends_on_job_id: uuid.UUID) -> bool:
    """BFS check to ensure adding (job_id depends on depends_on_job_id) does not create a cycle."""
    if job_id == depends_on_job_id:
        return True
    
    visited = set()
    queue = [depends_on_job_id]
    
    while queue:
        curr = queue.pop(0)
        if curr == job_id:
            return True
        if curr in visited:
            continue
        visited.add(curr)
        
        parents = db.query(JobDependency.depends_on_job_id).filter(JobDependency.job_id == curr).all()
        for p in parents:
            queue.append(p[0])
            
    return False

def claim_job(db: Session, worker_id: uuid.UUID, lease_duration_seconds: int = 30) -> Optional[Job]:
    """Atomic polling service that dynamically selects and claims a job from the best available queue.
    
    Implements:
    - Queue priority scanning (highest priority first).
    - Queue row-level locking (FOR UPDATE SKIP LOCKED) to serialize concurrency checks per queue.
    - Concurrency limit verification (active CLAIMED/RUNNING jobs vs concurrency_limit).
    - Job priority selection (FOR UPDATE SKIP LOCKED) to claim the next eligible job.
    - Zero global locks: concurrent queries on different queues can proceed in parallel.
    """
    # 1. Verify worker exists and is active
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        # For testing purposes, we can auto-register workers if they don't exist yet, 
        # but let's raise an error or handle it.
        raise ValueError(f"Worker {worker_id} not registered")
        
    if worker.status != "ACTIVE":
        raise ValueError(f"Worker {worker_id} is INACTIVE")
        
    # Update worker heartbeat
    worker.last_heartbeat_at = datetime.now(timezone.utc)
    db.flush()

    # 2. Query active, unpaused queues in priority order
    queues = db.query(Queue.id).filter(Queue.is_paused == False).order_by(Queue.priority.desc()).all()
    
    for (queue_id,) in queues:
        # Start nested subtransaction (Savepoint)
        nested = db.begin_nested()
        try:
            # 3. Try to lock the queue row (FOR UPDATE SKIP LOCKED)
            queue = db.query(Queue).filter(
                Queue.id == queue_id,
                Queue.is_paused == False
            ).with_for_update(skip_locked=True).first()
            
            if not queue:
                # Queue row is already locked by another worker transaction, skip it
                nested.rollback()
                continue
                
            # 4. Count active jobs in this queue
            active_count = db.query(Job).filter(
                Job.queue_id == queue.id,
                Job.status.in_(["CLAIMED", "RUNNING"])
            ).count()
            
            # 5. Check queue concurrency limit
            if queue.concurrency_limit is not None and active_count >= queue.concurrency_limit:
                # Capacity is saturated, rollback savepoint and try next queue
                nested.rollback()
                continue
                
            # 6. Query candidate jobs in this queue (FOR UPDATE SKIP LOCKED)
            candidates = db.query(Job).filter(
                Job.queue_id == queue.id,
                Job.status == "QUEUED",
                Job.available_at <= datetime.now(timezone.utc)
            ).order_by(
                Job.priority.desc(),
                Job.available_at.asc(),
                Job.created_at.asc()
            ).with_for_update(skip_locked=True).limit(20).all()
            
            job = None
            for cand in candidates:
                # Verify that all parent jobs this candidate depends on are COMPLETED
                dep_job_ids = db.query(JobDependency.depends_on_job_id).filter(JobDependency.job_id == cand.id).all()
                if dep_job_ids:
                    parent_ids = [d[0] for d in dep_job_ids]
                    incomplete_count = db.query(Job).filter(
                        Job.id.in_(parent_ids),
                        Job.status != "COMPLETED"
                    ).count()
                    if incomplete_count > 0:
                        continue  # Skip candidate as its dependencies are not met yet
                
                job = cand
                break
            
            if not job:
                # No eligible jobs with satisfied dependencies in this queue, rollback savepoint
                nested.rollback()
                continue
                
            # 7. Claim the job (transition status but DO NOT increment attempt)
            now = datetime.now(timezone.utc)
            job.status = "CLAIMED"
            job.claimed_by_worker_id = worker_id
            job.claimed_at = now
            job.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
            job.updated_at = now
            
            log = JobLog(
                id=uuid.uuid4(),
                job_id=job.id,
                log_level="INFO",
                message=f"Job claimed by worker {worker_id}."
            )
            db.add(log)
            db.flush()

            # Increment Prometheus counter
            from backend.app.core.prometheus_metrics import JOBS_CLAIMED_TOTAL
            JOBS_CLAIMED_TOTAL.inc()
            
            # Do not rollback the savepoint, we successfully claimed!
            return job

            
        except Exception:
            # On any error, rollback savepoint to release lock and fail gracefully
            nested.rollback()
            raise
            
    return None

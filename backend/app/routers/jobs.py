from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from datetime import datetime, timezone, timedelta
from croniter import croniter  # type: ignore[import-untyped]
import uuid

from backend.app.core.database import get_db
from backend.app.models import Job, Queue, Project, User, RetryPolicy, ScheduledJob, JobExecution, JobLog, BatchSubmission
from backend.app.core.rate_limiter import limiter
from backend.app.models import JobDependency
from backend.app.schemas import (
    JobCreate, JobResponse, JobDetailResponse, PaginatedResponse,
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobResponse,
    BatchJobCreate, BatchJobResponse, JobDependencyCreate, JobDependencyResponse
)
from backend.app.routers.deps import get_current_user, require_role
from backend.app.services.transitions import retry_job
from backend.app.services.claiming import would_create_cycle
from backend.app.services.failure_summary import FailureSummaryService

router = APIRouter(prefix="/jobs", tags=["Jobs"])

batch_jobs_counter = 0

# --- Helper ---
def get_job_with_isolation(job_id: UUID, db: Session, current_user: User) -> Job:
    """Helper to fetch a job while validating organization ownership."""
    job = db.query(Job).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"}
        )
    return job

# --- Batch & Regular Jobs Endpoints ---

@router.post("/batch", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
def create_batch_jobs(
    request: BatchJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN", "MEMBER"]))
):
    """Submits multiple jobs atomically within a single database transaction."""
    global batch_jobs_counter
    limiter.check_rate_limit(f"user:{current_user.id}:batch", max_requests=20, window_seconds=60)
    
    created_jobs: list[Job] = []
    now = datetime.now(timezone.utc)

    try:
        batch_sub = BatchSubmission(
            id=uuid.uuid4(),
            organization_id=current_user.organization_id,
            name=f"Batch Subscribed ({len(request.jobs)} jobs)",
            status="QUEUED",
            total_jobs=len(request.jobs)
        )
        db.add(batch_sub)

        for j_req in request.jobs:
            queue = db.query(Queue).join(Project).filter(
                Queue.id == j_req.queue_id,
                Project.organization_id == current_user.organization_id
            ).first()
            if not queue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "QUEUE_NOT_FOUND", "message": f"Queue {j_req.queue_id} not found in organization"}
                )
            
            resolved_policy_id = None
            resolved_max_retries = 3
            if j_req.retry_policy_id:
                policy = db.query(RetryPolicy).filter(RetryPolicy.id == j_req.retry_policy_id).first()
                if policy:
                    resolved_policy_id = policy.id
                    resolved_max_retries = policy.max_retries
            else:
                policy = db.query(RetryPolicy).filter(RetryPolicy.name == queue.name).first()
                if not policy:
                    policy = db.query(RetryPolicy).filter(RetryPolicy.name == "default").first()
                if policy:
                    resolved_policy_id = policy.id
                    resolved_max_retries = policy.max_retries

            available_at = now + timedelta(seconds=j_req.delay) if j_req.delay and j_req.delay > 0 else now
            status_str = "SCHEDULED" if available_at > now else "QUEUED"

            job = Job(
                id=uuid.uuid4(),
                queue_id=j_req.queue_id,
                retry_policy_id=resolved_policy_id,
                batch_id=batch_sub.id,
                status=status_str,
                task_type=j_req.task_type,
                payload=j_req.payload,
                priority=j_req.priority,
                max_retries=resolved_max_retries,
                attempt=0,
                scheduled_at=now,
                available_at=available_at
            )
            db.add(job)
            created_jobs.append(job)

        db.commit()
        for j in created_jobs:
            db.refresh(j)

        batch_jobs_counter += len(created_jobs)
        
        # Prometheus Metrics
        from backend.app.core.prometheus_metrics import BATCH_SUBMISSIONS_TOTAL, BATCH_JOBS_TOTAL, JOBS_SUBMITTED_TOTAL
        BATCH_SUBMISSIONS_TOTAL.inc()
        BATCH_JOBS_TOTAL.inc(len(created_jobs))
        JOBS_SUBMITTED_TOTAL.inc(len(created_jobs))

        return {"total_created": len(created_jobs), "jobs": created_jobs}
    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BATCH_CREATION_FAILED", "message": f"Batch creation failed: {str(e)}"}
        )

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    request: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN", "MEMBER"]))
):
    """Submits a new job (immediate or delayed), resolving the appropriate retry policy."""
    limiter.check_rate_limit(f"user:{current_user.id}:job", max_requests=100, window_seconds=60)
    
    queue = db.query(Queue).join(Project).filter(
        Queue.id == request.queue_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUEUE_NOT_FOUND", "message": "Queue not found"}
        )
        
    resolved_policy_id = None
    resolved_max_retries = 3
    
    if request.retry_policy_id:
        policy = db.query(RetryPolicy).filter(RetryPolicy.id == request.retry_policy_id).first()
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "RETRY_POLICY_NOT_FOUND", "message": "Retry policy not found"}
            )
        resolved_policy_id = policy.id
        resolved_max_retries = policy.max_retries
    else:
        policy = db.query(RetryPolicy).filter(RetryPolicy.name == queue.name).first()
        if not policy:
            policy = db.query(RetryPolicy).filter(RetryPolicy.name == "default").first()
        if policy:
            resolved_policy_id = policy.id
            resolved_max_retries = policy.max_retries
            
    now = datetime.now(timezone.utc)
    if request.delay and request.delay > 0:
        available_at = now + timedelta(seconds=request.delay)
    else:
        available_at = now
        
    status_str = "SCHEDULED" if available_at > now else "QUEUED"
    
    job = Job(
        id=uuid.uuid4(),
        queue_id=request.queue_id,
        retry_policy_id=resolved_policy_id,
        status=status_str,
        task_type=request.task_type,
        payload=request.payload,
        priority=request.priority,
        max_retries=resolved_max_retries,
        attempt=0,
        scheduled_at=now,
        available_at=available_at
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Prometheus Metric
    from backend.app.core.prometheus_metrics import JOBS_SUBMITTED_TOTAL, DEPENDENCY_BLOCKS_TOTAL, DEPENDENCY_CYCLES_REJECTED_TOTAL
    JOBS_SUBMITTED_TOTAL.inc()

    return job

@router.get("", response_model=PaginatedResponse[JobResponse])
def list_jobs(
    status: str | None = Query(default=None),
    queue_id: UUID | None = Query(default=None),
    priority: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists jobs belonging to the authenticated user's organization with filtering and pagination."""
    query = db.query(Job).join(Queue).join(Project).filter(
        Project.organization_id == current_user.organization_id
    )
    
    if status:
        query = query.filter(Job.status == status)
    if queue_id:
        query = query.filter(Job.queue_id == queue_id)
    if priority is not None:
        query = query.filter(Job.priority == priority)
        
    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size).all()
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total
    }

@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job_detail(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details of a job, including its execution logs, dependencies, and failure summary."""
    job = db.query(Job).options(
        joinedload(Job.executions),
        joinedload(Job.logs),
        joinedload(Job.dependencies),
        joinedload(Job.dependents)
    ).join(Queue).join(Project).filter(
        Job.id == job_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found"}
        )
        
    job.executions.sort(key=lambda x: x.started_at)
    job.logs.sort(key=lambda x: x.created_at)

    failure_summary = None
    if job.status in ("FAILED", "DEAD_LETTER"):
        failure_summary = FailureSummaryService.generate_summary(
            task_type=job.task_type,
            error_message=job.error,
            attempt=job.attempt,
            max_retries=job.max_retries,
            logs=job.logs
        )

    res_dict = {
        "id": job.id,
        "queue_id": job.queue_id,
        "retry_policy_id": job.retry_policy_id,
        "status": job.status,
        "task_type": job.task_type,
        "payload": job.payload,
        "result": job.result,
        "error": job.error,
        "priority": job.priority,
        "max_retries": job.max_retries,
        "attempt": job.attempt,
        "scheduled_at": job.scheduled_at,
        "available_at": job.available_at,
        "claimed_at": job.claimed_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "failed_at": job.failed_at,
        "lease_expires_at": job.lease_expires_at,
        "claimed_by_worker_id": job.claimed_by_worker_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "executions": job.executions,
        "logs": job.logs,
        "dependencies": job.dependencies,
        "dependents": job.dependents,
        "failure_summary": failure_summary
    }
    return res_dict

@router.post("/{job_id}/dependencies", response_model=JobDependencyResponse, status_code=status.HTTP_201_CREATED)
def add_job_dependency(
    job_id: UUID,
    request: JobDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN", "MEMBER"]))
):
    """Declares a dependency: job_id depends on depends_on_job_id (Job B depends on Job A)."""
    job = get_job_with_isolation(job_id, db, current_user)
    parent_job = get_job_with_isolation(request.depends_on_job_id, db, current_user)

    if job.id == parent_job.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DEPENDENCY", "message": "A job cannot depend on itself."}
        )

    if would_create_cycle(db, job.id, parent_job.id):
        from backend.app.core.prometheus_metrics import DEPENDENCY_CYCLES_REJECTED_TOTAL
        DEPENDENCY_CYCLES_REJECTED_TOTAL.inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CIRCULAR_DEPENDENCY", "message": "Adding this dependency would create a circular dependency cycle."}
        )

    existing = db.query(JobDependency).filter(
        JobDependency.job_id == job.id,
        JobDependency.depends_on_job_id == parent_job.id
    ).first()
    if existing:
        return existing

    dep = JobDependency(
        id=uuid.uuid4(),
        job_id=job.id,
        depends_on_job_id=parent_job.id
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)

    from backend.app.core.prometheus_metrics import DEPENDENCY_BLOCKS_TOTAL
    DEPENDENCY_BLOCKS_TOTAL.inc()

    return dep


@router.post("/{job_id}/retry", response_model=JobResponse)
def trigger_job_retry(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually triggers a retry for a failed or DEAD_LETTER job."""
    # Ensure job ownership
    get_job_with_isolation(job_id, db, current_user)
    
    try:
        job = retry_job(db, job_id)
        db.commit()
        db.refresh(job)
        return job
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry job: {str(e)}"
        )

# --- Scheduled / Recurring Jobs Endpoints ---

@router.post("/scheduled", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
def create_scheduled_job(
    request: ScheduledJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a scheduled/recurring job based on a cron expression."""
    # Validate project and queue exist and belong to organization
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"}
        )
        
    queue = db.query(Queue).filter(
        Queue.id == request.queue_id,
        Queue.project_id == request.project_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUEUE_NOT_FOUND", "message": "Queue not found"}
        )
        
    # Calculate next run time
    now = datetime.now(timezone.utc)
    iter = croniter(request.cron_expression, now)
    next_run_at = iter.get_next(datetime)
    
    sched = ScheduledJob(
        id=uuid.uuid4(),
        project_id=request.project_id,
        queue_id=request.queue_id,
        name=request.name,
        cron_expression=request.cron_expression,
        payload=request.payload,
        is_active=request.is_active,
        next_run_at=next_run_at
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched

@router.get("/scheduled", response_model=PaginatedResponse[ScheduledJobResponse])
def list_scheduled_jobs(
    project_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all scheduled/recurring jobs within the organization's projects."""
    query = db.query(ScheduledJob).join(Project).filter(
        Project.organization_id == current_user.organization_id
    )
    if project_id:
        query = query.filter(ScheduledJob.project_id == project_id)
        
    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(ScheduledJob.name.asc()).offset(offset).limit(page_size).all()
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total
    }

@router.patch("/scheduled/{id}", response_model=ScheduledJobResponse)
def update_scheduled_job(
    id: UUID,
    request: ScheduledJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates recurring job config, re-evaluating the next run time if modified."""
    sched = db.query(ScheduledJob).join(Project).filter(
        ScheduledJob.id == id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULED_JOB_NOT_FOUND", "message": "Scheduled job not found"}
        )
        
    cron_changed = False
    
    if request.name is not None:
        sched.name = request.name
    if request.payload is not None:
        sched.payload = request.payload
    if request.is_active is not None:
        sched.is_active = request.is_active
        cron_changed = True  # Triggers next run re-evaluation
    if request.cron_expression is not None:
        sched.cron_expression = request.cron_expression
        cron_changed = True
        
    if cron_changed:
        if sched.is_active:
            now = datetime.now(timezone.utc)
            iter = croniter(sched.cron_expression, now)
            sched.next_run_at = iter.get_next(datetime)
        else:
            sched.next_run_at = None
            
    db.commit()
    db.refresh(sched)
    return sched

@router.delete("/scheduled/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scheduled_job(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a recurring/scheduled job config."""
    sched = db.query(ScheduledJob).join(Project).filter(
        ScheduledJob.id == id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULED_JOB_NOT_FOUND", "message": "Scheduled job not found"}
        )
        
    db.delete(sched)
    db.commit()
    return

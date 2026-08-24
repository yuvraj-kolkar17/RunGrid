from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
from typing import Any
import uuid

from backend.app.core.database import get_db
from backend.app.models import Worker, WorkerHeartbeat, Job
from backend.app.schemas import WorkerRegisterRequest, WorkerResponse, JobResponse
from backend.app.routers.deps import verify_internal_key
from backend.app.services.claiming import claim_job
from backend.app.services.transitions import start_job, complete_job, fail_job

# Define models for request bodies
from pydantic import BaseModel

class JobStartRequest(BaseModel):
    worker_id: UUID

class JobCompleteRequest(BaseModel):
    worker_id: UUID
    result: dict[str, Any] | None = None

class JobFailRequest(BaseModel):
    worker_id: UUID
    error_message: str


class WorkerHeartbeatRequest(BaseModel):
    status: str
    active_jobs: int
    max_concurrency: int
    available_capacity: int


router = APIRouter(prefix="/internal", tags=["Internal Worker API"])

@router.post("/workers/register", response_model=WorkerResponse)
def register_worker(
    request: WorkerRegisterRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Registers or updates a worker process in the database."""
    # Find existing worker by hostname & ip_address
    worker = db.query(Worker).filter(
        Worker.hostname == request.hostname,
        Worker.ip_address == request.ip_address
    ).first()
    
    now = datetime.now(timezone.utc)
    
    if worker:
        worker.status = "ACTIVE"
        worker.last_heartbeat_at = now
        worker.updated_at = now
    else:
        worker = Worker(
            id=uuid.uuid4(),
            hostname=request.hostname,
            ip_address=request.ip_address,
            status="ACTIVE",
            last_heartbeat_at=now,
            created_at=now,
            updated_at=now
        )
        db.add(worker)
        
    db.commit()
    db.refresh(worker)
    return worker

@router.post("/workers/{worker_id}/heartbeat")
def worker_heartbeat(
    worker_id: UUID,
    request: WorkerHeartbeatRequest | None = None,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Receives heartbeats from active workers and updates their status."""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WORKER_NOT_FOUND", "message": "Worker not found"}
        )
        
    now = datetime.now(timezone.utc)
    # If worker sends status, we can update it or keep ACTIVE
    if request:
        worker.status = request.status
    else:
        worker.status = "ACTIVE"
    worker.last_heartbeat_at = now
    worker.updated_at = now
    
    # Store heartbeat audit log
    heartbeat_log = WorkerHeartbeat(
        id=uuid.uuid4(),
        worker_id=worker.id,
        status_details=request.model_dump() if request else None,
        created_at=now
    )
    db.add(heartbeat_log)
    db.commit()
    return {"status": "ok"}


@router.post("/workers/{worker_id}/poll", response_model=JobResponse | None)
def worker_poll_job(
    worker_id: UUID,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Polls for the next eligible job dynamically locked and claimed for this worker."""
    try:
        job = claim_job(db, worker_id)
        db.commit()
        return job
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WORKER_INVALID_STATE", "message": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during claim transaction: {str(e)}"
        )

@router.post("/jobs/{job_id}/start", response_model=JobResponse)
def worker_start_job(
    job_id: UUID,
    request: JobStartRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Transitions a job to RUNNING state, incrementing attempt count."""
    try:
        job = start_job(db, job_id, request.worker_id)
        db.commit()
        db.refresh(job)
        return job
    except ValueError as e:
        db.rollback()
        if "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": str(e)}
            )
        if "Already started" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_STARTED", "message": str(e)}
            )
        if "Worker mismatch" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WORKER_MISMATCH", "message": str(e)}
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start job: {str(e)}"
        )

@router.post("/jobs/{job_id}/complete", response_model=JobResponse)
def worker_complete_job(
    job_id: UUID,
    request: JobCompleteRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Transitions a job to COMPLETED state and records the result payload."""
    try:
        job = complete_job(db, job_id, request.worker_id, request.result)
        db.commit()
        db.refresh(job)
        return job
    except ValueError as e:
        db.rollback()
        if "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": str(e)}
            )
        if "Already completed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_COMPLETED", "message": str(e)}
            )
        if "Worker mismatch" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WORKER_MISMATCH", "message": str(e)}
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete job: {str(e)}"
        )

@router.post("/jobs/{job_id}/fail", response_model=JobResponse)
def worker_fail_job(
    job_id: UUID,
    request: JobFailRequest,
    db: Session = Depends(get_db),
    _key: str = Depends(verify_internal_key)
):
    """Transitions a job to FAILED or RETRY_WAITING/DEAD_LETTER state based on attempt history."""
    try:
        job = fail_job(db, job_id, request.error_message, request.worker_id)
        db.commit()
        db.refresh(job)
        return job
    except ValueError as e:
        db.rollback()
        if "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "JOB_NOT_FOUND", "message": str(e)}
            )
        if "Already failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_FAILED", "message": str(e)}
            )
        if "Worker mismatch" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WORKER_MISMATCH", "message": str(e)}
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": str(e)}
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fail job: {str(e)}"
        )



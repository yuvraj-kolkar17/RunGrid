from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from backend.app.core.database import get_db
from backend.app.models import Queue, Project, User, Job, DeadLetterJob
from backend.app.schemas import QueueCreate, QueueUpdate, QueueResponse, QueueStats, PaginatedResponse
from backend.app.routers.deps import get_current_user, require_role

router = APIRouter(prefix="/queues", tags=["Queues"])

def get_queue_with_isolation(queue_id: UUID, db: Session, current_user: User) -> Queue:
    """Helper to fetch a queue while validating organization ownership."""
    queue = db.query(Queue).join(Project).filter(
        Queue.id == queue_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUEUE_NOT_FOUND", "message": "Queue not found"}
        )
    return queue

@router.post("", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
def create_queue(
    request: QueueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN"]))
):
    """Creates a queue within a project, validating project ownership and uniqueness."""
    # Validate project exists and belongs to the organization
    project = db.query(Project).filter(
        Project.id == request.project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"}
        )
        
    # Check uniqueness of queue name in the project
    existing = db.query(Queue).filter(
        Queue.project_id == request.project_id,
        Queue.name == request.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "QUEUE_ALREADY_EXISTS", "message": f"Queue '{request.name}' already exists in this project"}
        )
        
    queue = Queue(
        id=uuid.uuid4(),
        project_id=request.project_id,
        name=request.name,
        priority=request.priority,
        concurrency_limit=request.concurrency_limit,
        is_paused=False
    )
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue

@router.get("", response_model=PaginatedResponse[QueueResponse])
def list_queues(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists queues in projects belonging to the user's organization."""
    query = db.query(Queue).join(Project).filter(Project.organization_id == current_user.organization_id)
    if project_id:
        query = query.filter(Queue.project_id == project_id)
        
    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(Queue.priority.desc(), Queue.name.asc()).offset(offset).limit(page_size).all()
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total
    }

@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(
    queue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves a single queue details."""
    return get_queue_with_isolation(queue_id, db, current_user)

@router.patch("/{queue_id}", response_model=QueueResponse)
def update_queue(
    queue_id: UUID,
    request: QueueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN"]))
):
    """Updates queue configuration (priority/concurrency_limit)."""
    queue = get_queue_with_isolation(queue_id, db, current_user)
    
    if request.priority is not None:
        queue.priority = request.priority
    if request.concurrency_limit is not None:
        queue.concurrency_limit = request.concurrency_limit
        
    db.commit()
    db.refresh(queue)
    return queue

@router.patch("/{queue_id}/pause", response_model=QueueResponse)
def pause_queue(
    queue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN"]))
):
    """Pauses a queue, preventing new jobs from being claimed from it."""
    queue = get_queue_with_isolation(queue_id, db, current_user)
    queue.is_paused = True
    db.commit()
    db.refresh(queue)
    return queue

@router.patch("/{queue_id}/resume", response_model=QueueResponse)
def resume_queue(
    queue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN"]))
):
    """Resumes a queue, allowing workers to claim jobs again."""
    queue = get_queue_with_isolation(queue_id, db, current_user)
    queue.is_paused = False
    db.commit()
    db.refresh(queue)
    return queue

@router.get("/{queue_id}/stats", response_model=QueueStats)
def get_queue_stats(
    queue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns the job status distribution for the given queue."""
    # Validate queue exists and belongs to organization
    get_queue_with_isolation(queue_id, db, current_user)
    
    queued_count = db.query(Job).filter(Job.queue_id == queue_id, Job.status == "QUEUED").count()
    running_count = db.query(Job).filter(Job.queue_id == queue_id, Job.status == "RUNNING").count()
    claimed_count = db.query(Job).filter(Job.queue_id == queue_id, Job.status == "CLAIMED").count()
    completed_count = db.query(Job).filter(Job.queue_id == queue_id, Job.status == "COMPLETED").count()
    failed_count = db.query(Job).filter(Job.queue_id == queue_id, Job.status == "FAILED").count()
    dead_letter_count = db.query(DeadLetterJob).filter(DeadLetterJob.queue_id == queue_id).count()
    
    return {
        "queued_count": queued_count,
        "running_count": running_count,
        "claimed_count": claimed_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "dead_letter_count": dead_letter_count
    }

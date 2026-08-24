from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID
import uuid

from backend.app.core.database import get_db
from backend.app.models import Project, User
from backend.app.schemas import ProjectCreate, ProjectResponse, PaginatedResponse
from backend.app.routers.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a project for the authenticated user's organization."""
    project = Project(
        id=uuid.uuid4(),
        name=request.name,
        organization_id=current_user.organization_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("", response_model=PaginatedResponse[ProjectResponse])
def list_projects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all projects for the authenticated user's organization with pagination."""
    query = db.query(Project).filter(Project.organization_id == current_user.organization_id)
    total = query.count()
    
    offset = (page - 1) * page_size
    items = query.order_by(Project.name.asc()).offset(offset).limit(page_size).all()
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total
    }

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves a specific project, raising 404 if it does not belong to the user's organization."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.organization_id == current_user.organization_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PROJECT_NOT_FOUND", "message": "Project not found"}
        )
    return project

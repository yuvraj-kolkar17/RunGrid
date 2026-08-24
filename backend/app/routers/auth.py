from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import uuid

from backend.app.core.database import get_db
from backend.app.core.security import get_password_hash, verify_password, create_access_token
from backend.app.models import User, Organization, Project, Queue
from backend.app.schemas import UserRegisterRequest, UserResponse, Token
from backend.app.routers.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user and creates an organization."""
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_ALREADY_REGISTERED", "message": "Email is already registered"}
        )
        
    try:
        # Create Organization
        org = Organization(id=uuid.uuid4(), name=request.organization_name)
        db.add(org)
        db.flush()
        
        # Create User
        hashed_password = get_password_hash(request.password)
        user = User(
            id=uuid.uuid4(),
            email=request.email,
            password_hash=hashed_password,
            organization_id=org.id,
            role=request.role or "OWNER"
        )
        db.add(user)
        db.flush()

        # Create Default Project & Queue for quick evaluation
        proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Default Project")
        db.add(proj)
        db.flush()

        queue = Queue(
            id=uuid.uuid4(),
            project_id=proj.id,
            name="default",
            concurrency_limit=5,
            priority=1
        )
        db.add(queue)

        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Logs in a user and returns a JWT token. Auto-creates demo user on initial login if needed."""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    # Auto-seed demo accounts on demand if not present
    demo_credentials = {
        "owner@demo.com": "OWNER",
        "admin@demo.com": "ADMIN",
        "demo_user@example.com": "OWNER"
    }

    if form_data.username in demo_credentials and form_data.password == "Password123!":
        if not user:
            try:
                org = db.query(Organization).filter(Organization.name == "Acme Cloud").first()
                if not org:
                    org = Organization(id=uuid.uuid4(), name="Acme Cloud")
                    db.add(org)
                    db.flush()

                user = User(
                    id=uuid.uuid4(),
                    email=form_data.username,
                    password_hash=get_password_hash("Password123!"),
                    organization_id=org.id,
                    role=demo_credentials[form_data.username]
                )
                db.add(user)
                db.flush()

                proj = db.query(Project).filter(Project.organization_id == org.id).first()
                if not proj:
                    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Default Project")
                    db.add(proj)
                    db.flush()

                queue = db.query(Queue).filter(Queue.project_id == proj.id).first()
                if not queue:
                    queue = Queue(
                        id=uuid.uuid4(),
                        project_id=proj.id,
                        name="default",
                        concurrency_limit=5,
                        priority=1
                    )
                    db.add(queue)

                db.commit()
                db.refresh(user)
            except Exception as e:
                db.rollback()
                user = None
        else:
            # If user exists but password check failed, sync password hash for demo accounts
            if not verify_password(form_data.password, user.password_hash):
                user.password_hash = get_password_hash("Password123!")
                db.commit()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieves current user details."""
    return current_user

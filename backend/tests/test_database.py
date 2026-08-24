import pytest
import uuid
from collections.abc import Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.core.database import SessionLocal
from backend.app.models import (
    Organization, User, Project, Queue, RetryPolicy, Job, Worker, JobExecution, ScheduledJob, DeadLetterJob
)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Fixture to provide a clean database session rolled back after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_organization_and_user_creation(db: Session):
    # Test valid creation
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    user = User(
        email="user@example.com",
        password_hash="hash123",
        organization_id=org.id
    )
    db.add(user)
    db.flush()
    
    assert org.id is not None
    assert user.id is not None
    assert user.organization.name == "Test Org"


def test_unique_user_email(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    user1 = User(email="user@example.com", password_hash="h1", organization_id=org.id)
    db.add(user1)
    db.flush()
    
    user2 = User(email="user@example.com", password_hash="h2", organization_id=org.id)
    db.add(user2)
    
    with pytest.raises(IntegrityError):
        db.flush()


def test_foreign_key_user_organization(db: Session):
    # Invalid organization ID
    user = User(
        email="bad@example.com",
        password_hash="h",
        organization_id=uuid.uuid4()
    )
    db.add(user)
    with pytest.raises(IntegrityError):
        db.flush()


def test_unique_queue_name_in_project(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    proj1 = Project(name="Project 1", organization_id=org.id)
    proj2 = Project(name="Project 2", organization_id=org.id)
    db.add_all([proj1, proj2])
    db.flush()
    
    # Valid: Same queue name in different projects
    q1 = Queue(name="default", project_id=proj1.id)
    q2 = Queue(name="default", project_id=proj2.id)
    db.add_all([q1, q2])
    db.flush()
    
    # Invalid: Same queue name in the same project
    q3 = Queue(name="default", project_id=proj1.id)
    db.add(q3)
    with pytest.raises(IntegrityError):
        db.flush()


def test_queue_concurrency_limit_check(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    proj = Project(name="Proj", organization_id=org.id)
    db.add(proj)
    db.flush()
    
    # Invalid: Concurrency limit <= 0
    q = Queue(name="low_concurrency", project_id=proj.id, concurrency_limit=0)
    db.add(q)
    with pytest.raises(IntegrityError):
        db.flush()


def test_retry_policy_strategy_check(db: Session):
    # Invalid strategy
    policy = RetryPolicy(name="Bad Policy", strategy="random", base_delay=5, max_retries=3)
    db.add(policy)
    with pytest.raises(IntegrityError):
        db.flush()


def test_retry_policy_negative_values(db: Session):
    # Negative base_delay
    p1 = RetryPolicy(name="Neg Delay", strategy="fixed", base_delay=-5, max_retries=3)
    db.add(p1)
    with pytest.raises(IntegrityError):
        db.flush()
        
    db.rollback()
    
    # Negative max_retries
    p2 = RetryPolicy(name="Neg Retries", strategy="fixed", base_delay=5, max_retries=-1)
    db.add(p2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_job_status_constraint(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    proj = Project(name="Proj", organization_id=org.id)
    db.add(proj)
    db.flush()
    
    q = Queue(name="job_q", project_id=proj.id)
    db.add(q)
    db.flush()
    
    # Invalid status
    job = Job(queue_id=q.id, payload={"type": "test"}, status="NOT_REAL_STATUS")
    db.add(job)
    with pytest.raises(IntegrityError):
        db.flush()


def test_job_negative_fields(db: Session):
    org = Organization(name="Test Org")
    db.add(org)
    db.flush()
    
    proj = Project(name="Proj", organization_id=org.id)
    db.add(proj)
    db.flush()
    
    q = Queue(name="job_q2", project_id=proj.id)
    db.add(q)
    db.flush()
    
    # Negative priority
    j1 = Job(queue_id=q.id, payload={"type": "test"}, priority=-1)
    db.add(j1)
    with pytest.raises(IntegrityError):
        db.flush()
        
    db.rollback()
    
    # Negative attempt
    j2 = Job(queue_id=q.id, payload={"type": "test"}, attempt=-3)
    db.add(j2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_worker_status_constraint(db: Session):
    # Invalid worker status
    worker = Worker(hostname="host1", ip_address="127.0.0.1", status="UNKNOWN")
    db.add(worker)
    with pytest.raises(IntegrityError):
        db.flush()


def test_cascade_delete(db: Session):
    org = Organization(name="Cascade Org")
    db.add(org)
    db.flush()
    
    proj = Project(name="Cascade Proj", organization_id=org.id)
    db.add(proj)
    db.flush()
    
    q = Queue(name="Cascade Queue", project_id=proj.id)
    db.add(q)
    db.flush()
    
    job = Job(queue_id=q.id, payload={"task": "something"})
    db.add(job)
    db.flush()
    
    # Assert they exist
    assert db.query(Job).filter(Job.id == job.id).first() is not None
    
    # Delete organization
    db.delete(org)
    db.flush()
    
    # Verify cascade delete cascaded down to projects, queues, and jobs
    assert db.query(Project).filter(Project.id == proj.id).first() is None
    assert db.query(Queue).filter(Queue.id == q.id).first() is None
    assert db.query(Job).filter(Job.id == job.id).first() is None

from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Any, Generic, TypeVar, List
from croniter import croniter  # type: ignore[import-untyped]

# --- Pagination ---
T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total: int

# --- Authentication & User ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: UUID | None = None
    email: str | None = None
    role: str | None = None

class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str = "MEMBER"
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    organization_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="OWNER")

# --- Project ---
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Queue ---
class QueueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    priority: int = Field(default=0, ge=0)
    concurrency_limit: int | None = Field(default=None, gt=0)
    project_id: UUID

class QueueUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=0)
    concurrency_limit: int | None = Field(default=None, gt=0)

class QueueResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    priority: int
    concurrency_limit: int | None
    is_paused: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class QueueStats(BaseModel):
    queued_count: int
    running_count: int
    claimed_count: int
    completed_count: int
    failed_count: int
    dead_letter_count: int

# --- Retry Policy ---
class RetryPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    strategy: str = Field(..., description="fixed, linear, or exponential")
    base_delay: int = Field(..., ge=0)
    max_retries: int = Field(default=3, gt=0)

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        if v not in ("fixed", "linear", "exponential"):
            raise ValueError("strategy must be one of: fixed, linear, exponential")
        return v

class RetryPolicyResponse(BaseModel):
    id: UUID
    name: str
    strategy: str
    base_delay: int
    max_retries: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Job ---
class JobCreate(BaseModel):
    task_type: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    queue_id: UUID
    priority: int = Field(default=0, ge=0)
    delay: int | None = Field(default=None, ge=0)
    retry_policy_id: UUID | None = Field(default=None)

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        # Predefined allowed task types
        allowed = {
            "demo.success", "demo.failure", "demo.slow", "demo.retry",
            "email.send", "invoice.generate", "report.generate",
            "image.process", "notification.send", "customer.sync"
        }
        if v not in allowed:
            raise ValueError(f"task_type '{v}' is not registered. Allowed: {sorted(allowed)}")
        return v

class JobExecutionResponse(BaseModel):
    id: UUID
    job_id: UUID
    worker_id: UUID | None
    status: str
    error: str | None
    attempt: int
    started_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True

class JobLogResponse(BaseModel):
    id: UUID
    job_id: UUID
    execution_id: UUID | None
    log_level: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: UUID
    queue_id: UUID
    retry_policy_id: UUID | None
    status: str
    task_type: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    priority: int
    max_retries: int
    attempt: int
    scheduled_at: datetime
    available_at: datetime
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    lease_expires_at: datetime | None
    claimed_by_worker_id: UUID | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BatchJobCreate(BaseModel):
    jobs: List[JobCreate] = Field(..., min_length=1)

class BatchJobResponse(BaseModel):
    total_created: int
    jobs: List[JobResponse]

class JobDependencyCreate(BaseModel):
    depends_on_job_id: UUID

class JobDependencyResponse(BaseModel):
    id: UUID
    job_id: UUID
    depends_on_job_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class FailureSummaryResponse(BaseModel):
    summary: str
    likely_cause: str
    recommended_action: str

class JobDetailResponse(JobResponse):
    executions: List[JobExecutionResponse] = Field(default_factory=list)
    logs: List[JobLogResponse] = Field(default_factory=list)
    dependencies: List[JobDependencyResponse] = Field(default_factory=list)
    dependents: List[JobDependencyResponse] = Field(default_factory=list)
    failure_summary: FailureSummaryResponse | None = None

# --- Scheduled / Recurring Job ---
class ScheduledJobCreate(BaseModel):
    project_id: UUID
    queue_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    cron_expression: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(default=True)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"cron_expression '{v}' is not valid")
        return v

class ScheduledJobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    cron_expression: str | None = Field(default=None)
    payload: dict[str, Any] | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"cron_expression '{v}' is not valid")
        return v

class ScheduledJobResponse(BaseModel):
    id: UUID
    project_id: UUID
    queue_id: UUID
    name: str
    cron_expression: str
    payload: dict[str, Any]
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Worker ---
class WorkerRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    ip_address: str = Field(..., min_length=1, max_length=45)

class WorkerResponse(BaseModel):
    id: UUID
    hostname: str
    ip_address: str
    status: str
    last_heartbeat_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Errors ---
class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None

class ErrorResponse(BaseModel):
    error: ErrorDetail

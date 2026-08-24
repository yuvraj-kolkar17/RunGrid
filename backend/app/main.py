import uuid
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.routers import auth, projects, queues, jobs, internal, metrics, platform
from backend.app.core.config import settings

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (Request-ID: %(request_id)s) %(message)s"
)

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "N/A"
        return True

for h in logging.root.handlers:
    h.addFilter(RequestIDFilter())

logger = logging.getLogger("app")
logger.addFilter(RequestIDFilter())

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and inject a unique request ID into request state and response headers."""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

import re
from backend.app.core.prometheus_metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    get_prometheus_metrics,
    CONTENT_TYPE_LATEST
)

UUID_REGEX = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')

def normalize_route_path(request: Request) -> str:
    """Normalize route path replacing UUID parameters with {id} templates to prevent cardinality explosion."""
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match and hasattr(route, "path"):
            return route.path
    return UUID_REGEX.sub("{id}", request.url.path)

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to record HTTP request counters and duration histogram with strict route normalization."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in ("/health", "/ready", "/metrics"):
            return await call_next(request)
            
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        route_template = normalize_route_path(request)
        status_code = str(response.status_code)
        method = request.method
        
        HTTP_REQUESTS_TOTAL.labels(method=method, route=route_template, status=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route_template).observe(duration)
        
        return response

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log API request metrics (method, path, status, duration_ms)."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Suppress logging for noisy health checks and metrics
        if path in ("/health", "/ready", "/metrics"):
            return await call_next(request)
            
        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        request_id = getattr(request.state, "request_id", "N/A")
        logger.info(
            f"HTTP {request.method} {path} -> Status: {response.status_code} ({duration_ms}ms) [Request-ID: {request_id}]"
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to seed default demo user on startup."""
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.models import User, Organization, Project, Queue
        from backend.app.core.security import get_password_hash
        
        db = SessionLocal()
        try:
            demo_accounts = [
                ("owner@demo.com", "Acme Cloud", "OWNER"),
                ("admin@demo.com", "Acme Cloud", "ADMIN"),
                ("demo_user@example.com", "Demo Corp", "OWNER"),
            ]
            hashed_password = get_password_hash("Password123!")

            for email, org_name, role in demo_accounts:
                existing_user = db.query(User).filter(User.email == email).first()
                if not existing_user:
                    org = db.query(Organization).filter(Organization.name == org_name).first()
                    if not org:
                        org = Organization(id=uuid.uuid4(), name=org_name)
                        db.add(org)
                        db.flush()

                    user = User(
                        id=uuid.uuid4(),
                        email=email,
                        password_hash=hashed_password,
                        role=role,
                        organization_id=org.id
                    )
                    db.add(user)
                    db.flush()

                    proj = db.query(Project).filter(Project.organization_id == org.id).first()
                    if not proj:
                        proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Default Project")
                        db.add(proj)
                        db.flush()

                    q = db.query(Queue).filter(Queue.project_id == proj.id).first()
                    if not q:
                        q = Queue(
                            id=uuid.uuid4(),
                            project_id=proj.id,
                            name="default",
                            concurrency_limit=5,
                            priority=1
                        )
                        db.add(q)
                    db.commit()
                    logger.info(f"Seeded default demo user '{email}' on startup.")
                else:
                    # Update password to ensure Password123! works
                    existing_user.password_hash = hashed_password
                    db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not seed demo users on startup: {e}")

        
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID, Prometheus & Logging Middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# --- Exception Handlers ---

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", None)
    
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "ERROR")
        message = exc.detail.get("message", "An error occurred")
    else:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR"
        }
        code = code_map.get(exc.status_code, "INTERNAL_SERVER_ERROR")
        message = str(exc.detail)
        
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    
    errors = exc.errors()
    if errors:
        first_err = errors[0]
        loc = " -> ".join(str(x) for x in first_err.get("loc", []))
        msg = first_err.get("msg", "Validation error")
        message = f"Field {loc}: {msg}"
    else:
        message = "Validation failed"
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "request_id": request_id
            }
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"Unhandled server error: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "request_id": request_id
            }
        }
    )

# --- Mount Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(queues.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(internal.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(platform.router, prefix="/api/v1")

@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    from fastapi.responses import Response
    from backend.app.core.database import SessionLocal
    db = SessionLocal()
    try:
        data = get_prometheus_metrics(db)
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    finally:
        db.close()

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}

@app.get("/ready", tags=["Health"])
def ready_check():
    from backend.app.core.database import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "detail": "Database connection failed"}
        )


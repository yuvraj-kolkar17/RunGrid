from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import math

from backend.app.core.database import get_db
from backend.app.models import Job, Worker, Queue, DeadLetterJob, ScheduledJob, JobExecution, User
from backend.app.routers.deps import get_current_user

router = APIRouter(prefix="/metrics", tags=["Metrics"])

@router.get("", response_model=Dict[str, Any])
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Exposes system metrics including job counts, worker status, execution performance, and queue utilization."""
    now = datetime.now(timezone.utc)
    
    # 1. Job counts by status
    status_counts_raw = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    status_counts = {status: count for status, count in status_counts_raw}
    
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    dead_letter_count = db.query(func.count(DeadLetterJob.id)).scalar() or 0
    
    completed_count = status_counts.get("COMPLETED", 0)
    failed_count = status_counts.get("FAILED", 0)
    queued_count = status_counts.get("QUEUED", 0)
    running_count = status_counts.get("RUNNING", 0)
    claimed_count = status_counts.get("CLAIMED", 0)
    retry_waiting_count = status_counts.get("RETRY_WAITING", 0)
    scheduled_count = status_counts.get("SCHEDULED", 0)
    
    terminal_jobs = completed_count + failed_count + dead_letter_count
    
    # Calculate rates safely (avoid division by zero)
    success_rate = round((completed_count / terminal_jobs) * 100, 2) if terminal_jobs > 0 else 0.0
    failure_rate = round(((failed_count + dead_letter_count) / terminal_jobs) * 100, 2) if terminal_jobs > 0 else 0.0
    retry_rate = round((retry_waiting_count / total_jobs) * 100, 2) if total_jobs > 0 else 0.0
    
    total_retry_attempts = db.query(func.sum(Job.attempt)).scalar() or 0
    
    jobs_summary = {
        "total": total_jobs,
        "queued": queued_count,
        "claimed": claimed_count,
        "running": running_count,
        "completed": completed_count,
        "failed": failed_count,
        "retry_waiting": retry_waiting_count,
        "scheduled": scheduled_count,
        "dead_letter": dead_letter_count,
        "rates": {
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "retry_rate": retry_rate,
            "total_retry_attempts": int(total_retry_attempts),
        }
    }
    
    # Backward compatibility key system_overview
    system_overview = {
        "total_jobs": total_jobs,
        "total": total_jobs,
        "queued": queued_count,
        "claimed": claimed_count,
        "running": running_count,
        "completed": completed_count,
        "failed": failed_count,
        "retry_waiting": retry_waiting_count,
        "scheduled": scheduled_count,
        "dead_letter": dead_letter_count
    }
    
    # 2. Worker stats & Heartbeat Freshness
    cutoff_60s = now - timedelta(seconds=60)
    workers = db.query(Worker).all()
    
    total_workers = len(workers)
    active_workers = 0
    stale_workers = 0
    inactive_workers = 0
    worker_nodes_detail: List[Dict[str, Any]] = []
    
    for w in workers:
        hb_time = w.last_heartbeat_at
        if hb_time and hb_time.tzinfo is None:
            hb_time = hb_time.replace(tzinfo=timezone.utc)
            
        hb_age = round((now - hb_time).total_seconds(), 1) if hb_time else 9999.0
        
        if w.status == "INACTIVE":
            w_status = "INACTIVE"
            inactive_workers += 1
        elif hb_age <= 60.0:
            w_status = "ACTIVE"
            active_workers += 1
        else:
            w_status = "STALE"
            stale_workers += 1
            
        # Count active jobs assigned to worker
        w_active_jobs = db.query(func.count(Job.id)).filter(
            Job.claimed_by_worker_id == w.id,
            Job.status.in_(["CLAIMED", "RUNNING"])
        ).scalar() or 0
        
        worker_nodes_detail.append({
            "worker_id": str(w.id),
            "hostname": w.hostname,
            "ip_address": w.ip_address,
            "status": w.status,
            "health_status": w_status,
            "last_heartbeat": hb_time.isoformat() if hb_time else None,
            "heartbeat_age_seconds": hb_age,
            "active_jobs": w_active_jobs,
            "max_concurrency": 10,
            "available_capacity": max(0, 10 - w_active_jobs),
            "created_at": w.created_at.isoformat() if w.created_at else None,
        })
        
    workers_summary = {
        "total_workers": total_workers,
        "active_workers": active_workers,
        "stale_workers": stale_workers,
        "inactive_workers": inactive_workers,
        "total_capacity": total_workers * 10,
        "active_capacity": active_workers * 10,
    }
    
    # 3. Queue utilization
    queues = db.query(Queue).all()
    queue_utilization: List[Dict[str, Any]] = []
    
    for q in queues:
        q_active = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status.in_(["CLAIMED", "RUNNING"])
        ).scalar() or 0
        
        q_queued = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status == "QUEUED"
        ).scalar() or 0
        
        q_completed = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status == "COMPLETED"
        ).scalar() or 0
        
        q_failed = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status.in_(["FAILED", "DEAD_LETTER"])
        ).scalar() or 0
        
        q_retry = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status == "RETRY_WAITING"
        ).scalar() or 0
        
        if q.concurrency_limit and q.concurrency_limit > 0:
            util_pct: Optional[float] = round((q_active / q.concurrency_limit) * 100, 2)
            is_saturated = q_active >= q.concurrency_limit
        else:
            util_pct = None
            is_saturated = False
            
        queue_utilization.append({
            "queue_id": str(q.id),
            "queue_name": q.name,
            "priority": q.priority,
            "is_paused": q.is_paused,
            "concurrency_limit": q.concurrency_limit,
            "active_jobs": q_active,
            "queued_jobs": q_queued,
            "completed_jobs": q_completed,
            "failed_jobs": q_failed,
            "retry_waiting_jobs": q_retry,
            "utilization_percentage": util_pct,
            "is_saturated": is_saturated,
            "has_backlog": q_queued > 0
        })
        
    # 4. Multi-Window Throughput
    t_5m = now - timedelta(minutes=5)
    t_15m = now - timedelta(minutes=15)
    t_1h = now - timedelta(hours=1)
    
    completed_last_5m = db.query(func.count(Job.id)).filter(
        Job.status == "COMPLETED",
        Job.completed_at >= t_5m
    ).scalar() or 0
    
    completed_last_15m = db.query(func.count(Job.id)).filter(
        Job.status == "COMPLETED",
        Job.completed_at >= t_15m
    ).scalar() or 0
    
    completed_last_hour = db.query(func.count(Job.id)).filter(
        Job.status == "COMPLETED",
        Job.completed_at >= t_1h
    ).scalar() or 0
    
    failed_last_hour = db.query(func.count(Job.id)).filter(
        Job.status.in_(["FAILED", "DEAD_LETTER"]),
        Job.failed_at >= t_1h
    ).scalar() or 0
    
    throughput_per_min = round(completed_last_hour / 60.0, 2)
    
    # 5. Execution Performance (aggregations on JobExecution)
    executions = db.query(JobExecution).filter(
        JobExecution.finished_at.isnot(None),
        JobExecution.started_at.isnot(None)
    ).all()
    
    durations_ms: List[float] = []
    completed_execs = 0
    failed_execs = 0
    
    for ex in executions:
        if ex.status == "COMPLETED":
            completed_execs += 1
        elif ex.status in ("FAILED", "DEAD_LETTER"):
            failed_execs += 1
            
        st = ex.started_at
        ft = ex.finished_at
        if st and ft:
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            if ft.tzinfo is None:
                ft = ft.replace(tzinfo=timezone.utc)
            dur_ms = max(0.0, (ft - st).total_seconds() * 1000.0)
            durations_ms.append(dur_ms)
            
    if durations_ms:
        durations_ms.sort()
        n = len(durations_ms)
        avg_dur = round(sum(durations_ms) / n, 2)
        min_dur = round(durations_ms[0], 2)
        max_dur = round(durations_ms[-1], 2)
        
        p50 = round(durations_ms[math.ceil(0.50 * n) - 1], 2)
        p95 = round(durations_ms[math.ceil(0.95 * n) - 1], 2)
        p99 = round(durations_ms[math.ceil(0.99 * n) - 1], 2)
    else:
        avg_dur = 0.0
        min_dur = 0.0
        max_dur = 0.0
        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        
    execution_performance = {
        "completed_executions_count": completed_execs,
        "failed_executions_count": failed_execs,
        "avg_duration_ms": avg_dur,
        "min_duration_ms": min_dur,
        "max_duration_ms": max_dur,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99
    }
    
    # 6. Scheduler Observability
    active_schedules = db.query(func.count(ScheduledJob.id)).filter(ScheduledJob.is_active.is_(True)).scalar() or 0
    due_schedules = db.query(func.count(ScheduledJob.id)).filter(
        ScheduledJob.is_active.is_(True),
        ScheduledJob.next_run_at <= now
    ).scalar() or 0
    total_schedules = db.query(func.count(ScheduledJob.id)).scalar() or 0
    
    scheduler_summary = {
        "active_schedules_count": active_schedules,
        "due_schedules_count": due_schedules,
        "total_scheduled_jobs": total_schedules
    }
    
    # 7. Reaper / Recovery Observability
    recovered_jobs = db.query(func.count(Job.id)).filter(Job.attempt > 0).scalar() or 0
    
    reaper_summary = {
        "stale_workers_detected": stale_workers,
        "recovered_jobs_count": recovered_jobs,
        "dead_letter_total": dead_letter_count
    }
    
    # 8. Phase 7 Bonus Features Observability
    from backend.app.core.rate_limiter import limiter
    from backend.app.routers.jobs import batch_jobs_counter
    from backend.app.models import JobDependency

    blocked_subquery = db.query(JobDependency.job_id).join(
        Job, JobDependency.depends_on_job_id == Job.id
    ).filter(Job.status != "COMPLETED").subquery()

    dependency_blocked_jobs = db.query(func.count(Job.id)).filter(
        Job.status == "QUEUED",
        Job.id.in_(db.query(blocked_subquery.c.job_id))
    ).scalar() or 0

    failure_summaries_generated = db.query(func.count(Job.id)).filter(
        Job.status.in_(["FAILED", "DEAD_LETTER"])
    ).scalar() or 0

    bonus_metrics = {
        "batch_jobs_created": batch_jobs_counter,
        "dependency_blocked_jobs": dependency_blocked_jobs,
        "rate_limit_rejections": limiter.rejection_count,
        "failure_summaries_generated": failure_summaries_generated
    }

    return {
        "timestamp": now.isoformat(),
        "jobs": jobs_summary,
        "system_overview": system_overview,
        "workers": workers_summary,
        "worker_metrics": workers_summary,
        "worker_nodes": worker_nodes_detail,
        "queues": queue_utilization,
        "queue_utilization": queue_utilization,
        "throughput": {
            "completed_last_5m": completed_last_5m,
            "completed_last_15m": completed_last_15m,
            "completed_last_hour": completed_last_hour,
            "failed_last_hour": failed_last_hour,
            "avg_jobs_per_minute": throughput_per_min
        },
        "execution_performance": execution_performance,
        "scheduler": scheduler_summary,
        "reaper": reaper_summary,
        "bonus_features": bonus_metrics
    }

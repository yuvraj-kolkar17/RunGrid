from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import uuid

from backend.app.core.database import get_db
from backend.app.models import (
    Job, Queue, Project, User, Worker, JobExecution, JobLog,
    DeadLetterJob, JobDependency, BatchSubmission, ScheduledJob
)
from backend.app.core.rate_limiter import limiter
from backend.app.routers.deps import get_current_user, require_role
from backend.app.services.failure_summary import FailureSummaryService

router = APIRouter(prefix="/platform", tags=["Platform Operations"])


# 1. Platform Overview Endpoint
@router.get("/overview", response_model=Dict[str, Any])
def get_platform_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Operational summary metrics for the Platform Operations Center."""
    now = datetime.now(timezone.utc)
    org_id = current_user.organization_id

    # Base query for organization jobs
    base_job_query = db.query(Job).join(Queue).join(Project).filter(Project.organization_id == org_id)

    total_jobs = base_job_query.count()

    # Batch jobs count (either from batch_submissions or jobs with batch_id)
    batch_jobs_created = db.query(func.count(Job.id)).join(Queue).join(Project).filter(
        Project.organization_id == org_id,
        Job.batch_id.isnot(None)
    ).scalar() or 0

    # Dependency blocked jobs
    blocked_subquery = db.query(JobDependency.job_id).join(
        Job, JobDependency.depends_on_job_id == Job.id
    ).filter(Job.status != "COMPLETED").subquery()

    dependency_blocks = db.query(func.count(Job.id)).join(Queue).join(Project).filter(
        Project.organization_id == org_id,
        Job.status == "QUEUED",
        Job.id.in_(db.query(blocked_subquery.c.job_id))
    ).scalar() or 0

    # Rate limit rejections
    rate_limit_rejections = limiter.rejection_count

    # Failure analyses generated
    failure_analyses = base_job_query.filter(Job.status.in_(["FAILED", "DEAD_LETTER"])).count()

    # System Health
    workers = db.query(Worker).all()
    active_workers = 0
    stale_workers = 0
    inactive_workers = 0
    for w in workers:
        hb_time = w.last_heartbeat_at
        if hb_time and hb_time.tzinfo is None:
            hb_time = hb_time.replace(tzinfo=timezone.utc)
        hb_age = (now - hb_time).total_seconds() if hb_time else 9999.0

        if w.status == "INACTIVE":
            inactive_workers += 1
        elif hb_age <= 60.0:
            active_workers += 1
        else:
            stale_workers += 1

    system_health = "HEALTHY" if active_workers > 0 else ("DEGRADED" if stale_workers > 0 else "CRITICAL")

    # Queue stats
    queues = db.query(Queue).join(Project).filter(Project.organization_id == org_id).all()
    total_queues = len(queues)
    paused_queues = sum(1 for q in queues if q.is_paused)

    return {
        "timestamp": now.isoformat(),
        "organization_id": str(org_id),
        "summary": {
            "batch_jobs_created": batch_jobs_created,
            "dependency_blocks": dependency_blocks,
            "rate_limit_rejections": rate_limit_rejections,
            "failure_analyses": failure_analyses
        },
        "system_health": {
            "status": system_health,
            "total_workers": len(workers),
            "active_workers": active_workers,
            "stale_workers": stale_workers,
            "inactive_workers": inactive_workers,
            "total_queues": total_queues,
            "paused_queues": paused_queues,
            "total_jobs": total_jobs
        }
    }


import os
import json
import urllib.request
import urllib.parse

def fetch_prometheus_data() -> Dict[str, Any]:
    """Helper to query local or internal Prometheus server for active target health and execution quantiles."""
    prom_url = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    urls_to_try = [prom_url, "http://localhost:9090"]
    
    for base in urls_to_try:
        try:
            # 1. Fetch Targets
            targets_url = f"{base}/api/v1/targets"
            req = urllib.request.Request(targets_url, headers={"User-Agent": "FastAPI-Backend"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                targets_data = json.loads(resp.read().decode("utf-8"))
            
            active_targets = []
            if targets_data.get("status") == "success":
                for t in targets_data.get("data", {}).get("activeTargets", []):
                    active_targets.append({
                        "job": t.get("labels", {}).get("job", "unknown"),
                        "instance": t.get("discoveredLabels", {}).get("__address__", t.get("scrapeUrl", "")),
                        "health": t.get("health", "").upper(),
                        "last_scrape": t.get("lastScrape", ""),
                        "last_error": t.get("lastError", "")
                    })

            # 2. Fetch Latency Quantiles (P50, P95, P99)
            quantiles_ms = {"p50": 0.0, "p95": 0.0, "p99": 0.0}
            for q_name, q_val in [("p50", 0.50), ("p95", 0.95), ("p99", 0.99)]:
                query = f"histogram_quantile({q_val}, sum(rate(scheduler_jobs_execution_duration_seconds_bucket[5m])) by (le))"
                query_url = f"{base}/api/v1/query?query=" + urllib.parse.quote(query)
                req_q = urllib.request.Request(query_url, headers={"User-Agent": "FastAPI-Backend"})
                with urllib.request.urlopen(req_q, timeout=1.5) as q_resp:
                    q_data = json.loads(q_resp.read().decode("utf-8"))
                    if q_data.get("status") == "success":
                        results = q_data.get("data", {}).get("result", [])
                        if results and len(results) > 0:
                            val = float(results[0].get("value", [0, 0])[1])
                            if not (val != val):  # Check NaN
                                quantiles_ms[q_name] = round(val * 1000.0, 2)

            return {
                "status": "HEALTHY",
                "url": base,
                "targets": active_targets,
                "quantiles_ms": quantiles_ms
            }
        except Exception:
            continue
            
    return {
        "status": "UNREACHABLE",
        "url": prom_url,
        "targets": [],
        "quantiles_ms": {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    }


def fetch_prometheus_timeseries(range_str: str = "15m", step_param: Optional[Any] = None) -> Dict[str, Any]:
    """Queries Prometheus HTTP /api/v1/query_range for real job throughput & latency quantiles."""
    range_seconds_map = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600}
    default_step_map = {"5m": 5, "15m": 10, "30m": 15, "1h": 30}
    
    range_sec = range_seconds_map.get(range_str)
    if not range_sec:
        if range_str.endswith("m") and range_str[:-1].isdigit():
            range_sec = int(range_str[:-1]) * 60
        elif range_str.endswith("s") and range_str[:-1].isdigit():
            range_sec = int(range_str[:-1])
        elif range_str.endswith("h") and range_str[:-1].isdigit():
            range_sec = int(range_str[:-1]) * 3600
        else:
            range_str = "15m"
            range_sec = 900

    step_sec = None
    if step_param is not None:
        s_str = str(step_param).strip().rstrip("s")
        if s_str.isdigit():
            step_sec = int(s_str)
    
    if not step_sec or step_sec <= 0:
        step_sec = default_step_map.get(range_str, max(1, range_sec // 90))

    now_ts = int(datetime.now(timezone.utc).timestamp())
    start_ts = now_ts - range_sec
    end_ts = now_ts

    prom_url = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
    urls_to_try = [prom_url, "http://localhost:9090"]

    queries = {
        "completed": "rate(scheduler_jobs_completed_total[1m])",
        "failed": "rate(scheduler_jobs_failed_total[1m])",
        "retry": "rate(scheduler_jobs_retried_total[1m])",
        "dlq": "rate(scheduler_jobs_dead_lettered_total[1m])",
        "http": "sum(rate(scheduler_http_requests_total[1m]))",
        "p50": "histogram_quantile(0.50, sum(rate(scheduler_jobs_execution_duration_seconds_bucket[5m])) by (le))",
        "p95": "histogram_quantile(0.95, sum(rate(scheduler_jobs_execution_duration_seconds_bucket[5m])) by (le))",
        "p99": "histogram_quantile(0.99, sum(rate(scheduler_jobs_execution_duration_seconds_bucket[5m])) by (le))"
    }

    raw_results: Dict[str, Any] = {}
    prom_status = "UNREACHABLE"

    for base in urls_to_try:
        try:
            success = False
            for key, expr in queries.items():
                params = urllib.parse.urlencode({
                    "query": expr,
                    "start": start_ts,
                    "end": end_ts,
                    "step": f"{step_sec}s"
                })
                url = f"{base}/api/v1/query_range?{params}"
                req = urllib.request.Request(url, headers={"User-Agent": "FastAPI-Backend"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    if res_data.get("status") == "success":
                        raw_results[key] = res_data.get("data", {}).get("result", [])
                        success = True
            
            if success:
                prom_status = "HEALTHY"
                break
        except Exception:
            continue

    def safe_num(v: Any) -> float:
        try:
            f = float(v)
            if f != f or f == float('inf') or f == float('-inf'):
                return 0.0
            return max(0.0, f)
        except (ValueError, TypeError):
            return 0.0

    points_by_ts: Dict[int, Dict[str, float]] = {}

    for metric_key, result_list in raw_results.items():
        if not result_list:
            continue
        for item in result_list:
            values = item.get("values", [])
            for ts_val in values:
                ts = int(ts_val[0])
                val = safe_num(ts_val[1])
                if ts not in points_by_ts:
                    points_by_ts[ts] = {
                        "completed": 0.0, "failed": 0.0, "retry": 0.0, "dlq": 0.0,
                        "http": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0
                    }
                points_by_ts[ts][metric_key] += val

    sorted_timestamps = sorted(points_by_ts.keys())
    series = []

    for ts in sorted_timestamps:
        p = points_by_ts[ts]
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        t_label = dt.strftime("%H:%M:%S")

        c_sec = round(p["completed"], 3)
        f_sec = round(p["failed"], 3)
        r_sec = round(p["retry"], 3)
        d_sec = round(p["dlq"], 3)
        tp = round(c_sec + f_sec + r_sec + d_sec, 3)

        series.append({
            "timestamp": ts,
            "time_label": t_label,
            "completed_per_second": c_sec,
            "failed_per_second": f_sec,
            "retry_per_second": r_sec,
            "dlq_per_second": d_sec,
            "throughput": tp,
            "http_rate": round(p["http"], 3),
            "p50_ms": round(p["p50"] * 1000.0, 2),
            "p95_ms": round(p["p95"] * 1000.0, 2),
            "p99_ms": round(p["p99"] * 1000.0, 2)
        })

    # If series is empty (e.g. freshly started Prometheus or no datapoints returned yet), fill real timestamps
    if not series and prom_status == "HEALTHY":
        for ts in range(start_ts, end_ts + 1, step_sec):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            series.append({
                "timestamp": ts,
                "time_label": dt.strftime("%H:%M:%S"),
                "completed_per_second": 0.0,
                "failed_per_second": 0.0,
                "retry_per_second": 0.0,
                "dlq_per_second": 0.0,
                "throughput": 0.0,
                "http_rate": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0
            })

    latest_pt = series[-1] if series else {
        "throughput": 0.0, "completed_per_second": 0.0, "failed_per_second": 0.0,
        "retry_per_second": 0.0, "dlq_per_second": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0
    }

    return {
        "range": range_str,
        "step": step_sec,
        "prometheus_status": prom_status,
        "series": series,
        "latest_values": {
            "throughput": latest_pt.get("throughput", 0.0),
            "completed": latest_pt.get("completed_per_second", 0.0),
            "failed": latest_pt.get("failed_per_second", 0.0),
            "retry": latest_pt.get("retry_per_second", 0.0),
            "dlq": latest_pt.get("dlq_per_second", 0.0),
            "p50_ms": latest_pt.get("p50_ms", 0.0),
            "p95_ms": latest_pt.get("p95_ms", 0.0),
            "p99_ms": latest_pt.get("p99_ms", 0.0)
        }
    }


# 2. Observability Endpoint
@router.get("/observability", response_model=Dict[str, Any])
def get_platform_observability(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Complete operational observability dashboard metrics."""
    now = datetime.now(timezone.utc)
    org_id = current_user.organization_id

    # 1. Update DB state gauges
    from backend.app.core.prometheus_metrics import update_db_state_gauges
    update_db_state_gauges(db)

    # 2. Fetch Prometheus Telemetry & Target Health
    prom_data = fetch_prometheus_data()

    # 3. Job states breakdown
    status_counts_raw = db.query(Job.status, func.count(Job.id)).join(Queue).join(Project).filter(
        Project.organization_id == org_id
    ).group_by(Job.status).all()

    status_counts = {status: count for status, count in status_counts_raw}
    dead_letter_count = db.query(func.count(DeadLetterJob.id)).join(Queue).join(Project).filter(
        Project.organization_id == org_id
    ).scalar() or 0

    job_states = {
        "queued": status_counts.get("QUEUED", 0),
        "scheduled": status_counts.get("SCHEDULED", 0),
        "claimed": status_counts.get("CLAIMED", 0),
        "running": status_counts.get("RUNNING", 0),
        "completed": status_counts.get("COMPLETED", 0),
        "failed": status_counts.get("FAILED", 0),
        "retry_waiting": status_counts.get("RETRY_WAITING", 0),
        "dead_letter": dead_letter_count,
        "total": sum(status_counts.values()) + dead_letter_count
    }

    # 4. Throughput area chart history (last 12 5-minute buckets = 1 hour)
    throughput_series = []
    for i in range(11, -1, -1):
        bucket_end = now - timedelta(minutes=i * 5)
        bucket_start = bucket_end - timedelta(minutes=5)
        
        comp = db.query(func.count(Job.id)).join(Queue).join(Project).filter(
            Project.organization_id == org_id,
            Job.status == "COMPLETED",
            Job.completed_at >= bucket_start,
            Job.completed_at < bucket_end
        ).scalar() or 0

        fail = db.query(func.count(Job.id)).join(Queue).join(Project).filter(
            Project.organization_id == org_id,
            Job.status.in_(["FAILED", "DEAD_LETTER"]),
            Job.failed_at >= bucket_start,
            Job.failed_at < bucket_end
        ).scalar() or 0

        throughput_series.append({
            "timestamp": bucket_end.strftime("%H:%M"),
            "completed": comp,
            "failed": fail,
            "rate_per_min": round((comp + fail) / 5.0, 2)
        })

    # 5. Execution performance
    executions = db.query(JobExecution).join(Job).join(Queue).join(Project).filter(
        Project.organization_id == org_id,
        JobExecution.finished_at.isnot(None),
        JobExecution.started_at.isnot(None)
    ).all()

    durations_ms = []
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

    durations_ms.sort()
    avg_dur = round(sum(durations_ms) / len(durations_ms), 2) if durations_ms else 0.0

    # Calculate fallback quantiles if Prometheus quantiles are 0.0
    p50_fallback = durations_ms[int(len(durations_ms) * 0.50)] if durations_ms else 0.0
    p95_fallback = durations_ms[int(len(durations_ms) * 0.95)] if durations_ms else 0.0
    p99_fallback = durations_ms[int(len(durations_ms) * 0.99)] if durations_ms else 0.0

    p50 = prom_data["quantiles_ms"]["p50"] or round(p50_fallback, 2)
    p95 = prom_data["quantiles_ms"]["p95"] or round(p95_fallback, 2)
    p99 = prom_data["quantiles_ms"]["p99"] or round(p99_fallback, 2)

    # 6. Worker processes telemetry
    workers_raw = db.query(Worker).all()
    workers_telemetry = []

    for w in workers_raw:
        active = db.query(func.count(Job.id)).filter(
            Job.claimed_by_worker_id == w.id,
            Job.status.in_(["CLAIMED", "RUNNING"])
        ).scalar() or 0
        limit = w.max_concurrency or 5
        workers_telemetry.append({
            "id": str(w.id),
            "hostname": w.hostname,
            "ip_address": w.ip_address,
            "status": w.status,
            "active_jobs": active,
            "max_concurrency": limit,
            "capacity_ratio": round(active / limit, 4) if limit > 0 else 0.0,
            "last_heartbeat_at": w.last_heartbeat_at.isoformat() if w.last_heartbeat_at else None
        })

    # 7. Queues telemetry
    queues_raw = db.query(Queue).join(Project).filter(
        Project.organization_id == org_id
    ).all()
    queues_telemetry = []
    for q in queues_raw:
        active_c = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status.in_(["CLAIMED", "RUNNING"])
        ).scalar() or 0
        queued_c = db.query(func.count(Job.id)).filter(
            Job.queue_id == q.id,
            Job.status == "QUEUED"
        ).scalar() or 0
        limit = q.concurrency_limit or 100
        queues_telemetry.append({
            "id": str(q.id),
            "name": q.name,
            "project_name": q.project.name if q.project else "Default",
            "concurrency_limit": limit,
            "active_jobs": active_c,
            "queued_jobs": queued_c,
            "utilization_pct": round((active_c / limit) * 100.0, 1) if limit > 0 else 0.0
        })

    return {
        "timestamp": now.isoformat(),
        "prometheus": prom_data,
        "job_states": job_states,
        "throughput_series": throughput_series,
        "execution_performance": {
            "completed_executions": completed_execs,
            "failed_executions": failed_execs,
            "avg_duration_ms": avg_dur,
            "p50_duration_ms": p50,
            "p95_duration_ms": p95,
            "p99_duration_ms": p99,
            "total_executions": len(executions)
        },
        "workers": workers_telemetry,
        "queues": queues_telemetry,
        "rate_limiting": limiter.get_status()
    }


@router.get("/observability/timeseries", response_model=Dict[str, Any])
def get_platform_observability_timeseries(
    range: str = Query(default="15m", description="Time window range e.g. 5m, 15m, 30m, 1h"),
    step: Optional[str] = Query(default=None, description="Step size e.g. 5s, 10s, 15s, 30s"),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Real-time Prometheus range query time-series telemetry for throughput and latency."""
    return fetch_prometheus_timeseries(range_str=range, step_param=step)


# 3. Batches List & Detail

@router.get("/batches", response_model=Dict[str, Any])
def list_batch_submissions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Lists atomic batch submissions for the organization."""
    org_id = current_user.organization_id
    query = db.query(BatchSubmission).filter(BatchSubmission.organization_id == org_id)

    total = query.count()
    offset = (page - 1) * page_size
    batches = query.order_by(BatchSubmission.created_at.desc()).offset(offset).limit(page_size).all()

    items = []
    total_batch_jobs = 0
    successful_batches = 0
    failed_batches = 0

    for b in batches:
        b_jobs = db.query(Job).filter(Job.batch_id == b.id).all()
        completed_jobs = sum(1 for j in b_jobs if j.status == "COMPLETED")
        failed_jobs = sum(1 for j in b_jobs if j.status in ("FAILED", "DEAD_LETTER"))
        total_b_jobs = len(b_jobs) if len(b_jobs) > 0 else b.total_jobs

        total_batch_jobs += total_b_jobs
        if total_b_jobs > 0 and completed_jobs == total_b_jobs:
            status_str = "COMPLETED"
            successful_batches += 1
        elif failed_jobs > 0:
            status_str = "PARTIAL_FAILURE" if completed_jobs > 0 else "FAILED"
            failed_batches += 1
        else:
            status_str = b.status

        items.append({
            "id": str(b.id),
            "name": b.name or f"Batch {str(b.id)[:8]}",
            "status": status_str,
            "total_jobs": total_b_jobs,
            "successful_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "created_at": b.created_at.isoformat() if b.created_at else None
        })

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "summary": {
            "total_batches": total,
            "total_batch_jobs": total_batch_jobs,
            "successful_batches": successful_batches,
            "failed_batches": failed_batches
        }
    }


@router.get("/batches/{batch_id}", response_model=Dict[str, Any])
def get_batch_detail(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Retrieves batch details and list of jobs associated with a batch."""
    org_id = current_user.organization_id
    batch = db.query(BatchSubmission).filter(
        BatchSubmission.id == batch_id,
        BatchSubmission.organization_id == org_id
    ).first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "BATCH_NOT_FOUND", "message": "Batch submission not found"}
        )

    jobs = db.query(Job).filter(Job.batch_id == batch.id).order_by(Job.created_at.asc()).all()

    completed_jobs = sum(1 for j in jobs if j.status == "COMPLETED")
    failed_jobs = sum(1 for j in jobs if j.status in ("FAILED", "DEAD_LETTER"))

    return {
        "id": str(batch.id),
        "name": batch.name,
        "status": batch.status,
        "total_jobs": len(jobs),
        "successful_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "jobs": [
            {
                "id": str(j.id),
                "task_type": j.task_type,
                "status": j.status,
                "queue_id": str(j.queue_id),
                "priority": j.priority,
                "attempt": j.attempt,
                "created_at": j.created_at.isoformat() if j.created_at else None
            }
            for j in jobs
        ]
    }


# 4. Workflows & Dependency Graph
@router.get("/workflows", response_model=Dict[str, Any])
def get_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Aggregates workflow DAGs from real job dependency records."""
    org_id = current_user.organization_id

    # Fetch all job dependencies for the organization
    deps = db.query(JobDependency).join(
        Job, JobDependency.job_id == Job.id
    ).join(Queue).join(Project).filter(
        Project.organization_id == org_id
    ).all()

    if not deps:
        return {"workflows": [], "total_dependencies": 0}

    # Group into connected component DAGs
    parent_map: Dict[str, List[str]] = {}
    child_map: Dict[str, List[str]] = {}
    all_job_ids = set()

    for d in deps:
        child_id = str(d.job_id)
        parent_id = str(d.depends_on_job_id)
        all_job_ids.add(child_id)
        all_job_ids.add(parent_id)

        parent_map.setdefault(child_id, []).append(parent_id)
        child_map.setdefault(parent_id, []).append(child_id)

    # Fetch details for involved jobs
    jobs = db.query(Job).filter(Job.id.in_([uuid.UUID(jid) for jid in all_job_ids])).all()
    job_dict = {str(j.id): j for j in jobs}

    # Identify root jobs (jobs that do not depend on any parent, but have dependents)
    root_job_ids = [jid for jid in all_job_ids if jid not in parent_map]

    workflows = []
    for root_id in root_job_ids:
        root_job = job_dict.get(root_id)
        if not root_job:
            continue

        # Traverse DAG to find all connected nodes
        visited = set()
        stack = [root_id]
        nodes = []
        edges = []

        while stack:
            curr = stack.pop()
            if curr in visited:
                continue
            visited.add(curr)

            j_obj = job_dict.get(curr)
            if j_obj:
                # Check if job is blocked by incomplete dependencies
                p_ids = parent_map.get(curr, [])
                is_blocked = any(
                    job_dict.get(pid) and job_dict[pid].status != "COMPLETED"
                    for pid in p_ids
                )

                nodes.append({
                    "id": curr,
                    "title": j_obj.payload.get("title") or j_obj.task_type,
                    "task_type": j_obj.task_type,
                    "status": j_obj.status,
                    "is_blocked": is_blocked,
                    "parent_ids": p_ids
                })

                for cid in child_map.get(curr, []):
                    edges.append({"source": curr, "target": cid})
                    if cid not in visited:
                        stack.append(cid)

        completed_count = sum(1 for n in nodes if n["status"] == "COMPLETED")
        running_count = sum(1 for n in nodes if n["status"] in ("RUNNING", "CLAIMED"))
        blocked_count = sum(1 for n in nodes if n["is_blocked"])
        failed_count = sum(1 for n in nodes if n["status"] in ("FAILED", "DEAD_LETTER"))

        if completed_count == len(nodes):
            wf_status = "COMPLETED"
        elif failed_count > 0:
            wf_status = "FAILED"
        elif running_count > 0:
            wf_status = "RUNNING"
        elif blocked_count > 0:
            wf_status = "BLOCKED"
        else:
            wf_status = "PENDING"

        workflows.append({
            "id": f"wf-{root_id[:8]}",
            "name": root_job.payload.get("title") or root_job.task_type or "Customer Workflow",
            "root_job_id": root_id,
            "total_jobs": len(nodes),
            "completed_jobs": completed_count,
            "running_jobs": running_count,
            "blocked_jobs": blocked_count,
            "failed_jobs": failed_count,
            "status": wf_status,
            "nodes": nodes,
            "edges": edges
        })

    return {
        "workflows": workflows,
        "total_dependencies": len(deps)
    }


# 5. Rate Limiting Status & Test Control
@router.get("/rate-limits", response_model=Dict[str, Any])
def get_rate_limit_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Returns real-time status and policies of the process-local rate limiter."""
    return limiter.get_status()


@router.post("/rate-limits/test", response_model=Dict[str, Any])
def trigger_rate_limit_test(
    num_requests: int = Query(default=25, ge=1, le=150),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["OWNER", "ADMIN"]))
) -> Dict[str, Any]:
    """Operator test control endpoint to send test requests and verify rate limit rejections (HTTP 429)."""
    endpoint_key = f"user:{current_user.id}:batch"
    max_requests = 20
    window_seconds = 60

    allowed = 0
    rejected = 0

    for _ in range(num_requests):
        try:
            limiter.check_rate_limit(endpoint_key, max_requests=max_requests, window_seconds=window_seconds)
            allowed += 1
        except HTTPException as e:
            if e.status_code == 429:
                rejected += 1
            else:
                raise e

    return {
        "tested_key": endpoint_key,
        "configured_limit": f"{max_requests} req / {window_seconds}s",
        "requests_sent": num_requests,
        "allowed_requests": allowed,
        "rejected_429_requests": rejected,
        "limiter_total_rejections": limiter.rejection_count
    }


# 6. Failure Analysis Endpoint
@router.get("/failures", response_model=Dict[str, Any])
def get_failure_analysis(
    status_filter: Optional[str] = Query(default=None),
    task_type: Optional[str] = Query(default=None),
    queue_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Central failure investigation with automated diagnostic analyses."""
    org_id = current_user.organization_id

    query = db.query(Job).join(Queue).join(Project).filter(
        Project.organization_id == org_id,
        Job.status.in_(["FAILED", "RETRY_WAITING", "DEAD_LETTER"])
    )

    if status_filter:
        query = query.filter(Job.status == status_filter)
    if queue_id:
        query = query.filter(Job.queue_id == queue_id)
    if task_type:
        query = query.filter(Job.payload["task_type"].astext == task_type)

    total = query.count()
    offset = (page - 1) * page_size
    failed_jobs = query.order_by(Job.updated_at.desc()).offset(offset).limit(page_size).all()

    items = []
    cause_counts: Dict[str, int] = {}

    for job in failed_jobs:
        # Generate automated diagnostic summary
        logs = db.query(JobLog).filter(JobLog.job_id == job.id).order_by(JobLog.created_at.asc()).all()
        summary = FailureSummaryService.generate_summary(
            task_type=job.task_type,
            error_message=job.error,
            attempt=job.attempt,
            max_retries=job.max_retries,
            logs=logs
        )

        cause = summary.get("likely_cause", "Execution Error")
        cause_counts[cause] = cause_counts.get(cause, 0) + 1

        items.append({
            "id": str(job.id),
            "task_type": job.task_type,
            "title": job.payload.get("title") or job.task_type,
            "status": job.status,
            "queue_id": str(job.queue_id),
            "attempt": job.attempt,
            "max_retries": job.max_retries,
            "worker_id": str(job.claimed_by_worker_id) if job.claimed_by_worker_id else None,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "failure_analysis": summary
        })

    # Sort top failure causes
    top_causes = [
        {"cause": cause, "count": count}
        for cause, count in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "top_failure_causes": top_causes
    }

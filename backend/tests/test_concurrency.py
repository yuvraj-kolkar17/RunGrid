import uuid
import pytest
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models import Organization, Project, Queue, Job, Worker, RetryPolicy, ScheduledJob
from backend.app.services.claiming import claim_job
from backend.app.services.transitions import start_job, complete_job, fail_job
from backend.app.services.reaper import reap_stale_workers_and_jobs
from backend.app.services.scheduler import run_scheduler_cycle, initialize_scheduled_job
from backend.app.services.retry import calculate_delay

def test_retry_policy_calculator():
    # Fixed
    assert calculate_delay("fixed", 10, 1) == 10
    assert calculate_delay("fixed", 10, 3) == 10
    
    # Linear
    assert calculate_delay("linear", 5, 1) == 5
    assert calculate_delay("linear", 5, 2) == 10
    assert calculate_delay("linear", 5, 3) == 15
    
    # Exponential
    assert calculate_delay("exponential", 2, 1) == 2
    assert calculate_delay("exponential", 2, 2) == 4
    assert calculate_delay("exponential", 2, 3) == 8
    
    with pytest.raises(ValueError):
        calculate_delay("fixed", -1, 1)
    with pytest.raises(ValueError):
        calculate_delay("fixed", 10, 0)
    with pytest.raises(ValueError):
        calculate_delay("unknown", 10, 1)


def test_duplicate_claiming():
    db = SessionLocal()
    try:
        # Create Org, Project, Queue, Worker
        org = Organization(name="Test Org Dup")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Dup", organization_id=org.id)
        db.add(proj)
        db.flush()
        queue = Queue(name="test_q_dup", project_id=proj.id, concurrency_limit=100)
        db.add(queue)
        db.flush()
        
        # Register 5 workers
        workers = []
        for i in range(5):
            w = Worker(id=uuid.uuid4(), hostname=f"worker-dup-{i}", ip_address="127.0.0.1", status="ACTIVE")
            db.add(w)
            workers.append(w)
        db.flush()
        
        # Create 50 jobs
        jobs = []
        for i in range(50):
            j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", payload={"num": i})
            db.add(j)
            jobs.append(j)
        db.commit()
        
        claimed_ids = []
        
        def poll_jobs(worker_id):
            thread_db = SessionLocal()
            jobs_claimed = []
            try:
                while True:
                    job = claim_job(thread_db, worker_id)
                    if job:
                        jobs_claimed.append(job.id)
                        thread_db.commit()
                    else:
                        # If claim returned None (due to skip locked or empty queue),
                        # check if there are actually any QUEUED jobs left in the db.
                        # If none, we are done. Otherwise, retry polling.
                        queued_count = thread_db.query(Job).filter(Job.status == "QUEUED").count()
                        if queued_count == 0:
                            break
            finally:
                thread_db.close()
            return jobs_claimed
            
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(poll_jobs, w.id) for w in workers]
            for fut in as_completed(futures):
                claimed_ids.extend(fut.result())
                
        # Assertions
        assert len(claimed_ids) == 50
        assert len(set(claimed_ids)) == 50  # 50 unique claims (no duplicates)
    finally:
        db.delete(org)
        for w in workers:
            db.delete(w)
        db.commit()
        db.close()


def test_queue_concurrency():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Queue Con")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Queue Con", organization_id=org.id)
        db.add(proj)
        db.flush()
        # Concurrency limit = 3
        queue = Queue(name="test_q_queue_con", project_id=proj.id, concurrency_limit=3)
        db.add(queue)
        db.flush()
        
        workers = []
        for i in range(5):
            w = Worker(id=uuid.uuid4(), hostname=f"worker-con-{i}", ip_address="127.0.0.1", status="ACTIVE")
            db.add(w)
            workers.append(w)
        db.flush()
        
        # Create 20 jobs
        for i in range(20):
            j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", payload={"num": i})
            db.add(j)
        db.commit()
        
        max_active_seen = 0
        
        def worker_loop(worker_id):
            nonlocal max_active_seen
            thread_db = SessionLocal()
            try:
                for _ in range(8):
                    job = claim_job(thread_db, worker_id)
                    if job:
                        # Transition to RUNNING
                        start_job(thread_db, job.id, worker_id)
                        thread_db.commit()
                        
                        # Count active running/claimed jobs in the queue
                        active_count = thread_db.query(Job).filter(
                            Job.queue_id == queue.id,
                            Job.status.in_(["CLAIMED", "RUNNING"])
                        ).count()
                        
                        if active_count > max_active_seen:
                            max_active_seen = active_count
                            
                        # Complete the job immediately
                        complete_job(thread_db, job.id)
                        thread_db.commit()
            finally:
                thread_db.close()
                
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker_loop, w.id) for w in workers]
            for fut in futures:
                fut.result()
                
        # Assertions
        assert max_active_seen <= 3
    finally:
        db.delete(org)
        for w in workers:
            db.delete(w)
        db.commit()
        db.close()


def test_different_queues():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Diff Q")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Diff Q", organization_id=org.id)
        db.add(proj)
        db.flush()
        
        queue_a = Queue(name="test_q_diff_a", project_id=proj.id, concurrency_limit=2)
        queue_b = Queue(name="test_q_diff_b", project_id=proj.id, concurrency_limit=2)
        db.add_all([queue_a, queue_b])
        db.flush()
        
        workers = []
        for i in range(4):
            w = Worker(id=uuid.uuid4(), hostname=f"worker-diff-{i}", ip_address="127.0.0.1", status="ACTIVE")
            db.add(w)
            workers.append(w)
        db.flush()
        
        # 10 jobs in queue A, 10 in queue B
        for i in range(10):
            j_a = Job(id=uuid.uuid4(), queue_id=queue_a.id, status="QUEUED", payload={"num": i})
            j_b = Job(id=uuid.uuid4(), queue_id=queue_b.id, status="QUEUED", payload={"num": i})
            db.add_all([j_a, j_b])
        db.commit()
        
        def run_worker(worker_id):
            thread_db = SessionLocal()
            try:
                for _ in range(10):
                    job = claim_job(thread_db, worker_id)
                    if job:
                        start_job(thread_db, job.id, worker_id)
                        thread_db.commit()
                        complete_job(thread_db, job.id)
                        thread_db.commit()
            finally:
                thread_db.close()
                
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_worker, w.id) for w in workers]
            for fut in futures:
                fut.result()
                
        count_completed_a = db.query(Job).filter(Job.queue_id == queue_a.id, Job.status == "COMPLETED").count()
        count_completed_b = db.query(Job).filter(Job.queue_id == queue_b.id, Job.status == "COMPLETED").count()
        assert count_completed_a > 0
        assert count_completed_b > 0
    finally:
        db.delete(org)
        for w in workers:
            db.delete(w)
        db.commit()
        db.close()


def test_paused_queue():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Paused")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Paused", organization_id=org.id)
        db.add(proj)
        db.flush()
        
        # Paused Queue
        queue = Queue(name="test_q_paused", project_id=proj.id, concurrency_limit=5, is_paused=True)
        db.add(queue)
        db.flush()
        
        w = Worker(id=uuid.uuid4(), hostname="worker-paused", ip_address="127.0.0.1", status="ACTIVE")
        db.add(w)
        db.flush()
        
        j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", payload={"num": 1})
        db.add(j)
        db.commit()
        
        job = claim_job(db, w.id)
        assert job is None  # Cannot claim from paused queue
    finally:
        db.delete(org)
        db.delete(w)
        db.commit()
        db.close()


def test_job_priority_claiming():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Priority")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Priority", organization_id=org.id)
        db.add(proj)
        db.flush()
        
        queue = Queue(name="test_q_priority", project_id=proj.id)
        db.add(queue)
        db.flush()
        
        w = Worker(id=uuid.uuid4(), hostname="worker-priority", ip_address="127.0.0.1", status="ACTIVE")
        db.add(w)
        db.flush()
        
        # Create jobs with priority 0, 5, 10
        j1 = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", priority=0, payload={"num": 0}, created_at=datetime.now(timezone.utc) - timedelta(seconds=10))
        j2 = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", priority=10, payload={"num": 10}, created_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        j3 = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", priority=5, payload={"num": 5})
        db.add_all([j1, j2, j3])
        db.commit()
        
        # Claim first job
        claim1 = claim_job(db, w.id)
        assert claim1.priority == 10  # Highest priority first
        
        # Claim second job
        claim2 = claim_job(db, w.id)
        assert claim2.priority == 5
        
        # Claim third job
        claim3 = claim_job(db, w.id)
        assert claim3.priority == 0
    finally:
        db.delete(org)
        db.delete(w)
        db.commit()
        db.close()


def test_saturated_high_priority_queue():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Sat Q")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Sat Q", organization_id=org.id)
        db.add(proj)
        db.flush()
        
        # Queue A: high priority (10) but capacity limit = 1
        queue_a = Queue(name="test_q_sat_a", project_id=proj.id, priority=10, concurrency_limit=1)
        # Queue B: low priority (5) and capacity limit = 2
        queue_b = Queue(name="test_q_sat_b", project_id=proj.id, priority=5, concurrency_limit=2)
        db.add_all([queue_a, queue_b])
        db.flush()
        
        w1 = Worker(id=uuid.uuid4(), hostname="worker-sat-1", ip_address="127.0.0.1", status="ACTIVE")
        w2 = Worker(id=uuid.uuid4(), hostname="worker-sat-2", ip_address="127.0.0.1", status="ACTIVE")
        db.add_all([w1, w2])
        db.flush()
        
        # Queue A has a claimed/active job
        j_active = Job(id=uuid.uuid4(), queue_id=queue_a.id, status="CLAIMED", claimed_by_worker_id=w1.id, payload={"type": "active"})
        # Both queues have queued jobs
        j_queued_a = Job(id=uuid.uuid4(), queue_id=queue_a.id, status="QUEUED", payload={"type": "a"})
        j_queued_b = Job(id=uuid.uuid4(), queue_id=queue_b.id, status="QUEUED", payload={"type": "b"})
        db.add_all([j_active, j_queued_a, j_queued_b])
        db.commit()
        
        # Worker 2 polls
        job = claim_job(db, w2.id)
        
        # Expected: it must skip saturated Queue A and claim from Queue B
        assert job is not None
        assert job.queue_id == queue_b.id
        assert job.payload["type"] == "b"
    finally:
        db.delete(org)
        db.delete(w1)
        db.delete(w2)
        db.commit()
        db.close()


def test_claimed_worker_crash():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Crash 1")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Crash 1", organization_id=org.id)
        db.add(proj)
        db.flush()
        queue = Queue(name="test_q_crash_1", project_id=proj.id)
        db.add(queue)
        db.flush()
        
        w = Worker(id=uuid.uuid4(), hostname="worker-crash-1", ip_address="127.0.0.1", status="ACTIVE")
        db.add(w)
        db.flush()
        
        # Create job
        j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", attempt=0, payload={"type": "crash"})
        db.add(j)
        db.commit()
        
        # Claim job (transitions to CLAIMED, attempt count remains 0)
        job = claim_job(db, w.id)
        assert job.status == "CLAIMED"
        assert job.attempt == 0
        db.commit()
        
        # Worker crashes (make its last_heartbeat_at very old)
        w.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.commit()
        
        # Run Reaper
        reap_stale_workers_and_jobs(db, heartbeat_timeout_seconds=30)
        db.commit()
        
        # Reload job and worker
        db.refresh(job)
        db.refresh(w)
        
        # Expected: worker is inactive, job is requeued (status=QUEUED), attempt remains 0
        assert w.status == "INACTIVE"
        assert job.status == "QUEUED"
        assert job.attempt == 0
        assert job.claimed_by_worker_id is None
    finally:
        db.delete(org)
        db.delete(w)
        db.commit()
        db.close()


def test_running_worker_crash():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Crash 2")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Crash 2", organization_id=org.id)
        db.add(proj)
        db.flush()
        queue = Queue(name="test_q_crash_2", project_id=proj.id)
        db.add(queue)
        db.flush()
        
        w = Worker(id=uuid.uuid4(), hostname="worker-crash-2", ip_address="127.0.0.1", status="ACTIVE")
        db.add(w)
        db.flush()
        
        # Create job with max_retries = 3
        j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", attempt=0, max_retries=3, payload={"type": "crash"})
        db.add(j)
        db.commit()
        
        # Claim and Start job (transitions to RUNNING, attempt count becomes 1)
        job = claim_job(db, w.id)
        start_job(db, job.id, w.id)
        db.commit()
        
        db.refresh(job)
        assert job.status == "RUNNING"
        assert job.attempt == 1
        
        # Worker crashes
        w.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.commit()
        
        # Run Reaper
        reap_stale_workers_and_jobs(db, heartbeat_timeout_seconds=30)
        db.commit()
        
        # Reload job
        db.refresh(job)
        
        # Expected: job is recovered (status=RETRY_WAITING), attempt remains 1 (not incremented again)
        assert job.status == "RETRY_WAITING"
        assert job.attempt == 1
        assert job.claimed_by_worker_id is None
    finally:
        db.delete(org)
        db.delete(w)
        db.commit()
        db.close()


def test_scheduler_recurring_jobs():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Scheduler")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Scheduler", organization_id=org.id)
        db.add(proj)
        db.flush()
        queue = Queue(name="test_q_sched", project_id=proj.id)
        db.add(queue)
        db.flush()
        
        # 1. ScheduledJob with cron "*/5 * * * *"
        sj = ScheduledJob(
            id=uuid.uuid4(),
            project_id=proj.id,
            queue_id=queue.id,
            name="every_5_minutes",
            cron_expression="*/5 * * * *",
            payload={"type": "cron"},
            is_active=True
        )
        db.add(sj)
        db.flush()
        
        # Initialize
        initialize_scheduled_job(sj)
        db.commit()
        
        assert sj.next_run_at is not None
        
        # Make the scheduled job due by modifying next_run_at to the past
        sj.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Run scheduler cycle
        jobs_created = run_scheduler_cycle(db)
        db.commit()
        
        # Verify
        assert jobs_created == 1
        db.refresh(sj)
        assert sj.last_run_at is not None
        assert sj.next_run_at > datetime.now(timezone.utc)
        
        # Verify job was created in jobs table
        job = db.query(Job).filter(Job.queue_id == queue.id).first()
        assert job is not None
        assert job.status == "QUEUED"
        assert job.payload["type"] == "cron"
    finally:
        db.delete(org)
        db.commit()
        db.close()


def test_reaper_max_attempts_dead_letter():
    db = SessionLocal()
    try:
        org = Organization(name="Test Org Dead")
        db.add(org)
        db.flush()
        proj = Project(name="Test Proj Dead", organization_id=org.id)
        db.add(proj)
        db.flush()
        queue = Queue(name="test_q_dead", project_id=proj.id)
        db.add(queue)
        db.flush()
        
        w = Worker(id=uuid.uuid4(), hostname="worker-dead", ip_address="127.0.0.1", status="ACTIVE")
        db.add(w)
        db.flush()
        
        # Job has attempt = 0 and max_retries = 3
        j = Job(id=uuid.uuid4(), queue_id=queue.id, status="QUEUED", attempt=0, max_retries=3, payload={"type": "dead"})
        db.add(j)
        db.commit()
        
        # Attempt 1
        claim_job(db, w.id)
        start_job(db, j.id, w.id)
        fail_job(db, j.id, "error 1")
        db.commit()
        
        # Attempt 2 (set available_at to now to allow re-claiming)
        j.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        j.status = "QUEUED"
        db.commit()
        claim_job(db, w.id)
        start_job(db, j.id, w.id)
        fail_job(db, j.id, "error 2")
        db.commit()
        
        # Attempt 3 (set available_at to now to allow re-claiming)
        j.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        j.status = "QUEUED"
        db.commit()
        claim_job(db, w.id)
        start_job(db, j.id, w.id)
        db.commit()
        
        db.refresh(j)
        assert j.status == "RUNNING"
        assert j.attempt == 3
        
        # Worker crashes during 3rd attempt
        w.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        db.commit()
        
        # Reaper runs
        reap_stale_workers_and_jobs(db, heartbeat_timeout_seconds=30)
        db.commit()
        
        # Reload
        db.refresh(j)
        
        # Expected: attempt == 3 (max_retries reached), status becomes DEAD_LETTER
        assert j.status == "DEAD_LETTER"
        assert j.attempt == 3
        
        # Check dead_letter_jobs table
        from backend.app.models import DeadLetterJob
        dlq_job = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == j.id).first()
        assert dlq_job is not None
        assert dlq_job.failure_reason == "Execution lease expired and max retries reached."
    finally:
        db.delete(org)
        db.delete(w)
        db.commit()
        db.close()


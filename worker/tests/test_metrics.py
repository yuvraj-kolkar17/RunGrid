import pytest
from worker.metrics import (
    WORKER_JOBS_CLAIMED_TOTAL, WORKER_JOBS_STARTED_TOTAL,
    WORKER_JOBS_COMPLETED_TOTAL, WORKER_ACTIVE_JOBS,
    WORKER_CONCURRENCY_LIMIT, WORKER_CAPACITY_RATIO
)

def test_worker_metrics_counters():
    """Test worker counter increments."""
    init_claimed = WORKER_JOBS_CLAIMED_TOTAL._value.get()
    WORKER_JOBS_CLAIMED_TOTAL.inc()
    assert WORKER_JOBS_CLAIMED_TOTAL._value.get() == init_claimed + 1

    init_completed = WORKER_JOBS_COMPLETED_TOTAL._value.get()
    WORKER_JOBS_COMPLETED_TOTAL.inc()
    assert WORKER_JOBS_COMPLETED_TOTAL._value.get() == init_completed + 1

def test_worker_capacity_gauges():
    """Test worker concurrency and active job capacity gauges."""
    WORKER_CONCURRENCY_LIMIT.set(5)
    WORKER_ACTIVE_JOBS.set(2)
    WORKER_CAPACITY_RATIO.set(2 / 5)

    assert WORKER_CONCURRENCY_LIMIT._value.get() == 5
    assert WORKER_ACTIVE_JOBS._value.get() == 2
    assert WORKER_CAPACITY_RATIO._value.get() == 0.4

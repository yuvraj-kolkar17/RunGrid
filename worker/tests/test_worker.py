import pytest
import asyncio
import signal
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from worker.worker import WorkerProcess
from worker.config import settings
from worker.client import BackendClient

@pytest.fixture
def mock_client():
    client = MagicMock(spec=BackendClient)
    client.register_worker = AsyncMock(return_value={"id": "test-worker-uuid"})
    client.send_heartbeat = AsyncMock()
    client.poll_job = AsyncMock(return_value=None)
    client.start_job = AsyncMock(return_value={"attempt": 1})
    client.complete_job = AsyncMock()
    client.fail_job = AsyncMock()
    client.close = AsyncMock()
    return client

@pytest.mark.asyncio
async def test_worker_registration(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.polling_loop = AsyncMock()
    
    # Run the worker registration and loop setups
    await worker.run()
    
    mock_client.register_worker.assert_called_once_with(worker.hostname, worker.ip_address)
    assert worker.worker_id == "test-worker-uuid"
    
    # Cleanup tasks
    await worker.shutdown()

@pytest.mark.asyncio
async def test_successful_polling_and_execution(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    # Return one job, then None to stop loop
    mock_client.poll_job.side_effect = [
        {"id": "job-1", "task_type": "demo.success", "payload": {"data": "test"}, "attempt": 0},
        None
    ]
    
    # Create polling loop task
    polling_task = asyncio.create_task(worker.polling_loop())
    
    # Let it run for a bit
    await asyncio.sleep(0.2)
    
    # Stop polling
    await worker.shutdown()
    
    mock_client.poll_job.assert_called()
    mock_client.start_job.assert_called_once_with("job-1", "test-worker-uuid")
    mock_client.complete_job.assert_called_once_with("job-1", "test-worker-uuid", {
        "result": {"status": "success", "data": "test"},
        "duration_ms": pytest.approx(100, abs=150)
    })

@pytest.mark.asyncio
async def test_no_job_polling_releases_semaphore(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    # Return no job
    mock_client.poll_job.return_value = None
    
    # Run polling loop for a brief moment
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.1)
    
    # Concurrency limit should be intact (semaphore fully available)
    assert worker.semaphore._value == settings.WORKER_CONCURRENCY
    
    await worker.shutdown()

@pytest.mark.asyncio
async def test_concurrency_limit_enforced(mock_client):
    # Set concurrency limit to 1
    with patch.object(settings, 'WORKER_CONCURRENCY', 1):
        worker = WorkerProcess()
        worker.client = mock_client
        worker.worker_id = "test-worker-uuid"
        
        # Mock poll_job to return a slow job
        mock_client.poll_job.side_effect = [
            {"id": "slow-job", "task_type": "demo.slow", "payload": {"duration": 1.0}, "attempt": 0},
            {"id": "next-job", "task_type": "demo.success", "payload": {}, "attempt": 0},
            None
        ]
        
        polling_task = asyncio.create_task(worker.polling_loop())
        await asyncio.sleep(0.1)
        
        # Since concurrency is 1, the slow-job is running. The semaphore is occupied.
        # It should NOT have polled the second job yet.
        assert worker.get_active_count() == 1
        assert worker.semaphore._value == 0
        mock_client.poll_job.assert_called_once()  # Only slow-job polled
        
        await worker.shutdown()

@pytest.mark.asyncio
async def test_task_failure_reports_fail(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    mock_client.poll_job.side_effect = [
        {"id": "fail-job", "task_type": "demo.failure", "payload": {"error_message": "Failed task"}, "attempt": 0},
        None
    ]
    
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.2)
    await worker.shutdown()
    
    mock_client.start_job.assert_called_once_with("fail-job", "test-worker-uuid")
    mock_client.fail_job.assert_called_once_with(
        "fail-job", "test-worker-uuid", "Task raised exception: Failed task"
    )

@pytest.mark.asyncio
async def test_unknown_task_type(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    mock_client.poll_job.side_effect = [
        {"id": "unknown-job", "task_type": "demo.doesnotexist", "payload": {}, "attempt": 0},
        None
    ]
    
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.2)
    await worker.shutdown()
    
    mock_client.start_job.assert_called_once_with("unknown-job", "test-worker-uuid")
    mock_client.fail_job.assert_called_once_with(
        "unknown-job", "test-worker-uuid", "Unknown task type: demo.doesnotexist"
    )

@pytest.mark.asyncio
async def test_heartbeat_loop_sends_payload(mock_client):
    with patch.object(settings, 'HEARTBEAT_INTERVAL', 0.1):
        worker = WorkerProcess()
        worker.client = mock_client
        worker.worker_id = "test-worker-uuid"
        
        # Start heartbeat
        heartbeat_task = asyncio.create_task(worker.heartbeat_loop())
        await asyncio.sleep(0.25)
        
        # Verify send_heartbeat was called with active jobs, concurrency, and capacity
        mock_client.send_heartbeat.assert_called()
        args, kwargs = mock_client.send_heartbeat.call_args
        assert args[0] == "test-worker-uuid"
        payload = args[1]
        assert payload["status"] == "ACTIVE"
        assert payload["active_jobs"] == 0
        assert payload["max_concurrency"] == settings.WORKER_CONCURRENCY
        assert payload["available_capacity"] == settings.WORKER_CONCURRENCY
        
        heartbeat_task.cancel()

@pytest.mark.asyncio
async def test_backend_temporary_failure_resilience(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    # Raise network exception on first poll, then succeed
    mock_client.poll_job.side_effect = [
        RuntimeError("Temporary network timeout"),
        None
    ]
    
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.1)
    
    # Worker should log error and keep running (not crash)
    assert not polling_task.done()
    
    await worker.shutdown()

@pytest.mark.asyncio
async def test_graceful_shutdown(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    # Start a slow job that will be running during shutdown
    mock_client.poll_job.side_effect = [
        {"id": "slow-job", "task_type": "demo.slow", "payload": {"duration": 0.5}, "attempt": 0},
        None
    ]
    
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.1)
    
    assert worker.get_active_count() == 1
    
    # Trigger shutdown with 1s timeout
    with patch.object(settings, 'SHUTDOWN_TIMEOUT', 1.0):
        await worker.shutdown()
        
    # Active jobs should have drained cleanly since it slept 0.5s and timeout was 1.0s
    assert worker.get_active_count() == 0
    mock_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_graceful_shutdown_abandon_timeout(mock_client):
    worker = WorkerProcess()
    worker.client = mock_client
    worker.worker_id = "test-worker-uuid"
    
    # Slow job takes 2.0s
    mock_client.poll_job.side_effect = [
        {"id": "slow-job", "task_type": "demo.slow", "payload": {"duration": 2.0}, "attempt": 0},
        None
    ]
    
    polling_task = asyncio.create_task(worker.polling_loop())
    await asyncio.sleep(0.1)
    
    assert worker.get_active_count() == 1
    
    # Trigger shutdown with small timeout (0.1s)
    with patch.object(settings, 'SHUTDOWN_TIMEOUT', 0.1):
        await worker.shutdown()
        
    # The job was not finished, but worker exited cleanly without locking up
    assert mock_client.close.called

@pytest.mark.asyncio
async def test_client_idempotent_conflict_handling():
    # Setup mock httpx client that returns HTTP 409 with custom error code
    client = BackendClient()
    mock_resp_start = MagicMock(spec=httpx.Response)
    mock_resp_start.status_code = 409
    mock_resp_start.json.return_value = {
        "error": {
            "code": "ALREADY_STARTED",
            "message": "Already started: Job is in state RUNNING."
        }
    }
    
    mock_resp_complete = MagicMock(spec=httpx.Response)
    mock_resp_complete.status_code = 409
    mock_resp_complete.json.return_value = {
        "error": {
            "code": "ALREADY_COMPLETED",
            "message": "Already completed: Job is in state COMPLETED."
        }
    }

    mock_resp_mismatch = MagicMock(spec=httpx.Response)
    mock_resp_mismatch.status_code = 409
    mock_resp_mismatch.json.return_value = {
        "error": {
            "code": "WORKER_MISMATCH",
            "message": "Worker mismatch: worker does not own job"
        }
    }
    
    # Patch httpx AsyncClient request method
    with patch('httpx.AsyncClient.request', new_callable=AsyncMock) as mock_request:
        # Test ALREADY_STARTED (Start Job) -> Treated as Success
        mock_request.return_value = mock_resp_start
        mock_request.side_effect = httpx.HTTPStatusError("Conflict", request=MagicMock(), response=mock_resp_start)
        res = await client.start_job("job-id", "worker-id")
        assert res["status"] == "RUNNING"
        
        # Test ALREADY_COMPLETED (Complete Job) -> Treated as Success
        mock_request.return_value = mock_resp_complete
        mock_request.side_effect = httpx.HTTPStatusError("Conflict", request=MagicMock(), response=mock_resp_complete)
        res = await client.complete_job("job-id", "worker-id", {})
        assert res["status"] == "COMPLETED"

        # Test WORKER_MISMATCH -> Raises HTTPStatusError (Error not bypassed!)
        mock_request.return_value = mock_resp_mismatch
        mock_request.side_effect = httpx.HTTPStatusError("Conflict", request=MagicMock(), response=mock_resp_mismatch)
        with pytest.raises(httpx.HTTPStatusError):
            await client.complete_job("job-id", "worker-id", {})

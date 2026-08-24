import asyncio
import socket
import signal
import logging
import time
from typing import Set, Optional, Any
from worker.config import settings
from worker.client import BackendClient
from worker.tasks import TASK_REGISTRY
from worker.metrics import (
    start_worker_prometheus_server, WORKER_JOBS_CLAIMED_TOTAL, WORKER_JOBS_STARTED_TOTAL,
    WORKER_JOBS_COMPLETED_TOTAL, WORKER_JOBS_FAILED_TOTAL, WORKER_JOBS_EXECUTION_DURATION_SECONDS,
    WORKER_ACTIVE_JOBS, WORKER_CONCURRENCY_LIMIT, WORKER_CAPACITY_RATIO, WORKER_HEARTBEAT_TOTAL,
    WORKER_POLL_REQUESTS_TOTAL, WORKER_POLL_EMPTY_TOTAL, WORKER_SHUTDOWNS_TOTAL
)

logger = logging.getLogger("worker")

class WorkerProcess:
    def __init__(self, app: Optional[Any] = None):
        self.worker_id: Optional[str] = None
        self.hostname = socket.gethostname()
        try:
            self.ip_address = socket.gethostbyname(self.hostname)
        except Exception:
            self.ip_address = "127.0.0.1"
            
        self.client = BackendClient(app=app)

        self.semaphore = asyncio.Semaphore(settings.WORKER_CONCURRENCY)
        self.shutting_down = False
        self.active_tasks: Set[asyncio.Task] = set()
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.polling_task: Optional[asyncio.Task] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        WORKER_CONCURRENCY_LIMIT.set(settings.WORKER_CONCURRENCY)
        
    def get_active_count(self) -> int:
        count = len(self.active_tasks)
        WORKER_ACTIVE_JOBS.set(count)
        if settings.WORKER_CONCURRENCY > 0:
            WORKER_CAPACITY_RATIO.set(round(count / settings.WORKER_CONCURRENCY, 4))
        return count

    def get_available_capacity(self) -> int:
        return max(0, settings.WORKER_CONCURRENCY - self.get_active_count())

    async def heartbeat_loop(self):
        logger.info("Heartbeat loop started.")
        while not self.shutting_down:
            try:
                if self.worker_id:
                    status_details = {
                        "status": "DRAINING" if self.shutting_down else "ACTIVE",
                        "active_jobs": self.get_active_count(),
                        "max_concurrency": settings.WORKER_CONCURRENCY,
                        "available_capacity": self.get_available_capacity()
                    }
                    await self.client.send_heartbeat(self.worker_id, status_details)
                    WORKER_HEARTBEAT_TOTAL.inc()
                    logger.debug(f"Heartbeat sent: {status_details}")
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {str(e)}")

            
            try:
                await asyncio.sleep(settings.HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                break

    async def execute_job(self, job: dict):
        if not self.worker_id:
            logger.error("Worker not registered; cannot execute job")
            return
        worker_id = self.worker_id
        
        job_id = job["id"]
        task_type = job["task_type"]
        payload = job.get("payload", {})
        attempt = job.get("attempt", 0)
        
        extra = {"worker_id": worker_id, "job_id": job_id, "task_type": task_type}
        logger.info(f"Starting execution of job {job_id}", extra=extra)
        
        # 1. Transition to start
        try:
            start_resp = await self.client.start_job(job_id, worker_id)
            attempt = start_resp.get("attempt", attempt)
            WORKER_JOBS_STARTED_TOTAL.inc()
        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {str(e)}", extra=extra)
            return

        # 2. Get handler
        handler = TASK_REGISTRY.get(task_type)
        if not handler:
            error_msg = f"Unknown task type: {task_type}"
            logger.error(error_msg, extra=extra)
            WORKER_JOBS_FAILED_TOTAL.inc()
            try:
                await self.client.fail_job(job_id, worker_id, error_msg)
            except Exception as fe:
                logger.error(f"Failed to report failure for unknown task type job {job_id}: {str(fe)}", extra=extra)
            return

        # 3. Execute handler
        start_time = time.time()
        try:
            result = await handler(payload, attempt)
            duration_ms = int((time.time() - start_time) * 1000)
            duration_sec = (time.time() - start_time)
            WORKER_JOBS_COMPLETED_TOTAL.inc()
            WORKER_JOBS_EXECUTION_DURATION_SECONDS.observe(duration_sec)
            
            # 4. Success -> transition to complete
            logger.info(f"Job {job_id} executed successfully. Duration: {duration_ms}ms", extra=extra)
            await self.client.complete_job(job_id, worker_id, {"result": result, "duration_ms": duration_ms})
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            duration_sec = (time.time() - start_time)
            WORKER_JOBS_FAILED_TOTAL.inc()
            WORKER_JOBS_EXECUTION_DURATION_SECONDS.observe(duration_sec)
            error_msg = f"Task raised exception: {str(exc)}"
            logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True, extra=extra)
            # 5. Exception -> transition to fail
            try:
                await self.client.fail_job(job_id, worker_id, error_msg)
            except Exception as fe:
                logger.error(f"Failed to report failure for job {job_id}: {str(fe)}", extra=extra)

    async def polling_loop(self):
        logger.info("Polling loop started.")
        while not self.shutting_down:
            try:
                await self.semaphore.acquire()
            except asyncio.CancelledError:
                break
            
            if self.shutting_down:
                self.semaphore.release()
                break

            job = None
            try:
                WORKER_POLL_REQUESTS_TOTAL.inc()
                job = await self.client.poll_job(self.worker_id)
            except Exception as e:
                logger.error(f"Failed to poll backend: {str(e)}")
                self.semaphore.release()
                try:
                    await asyncio.sleep(settings.POLL_INTERVAL)
                except asyncio.CancelledError:
                    break
                continue

            if not job:
                WORKER_POLL_EMPTY_TOTAL.inc()
                self.semaphore.release()
                try:
                    await asyncio.sleep(settings.POLL_INTERVAL)
                except asyncio.CancelledError:
                    break
                continue

            WORKER_JOBS_CLAIMED_TOTAL.inc()

            # Spawn job execution task in background with proper cleanup
            async def run_with_cleanup(j=job):
                t = asyncio.current_task()
                if t:
                    self.active_tasks.add(t)
                    self.get_active_count()
                try:
                    await self.execute_job(j)
                finally:
                    if t:
                        self.active_tasks.discard(t)
                        self.get_active_count()
                    self.semaphore.release()

            asyncio.create_task(run_with_cleanup())

    async def run(self):
        self.loop = asyncio.get_running_loop()
        
        # Start Prometheus metrics server
        start_worker_prometheus_server()
        
        # 1. Register worker
        try:
            reg_data = await self.client.register_worker(self.hostname, self.ip_address)
            self.worker_id = reg_data["id"]
            logger.info(f"Worker registered successfully with ID: {self.worker_id}")
        except Exception as e:
            logger.critical(f"Failed to register worker with backend: {str(e)}. Terminating.")
            await self.client.close()
            return
        
        # Setup signal handlers
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown_handler(s)))
            except NotImplementedError:
                pass

        # 2. Start heartbeat loop
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        
        # 3. Start polling loop
        self.polling_task = asyncio.create_task(self.polling_loop())
        try:
            await self.polling_task
        except asyncio.CancelledError:
            pass

    async def shutdown_handler(self, sig):
        logger.info(f"Signal {sig.name} received. Starting graceful shutdown...")
        await self.shutdown()

    async def shutdown(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        WORKER_SHUTDOWNS_TOTAL.inc()
        logger.info("Stopping polling loop and draining active tasks...")

        
        # Cancel polling task to interrupt any active semaphore acquire or sleep
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        # Wait for currently executing tasks to complete up to settings.SHUTDOWN_TIMEOUT
        if self.active_tasks:
            logger.info(f"Waiting for {len(self.active_tasks)} active tasks to finish (Timeout: {settings.SHUTDOWN_TIMEOUT}s)...")
            start_time = time.time()
            while self.active_tasks and (time.time() - start_time) < settings.SHUTDOWN_TIMEOUT:
                await asyncio.sleep(0.2)
            
            if self.active_tasks:
                logger.warning(
                    f"{len(self.active_tasks)} tasks still active after shutdown timeout. "
                    "Exiting worker without forced state transitions (backend lease will recover them)."
                )
                for t in self.active_tasks:
                    logger.warning(f"Active task left running: {t}")
            else:
                logger.info("All active tasks finished execution.")

        # Cancel heartbeat loop task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close backend client
        await self.client.close()
        logger.info("Graceful worker shutdown completed.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    wp = WorkerProcess()
    asyncio.run(wp.run())

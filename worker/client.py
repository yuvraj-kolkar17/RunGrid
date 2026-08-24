import httpx
import asyncio
import logging
from typing import Any, Optional
from worker.config import settings

logger = logging.getLogger("worker.client")

class BackendClient:
    def __init__(self, app: Optional[Any] = None):
        self.base_url = settings.BACKEND_URL.rstrip("/")
        self.headers = {
            "X-Internal-Key": settings.INTERNAL_API_KEY,
            "Content-Type": "application/json"
        }
        self.app = app
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            kwargs: dict[str, Any] = {
                "base_url": self.base_url,
                "headers": self.headers,
                "timeout": httpx.Timeout(10.0, connect=5.0)
            }
            if self.app is not None:
                kwargs["transport"] = httpx.ASGITransport(app=self.app)
            self._client = httpx.AsyncClient(**kwargs)
        return self._client



    async def close(self):
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _request_with_retry(
        self, method: str, path: str, json_data: Any = None, max_retries: int = 3, retry_delay: float = 1.0, is_idempotent: bool = True
    ) -> httpx.Response:
        client = await self.get_client()
        attempt = 0
        while True:
            try:
                resp = await client.request(method, path, json=json_data)
                resp.raise_for_status()
                return resp
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError) as e:
                attempt += 1
                if attempt >= max_retries or not is_idempotent:
                    logger.error(f"HTTP connection failure: {method} {path} - {str(e)}")
                    raise
                delay = retry_delay * (2 ** (attempt - 1))
                logger.warning(f"Connection failure ({str(e)}). Retrying {path} in {delay}s...")
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                # Do not retry HTTP Status errors (like 400, 404, 422, etc.)
                raise

    async def register_worker(self, hostname: str, ip_address: str) -> dict:
        resp = await self._request_with_retry(
            "POST", "/api/v1/internal/workers/register",
            json_data={"hostname": hostname, "ip_address": ip_address},
            is_idempotent=True
        )
        return resp.json()

    async def send_heartbeat(self, worker_id: str, status_details: dict) -> None:
        await self._request_with_retry(
            "POST", f"/api/v1/internal/workers/{worker_id}/heartbeat",
            json_data=status_details,
            is_idempotent=True
        )

    async def poll_job(self, worker_id: str) -> Optional[dict]:
        resp = await self._request_with_retry(
            "POST", f"/api/v1/internal/workers/{worker_id}/poll",
            is_idempotent=True
        )
        return resp.json()

    async def start_job(self, job_id: str, worker_id: str) -> dict:
        try:
            resp = await self._request_with_retry(
                "POST", f"/api/v1/internal/jobs/{job_id}/start",
                json_data={"worker_id": worker_id},
                is_idempotent=True
            )
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                try:
                    err_json = e.response.json()
                    code = err_json.get("error", {}).get("code")
                    if code == "ALREADY_STARTED":
                        logger.warning(f"Job {job_id} already marked ALREADY_STARTED. Treating as idempotent success.")
                        # Fetch job detail or return mock response with success
                        return {"id": job_id, "status": "RUNNING"}
                except Exception:
                    pass
            raise

    async def complete_job(self, job_id: str, worker_id: str, result: dict) -> dict:
        try:
            resp = await self._request_with_retry(
                "POST", f"/api/v1/internal/jobs/{job_id}/complete",
                json_data={"worker_id": worker_id, "result": result},
                is_idempotent=True
            )
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                try:
                    err_json = e.response.json()
                    code = err_json.get("error", {}).get("code")
                    if code == "ALREADY_COMPLETED":
                        logger.warning(f"Job {job_id} already marked ALREADY_COMPLETED. Treating as idempotent success.")
                        return {"id": job_id, "status": "COMPLETED"}
                except Exception:
                    pass
            raise

    async def fail_job(self, job_id: str, worker_id: str, error_message: str) -> dict:
        try:
            resp = await self._request_with_retry(
                "POST", f"/api/v1/internal/jobs/{job_id}/fail",
                json_data={"worker_id": worker_id, "error_message": error_message},
                is_idempotent=True
            )
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                try:
                    err_json = e.response.json()
                    code = err_json.get("error", {}).get("code")
                    if code == "ALREADY_FAILED":
                        logger.warning(f"Job {job_id} already marked ALREADY_FAILED. Treating as idempotent success.")
                        return {"id": job_id, "status": "FAILED"}
                except Exception:
                    pass
            raise

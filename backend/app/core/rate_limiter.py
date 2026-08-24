import time
from threading import Lock
from typing import Dict, Any, List
from fastapi import HTTPException, status

class InMemoryRateLimiter:
    """Thread-safe sliding window rate limiter for process-local environment."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[str, list[float]] = {}
        self.allowed_count: int = 0
        self.rejection_count: int = 0

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int = 60) -> None:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._requests.get(key, [])
            # Filter timestamps outside window
            valid_timestamps = [t for t in timestamps if t > cutoff]

            safe_endpoint = "POST /api/v1/jobs/batch" if "batch" in key else "POST /api/v1/jobs"

            if len(valid_timestamps) >= max_requests:
                self.rejection_count += 1
                from backend.app.core.prometheus_metrics import RATE_LIMIT_REJECTED_TOTAL
                RATE_LIMIT_REJECTED_TOTAL.labels(endpoint=safe_endpoint).inc()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded ({max_requests} requests per {window_seconds}s). Please try again later."
                    }
                )

            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps
            self.allowed_count += 1
            from backend.app.core.prometheus_metrics import RATE_LIMIT_ALLOWED_TOTAL
            RATE_LIMIT_ALLOWED_TOTAL.inc()


    def get_status(self) -> Dict[str, Any]:
        now = time.time()
        window_seconds = 60
        cutoff = now - window_seconds

        with self._lock:
            current_active_requests = 0
            active_keys_count = 0
            for k, ts_list in self._requests.items():
                valid = [t for t in ts_list if t > cutoff]
                if valid:
                    current_active_requests += len(valid)
                    active_keys_count += 1

            return {
                "architecture": "Process-local sliding window rate limiting (InMemoryRateLimiter)",
                "total_allowed": self.allowed_count,
                "total_rejected": self.rejection_count,
                "active_window_seconds": window_seconds,
                "current_active_requests": current_active_requests,
                "active_tracked_keys": active_keys_count,
                "protected_endpoints": [
                    {
                        "endpoint": "POST /api/v1/jobs",
                        "description": "Single job submission API",
                        "limit": 100,
                        "window_seconds": 60,
                        "key_format": "user:{user_id}:job"
                    },
                    {
                        "endpoint": "POST /api/v1/jobs/batch",
                        "description": "Atomic multi-job batch submission API",
                        "limit": 20,
                        "window_seconds": 60,
                        "key_format": "user:{user_id}:batch"
                    }
                ]
            }

limiter = InMemoryRateLimiter()

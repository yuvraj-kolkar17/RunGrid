import os

class Settings:
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "internal-worker-secret-key")
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "2"))
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "1.0"))
    HEARTBEAT_INTERVAL: float = float(os.getenv("HEARTBEAT_INTERVAL", "5.0"))
    SHUTDOWN_TIMEOUT: float = float(os.getenv("SHUTDOWN_TIMEOUT", "10.0"))

settings = Settings()

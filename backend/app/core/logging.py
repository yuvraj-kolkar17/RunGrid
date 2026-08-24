import logging
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict

# Sensitive fields to sanitize
SENSITIVE_KEYS = {
    "password", "password_hash", "access_token", "jwt", "token",
    "secret", "api_key", "internal_api_key", "authorization", "cookie"
}

def sanitize_data(data: Any) -> Any:
    """Recursively redacts sensitive fields in dictionaries or log data."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k.lower() in SENSITIVE_KEYS:
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_data(v)
        return cleaned
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data

class StructuredJsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs logs as structured JSON strings."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Include request_id if present
        if hasattr(record, "request_id"):
            log_obj["request_id"] = getattr(record, "request_id")
            
        # Include structured event payload if attached
        if hasattr(record, "event_data") and isinstance(record.event_data, dict):
            log_obj.update(sanitize_data(record.event_data))
            
        return json.dumps(log_obj)

def get_structured_logger(name: str = "scheduler_engine") -> logging.Logger:
    """Returns a logger pre-configured with structured output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

structured_logger = get_structured_logger()

def log_event(event_name: str, component: str = "backend", **kwargs: Any) -> None:
    """Logs a structured domain event with sanitized fields."""
    event_data = {
        "event": event_name,
        "component": component,
        **sanitize_data(kwargs)
    }
    extra = {"event_data": event_data}
    structured_logger.info(f"[{component.upper()}] {event_name}", extra=extra)

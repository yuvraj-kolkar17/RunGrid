from typing import Any

class FailureSummaryService:
    """Service to generate deterministic failure analysis and recommendations for failed jobs."""

    @staticmethod
    def generate_summary(
        task_type: str,
        error_message: str | None,
        attempt: int = 0,
        max_retries: int = 3,
        logs: list[Any] | None = None
    ) -> dict[str, str]:
        err_text = (error_message or "").lower()
        log_text = " ".join([getattr(l, "message", str(l)).lower() for l in (logs or [])])
        combined = f"{err_text} {log_text}"

        res = {
            "summary": f"Job execution failed on attempt {attempt}.",
            "likely_cause": error_message or "An unexpected runtime exception was raised during execution.",
            "recommended_action": "Check detailed job execution logs for step-by-step diagnostic trace."
        }
        if any(k in combined for k in ["timeout", "connection refused", "connect error", "unreachable", "timed out"]):
            res = {
                "summary": "External service connection timed out or was refused.",
                "likely_cause": "The worker was unable to establish a connection with an external API, database, or network endpoint.",
                "recommended_action": "Verify target endpoint health, network security groups, and API rate limits."
            }
        elif any(k in combined for k in ["not registered", "unknown task", "unhandled task", "invalid task_type"]):
            res = {
                "summary": f"Worker task type '{task_type}' is unregistered.",
                "likely_cause": "The task_type submitted is not registered in the worker's TASK_REGISTRY.",
                "recommended_action": "Add the task handler function to TASK_REGISTRY in worker/app/tasks.py."
            }
        elif any(k in combined for k in ["valueerror", "typeerror", "keyerror", "zerodivisionerror", "jsondecodeerror"]):
            res = {
                "summary": "Runtime code or payload schema error encountered.",
                "likely_cause": "The task payload contained unexpected data types, missing required keys, or invalid parameters.",
                "recommended_action": "Inspect job payload parameters and ensure compatibility with task execution logic."
            }
        elif any(k in combined for k in ["memoryerror", "out of memory", "oom", "resource limit"]):
            res = {
                "summary": "Worker node resource limit exceeded.",
                "likely_cause": "The job required more RAM or memory resources than allocated to the worker thread.",
                "recommended_action": "Scale worker container memory limits or optimize heavy payload data processing."
            }
        elif attempt >= max_retries:
            res = {
                "summary": f"Job failed across all {attempt} execution attempt(s).",
                "likely_cause": "Repeated non-transient failures prevented task completion prior to reaching max retries.",
                "recommended_action": "Inspect full execution log history and verify dependencies before re-submitting."
            }

        try:
            from backend.app.core.prometheus_metrics import FAILURE_ANALYSES_GENERATED_TOTAL
            FAILURE_ANALYSES_GENERATED_TOTAL.inc()
        except Exception:
            pass

        return res


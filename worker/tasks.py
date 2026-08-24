import asyncio
import logging
from typing import Any

logger = logging.getLogger("worker.tasks")

async def demo_success(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running demo_success (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.1)
    return {"status": "success", "data": payload.get("data", "Hello World")}

async def demo_failure(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running demo_failure (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.1)
    raise RuntimeError(payload.get("error_message", "Task execution failed intentionally"))

async def demo_slow(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    duration = float(payload.get("duration", 5.0))
    logger.info(f"Running demo_slow (attempt: {attempt}) for {duration} seconds with payload: {payload}")
    await asyncio.sleep(duration)
    return {"status": "slow_success", "duration": duration}

async def demo_retry(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    fail_until_attempt = int(payload.get("fail_until_attempt", 2))
    logger.info(f"Running demo_retry (attempt: {attempt}, fail_until_attempt: {fail_until_attempt}) with payload: {payload}")
    await asyncio.sleep(0.1)
    if attempt < fail_until_attempt:
        raise RuntimeError(f"Transient failure (attempt {attempt} < {fail_until_attempt})")
    return {"status": "retry_success", "attempt": attempt}

async def email_send(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running email.send (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.2)
    sim_failure = payload.get("simulate_failure")
    if sim_failure == "transient" and attempt == 1:
        raise RuntimeError("SMTP Gateway connection timeout (simulated transient failure)")
    if sim_failure == "permanent" or payload.get("simulate_failure") is True:
        raise RuntimeError("Fatal: Recipient address rejected (550 User unknown)")
    
    recipient = payload.get("recipient", "user@example.com")
    template = payload.get("template", "welcome")
    return {
        "status": "simulated",
        "operation": "email.send",
        "message": f"Welcome email processed successfully for {recipient}",
        "recipient": recipient,
        "template": template
    }

async def invoice_generate(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running invoice.generate (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.3)
    invoice_id = payload.get("invoice_id", "INV-1001")
    amount = payload.get("amount", 249.99)
    return {
        "status": "simulated",
        "operation": "invoice.generate",
        "message": f"Invoice {invoice_id} PDF compiled successfully",
        "invoice_id": invoice_id,
        "amount": amount
    }

async def report_generate(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running report.generate (attempt: {attempt}) with payload: {payload}")
    sim_failure = payload.get("simulate_failure")
    if sim_failure == "transient" and attempt == 1:
        await asyncio.sleep(0.1)
        raise RuntimeError("Database lock contention during aggregation (simulated transient failure)")
    
    duration = float(payload.get("duration", 0.3))
    if duration > 0:
        await asyncio.sleep(duration)
        
    report_name = payload.get("report", "daily_sales")
    return {
        "status": "simulated",
        "operation": "report.generate",
        "message": f"Report '{report_name}' compiled successfully",
        "report": report_name,
        "rows_processed": 4520
    }

async def image_process(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running image.process (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.4)
    operation = payload.get("operation", "resize")
    count = payload.get("image_count", 24)
    return {
        "status": "simulated",
        "operation": "image.process",
        "message": f"Processed {count} product images ({operation})",
        "images_processed": count,
        "target_size": payload.get("target_size", "1200x1200")
    }

async def notification_send(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running notification.send (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.15)
    customer_id = payload.get("customer_id", "CUS-1001")
    channel = payload.get("channel", "email")
    return {
        "status": "simulated",
        "operation": "notification.send",
        "message": f"Notification dispatched to customer {customer_id} via {channel}",
        "customer_id": customer_id,
        "channel": channel
    }

async def customer_sync(payload: dict[str, Any], attempt: int) -> dict[str, Any]:
    logger.info(f"Running customer.sync (attempt: {attempt}) with payload: {payload}")
    await asyncio.sleep(0.2)
    sim_failure = payload.get("simulate_failure")
    if sim_failure == "permanent" or payload.get("simulate_failure") is True:
        raise RuntimeError("Fatal: Customer record INVALID-DEMO-CUSTOMER not found in CRM")
    if sim_failure == "transient" and attempt == 1:
        raise RuntimeError("CRM API endpoint rate limit reached (simulated transient error)")
        
    customer_id = payload.get("customer_id", "CUS-1001")
    return {
        "status": "simulated",
        "operation": "customer.sync",
        "message": f"Customer profile {customer_id} synchronized",
        "customer_id": customer_id,
        "synced_fields": ["email", "address", "tier"]
    }

TASK_REGISTRY = {
    "demo.success": demo_success,
    "demo.failure": demo_failure,
    "demo.slow": demo_slow,
    "demo.retry": demo_retry,
    "email.send": email_send,
    "invoice.generate": invoice_generate,
    "report.generate": report_generate,
    "image.process": image_process,
    "notification.send": notification_send,
    "customer.sync": customer_sync,
}

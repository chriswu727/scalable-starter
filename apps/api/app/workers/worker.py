"""Background worker (consumer side) — at-least-once processing.

Runs as its own Deployment so long/bursty work never blocks request handling and
can scale independently. ``BLMOVE`` moves each job to a per-worker *processing*
list before it runs, so a crash or SIGKILL can't lose it: on restart the worker
requeues its own processing list, and a job is acked (``LREM``) only after its
handler succeeds. Failures retry up to ``MAX_ATTEMPTS``, then go to the
dead-letter list (``jobs:dead``).

Handlers MUST be idempotent — a job can run more than once (e.g. if the process
dies after the handler succeeds but before the ack). Run with
``python -m app.workers.worker`` (or the ``worker`` console script).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
from collections.abc import Awaitable, Callable
from typing import Any, cast

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.workers.queue import DEAD_KEY, MAX_ATTEMPTS, PROCESSING_KEY_PREFIX, QUEUE_KEY

log = get_logger("worker")

JobHandler = Callable[[dict[str, Any]], Awaitable[None]]

# Map job types to async handlers. Register real handlers as you add them.
HANDLERS: dict[str, JobHandler] = {}


def handler(job_type: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator to register a job handler: ``@handler("send_email")``."""

    def register(fn: JobHandler) -> JobHandler:
        HANDLERS[job_type] = fn
        return fn

    return register


@handler("noop")
async def _noop(payload: dict[str, Any]) -> None:
    """Example handler. Delete it once you have real jobs."""
    log.info("job.noop", payload=payload)


def processing_key() -> str:
    """Per-worker processing list, so a worker recovers only its own in-flight jobs."""
    return f"{PROCESSING_KEY_PREFIX}:{os.getenv('HOSTNAME', 'local')}"


async def recover_orphans(client: aioredis.Redis, pkey: str) -> int:
    """Requeue jobs left in this worker's processing list by a previous crash."""
    count = 0
    while await client.lmove(pkey, QUEUE_KEY, src="LEFT", dest="RIGHT") is not None:
        count += 1
    if count:
        log.warning("worker.recovered_orphans", count=count)
    return count


async def handle_job(client: aioredis.Redis, pkey: str, raw: str) -> None:
    """Process one job already moved to the processing list: ack, retry, or dead-letter."""
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        log.exception("job.unparseable", raw=raw)
        await client.lrem(pkey, 1, raw)  # drop poison message
        return

    handler_fn = HANDLERS.get(job.get("type"))
    if handler_fn is None:
        log.warning("job.unknown_type", type=job.get("type"), id=job.get("id"))
        await client.lrem(pkey, 1, raw)
        return

    try:
        await handler_fn(job.get("payload", {}))
    except Exception:
        attempts = int(job.get("attempts", 0)) + 1
        job["attempts"] = attempts
        await client.lrem(pkey, 1, raw)
        if attempts >= MAX_ATTEMPTS:
            await client.rpush(DEAD_KEY, json.dumps(job))
            log.exception("job.dead_lettered", id=job.get("id"), attempts=attempts)
        else:
            await client.rpush(QUEUE_KEY, json.dumps(job))
            log.warning("job.retrying", id=job.get("id"), attempts=attempts)
        return

    await client.lrem(pkey, 1, raw)  # ack only after the handler succeeds
    log.info("job.done", id=job.get("id"), type=job.get("type"))


async def process_next(client: aioredis.Redis, pkey: str, *, block_seconds: int = 5) -> bool:
    """Block up to ``block_seconds`` for a job, move it to processing, and handle it."""
    raw = cast("str | None", await client.blmove(QUEUE_KEY, pkey, timeout=block_seconds))
    if raw is None:
        return False
    await handle_job(client, pkey, raw)
    return True


async def _run() -> None:
    configure_logging()
    client = aioredis.from_url(
        str(settings.redis_url), decode_responses=True, health_check_interval=30
    )
    pkey = processing_key()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    log.info("worker.started", queue=QUEUE_KEY, processing=pkey, handlers=sorted(HANDLERS))
    backoff = 1
    try:
        await recover_orphans(client, pkey)
        while not stop.is_set():
            try:
                await process_next(client, pkey, block_seconds=5)
                backoff = 1
            except (RedisConnectionError, RedisTimeoutError):
                # Don't let a transient Redis blip kill the loop; back off and retry.
                log.warning("worker.redis_unavailable", retry_in_seconds=backoff)
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=backoff)
                backoff = min(backoff * 2, 30)
    finally:
        await client.aclose()
        log.info("worker.stopped")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

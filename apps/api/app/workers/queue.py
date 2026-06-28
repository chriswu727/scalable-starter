"""Job queue over Redis (producer side + shared constants).

The worker consumes these with at-least-once delivery (see ``worker.py``). This
is the *seam*, intentionally tiny: swap it for Celery / Arq / Dramatiq or a
managed queue when you outgrow it, keeping the ``enqueue`` call-site contract.
The producer reuses one pooled client instead of connecting per call.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

QUEUE_KEY = "jobs:default"
PROCESSING_KEY_PREFIX = "jobs:processing"
DEAD_KEY = "jobs:dead"
MAX_ATTEMPTS = 5

_client: aioredis.Redis | None = None


def get_client() -> aioredis.Redis:
    """Lazily-created, pooled Redis client reused across enqueue calls."""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            str(settings.redis_url),
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def aclose() -> None:
    """Close the producer client (call on app shutdown; safe if never opened)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def enqueue(job_type: str, payload: dict[str, Any]) -> str:
    """Push a job onto the queue and return its id. Call this from a service."""
    job = {"id": uuid.uuid4().hex, "type": job_type, "payload": payload, "attempts": 0}
    await get_client().rpush(QUEUE_KEY, json.dumps(job))
    return str(job["id"])

"""Worker reliability: at-least-once delivery, retries, dead-lettering, recovery.

Exercised against a fake Redis so the BLMOVE/ack/retry logic is covered in CI.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest

from app.workers import queue, worker

PKEY = "jobs:processing:test"


@pytest.fixture
async def client() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    c = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield c
    await c.aclose()


@pytest.fixture(autouse=True)
def _restore_handlers() -> AsyncIterator[None]:
    original = dict(worker.HANDLERS)
    yield
    worker.HANDLERS.clear()
    worker.HANDLERS.update(original)


async def test_successful_job_is_acked(client: fakeredis.aioredis.FakeRedis) -> None:
    seen: list[dict[str, object]] = []

    @worker.handler("t_ok")
    async def _h(payload: dict[str, object]) -> None:
        seen.append(payload)

    await client.rpush(
        queue.QUEUE_KEY, json.dumps({"id": "j", "type": "t_ok", "payload": {"x": 1}})
    )
    assert await worker.process_next(client, PKEY, block_seconds=1) is True
    assert seen == [{"x": 1}]
    assert await client.llen(PKEY) == 0  # acked out of the processing list
    assert await client.llen(queue.QUEUE_KEY) == 0


async def test_failing_job_requeues_with_incremented_attempts(
    client: fakeredis.aioredis.FakeRedis,
) -> None:
    @worker.handler("t_fail")
    async def _h(payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    await client.rpush(
        queue.QUEUE_KEY, json.dumps({"id": "j", "type": "t_fail", "payload": {}, "attempts": 0})
    )
    await worker.process_next(client, PKEY, block_seconds=1)

    assert await client.llen(PKEY) == 0
    assert await client.llen(queue.DEAD_KEY) == 0
    requeued = json.loads(await client.lindex(queue.QUEUE_KEY, 0))
    assert requeued["attempts"] == 1


async def test_job_dead_letters_after_max_attempts(
    client: fakeredis.aioredis.FakeRedis,
) -> None:
    @worker.handler("t_fail")
    async def _h(payload: dict[str, object]) -> None:
        raise RuntimeError("boom")

    await client.rpush(
        queue.QUEUE_KEY,
        json.dumps(
            {"id": "j", "type": "t_fail", "payload": {}, "attempts": queue.MAX_ATTEMPTS - 1}
        ),
    )
    await worker.process_next(client, PKEY, block_seconds=1)

    assert await client.llen(queue.QUEUE_KEY) == 0  # not requeued
    dead = json.loads(await client.lindex(queue.DEAD_KEY, 0))
    assert dead["attempts"] == queue.MAX_ATTEMPTS


async def test_unknown_type_is_dropped(client: fakeredis.aioredis.FakeRedis) -> None:
    await client.rpush(queue.QUEUE_KEY, json.dumps({"id": "j", "type": "nope", "payload": {}}))
    await worker.process_next(client, PKEY, block_seconds=1)
    assert await client.llen(PKEY) == 0
    assert await client.llen(queue.DEAD_KEY) == 0


async def test_recover_orphans_requeues_in_flight_jobs(
    client: fakeredis.aioredis.FakeRedis,
) -> None:
    await client.rpush(PKEY, json.dumps({"id": "orphan", "type": "noop", "payload": {}}))
    assert await worker.recover_orphans(client, PKEY) == 1
    assert await client.llen(PKEY) == 0
    assert await client.llen(queue.QUEUE_KEY) == 1


async def test_enqueue_uses_pooled_client(
    client: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(queue, "_client", client)
    job_id = await queue.enqueue("noop", {"hello": "world"})
    assert job_id
    stored = json.loads(await client.lindex(queue.QUEUE_KEY, 0))
    assert stored["type"] == "noop"
    assert stored["id"] == job_id

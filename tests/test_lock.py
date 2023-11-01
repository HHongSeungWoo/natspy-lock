import asyncio

import nats
import pytest

from natspy_lock import NatsLock


@pytest.fixture(scope="session")
def event_loop():
    return asyncio.get_event_loop()


@pytest.fixture(scope="session")
async def nats_client():
    nc = None
    try:
        nc = await nats.connect("nats://127.0.0.1:4222")
        yield nc
    finally:
        if nc:
            await nc.drain()


@pytest.fixture(scope="session", autouse=True)
async def init_nats_lock(nats_client: nats.NATS):
    await NatsLock.init(nats_client.jetstream(), "test_lock", 100)


async def should_be_locked():
    async with NatsLock.lock("test_lock", 1) as lock:
        assert lock
        await asyncio.sleep(0.5)


async def test_nats_lock():
    await asyncio.gather(should_be_locked(), should_be_locked())

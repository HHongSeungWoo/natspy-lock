import asyncio
import multiprocessing

import nats

from natspy_lock import NatsLock

shared_variable = multiprocessing.Value("i", 0)


async def should_be_locked():
    nc = await nats.connect("nats://127.0.0.1:4222")
    kv = await nc.jetstream().key_value("test_lock")
    lock = NatsLock(kv)

    for _ in range(300):
        async with lock.get_lock("test_lock11111", 1):
            shared_variable.value += 1
    await nc.drain()


def run_async():
    asyncio.run(should_be_locked())


async def test_nats_lock():
    p1 = multiprocessing.Process(target=run_async)
    p2 = multiprocessing.Process(target=run_async)
    p3 = multiprocessing.Process(target=run_async)
    p4 = multiprocessing.Process(target=run_async)
    p1.start()
    p2.start()
    p3.start()
    p4.start()

    p1.join()
    p2.join()
    p3.join()
    p4.join()

    assert shared_variable.value == 1200, "Lock is not working"

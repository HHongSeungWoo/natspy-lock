import asyncio
import multiprocessing

import nats

from natspy_lock import NatsLock

shared_variable = multiprocessing.Value("i", 0)


async def should_be_locked():
    nc = await nats.connect("nats://127.0.0.1:4222")
    kv = await nc.jetstream().key_value("test_lock")
    lock = NatsLock(kv)

    await asyncio.sleep(4)

    for _ in range(1000):
        async with lock.lock("test_lock1111", 1) as asd:
            print(asd)  # noqa: T201
            shared_variable.value += 1
    await nc.drain()


def run_async():
    asyncio.run(should_be_locked())


async def test_nats_lock():
    p1 = multiprocessing.Process(target=run_async)
    p2 = multiprocessing.Process(target=run_async)
    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("Final value of shared_variable:", shared_variable.value)  # noqa: T201

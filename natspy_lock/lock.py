import asyncio
import time
import warnings

from nats.js.errors import KeyWrongLastSequenceError
from nats.js.kv import KeyValue


class NoOpClass:
    @staticmethod
    def set_result(*args, **kwargs):
        pass


async def watch_lock(kv: KeyValue, key_dict: dict[str, asyncio.Future]):
    # info = await kv.status()
    w = await kv.watchall()
    while True:
        try:
            entry = await w.updates(30)
        except asyncio.TimeoutError:
            continue

        if entry:
            if entry.operation is None:
                _ = key_dict.setdefault(entry.key, asyncio.Future())
            elif entry.operation == "PURGE":
                key_dict.pop(entry.key, NoOpClass).set_result(True)


async def acquire(kv: KeyValue, key_dict: dict[str, asyncio.Future], key: str, wait: float = 0):
    start = time.time()

    wait_future = key_dict.get(key, None)

    if wait_future is None:
        wait_future = key_dict.setdefault(key, asyncio.Future())

        try:
            await kv.create(key, b"")
            return True
        except KeyWrongLastSequenceError:
            pass
        except Exception as e:
            warnings.warn(f"Unexpected error occurred while acquiring lock: {e}", stacklevel=2)

    if wait > 0:
        try:
            await asyncio.wait_for(asyncio.shield(wait_future), wait)

            return await acquire(kv, key_dict, key, wait - (time.time() - start))
        except asyncio.TimeoutError:
            # noinspection PyAsyncCall
            key_dict.pop(key, None)
            return False
        except Exception:
            return False
    else:
        return False


async def release(kv: KeyValue, key: str):
    await kv.purge(key)


class _NatsLock:
    def __init__(self, kv: KeyValue, key_dict: dict[str, asyncio.Future], key: str, wait: float = 0):
        self.kv = kv
        self.key_dict = key_dict
        self.key = key
        self.wait = wait

        self._lock = False

    async def acquire(self):
        self._lock = await acquire(self.kv, self.key_dict, self.key, self.wait)

        return self._lock

    async def release(self):
        await release(self.kv, self.key)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            await self.release()

    async def __aenter__(self):
        return await self.acquire()


class NatsLock:
    def __init__(self, kv: KeyValue):
        self.kv = kv
        self.key_dict: dict[str, asyncio.Future] = {}

        self._watch_task = asyncio.create_task(watch_lock(self.kv, self.key_dict))

    def lock(self, key: str, wait: float = 0):
        return _NatsLock(self.kv, self.key_dict, key, wait)

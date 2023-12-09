import asyncio
import threading
import time
import warnings

import nats
from nats.js.api import KeyValueConfig
from nats.js.errors import KeyWrongLastSequenceError
from nats.js.kv import KeyValue


class NoOpClass:
    @staticmethod
    def set_result(*args, **kwargs):
        pass


class LockStorage(threading.local):
    def __init__(self):
        super().__init__()

        self._dict = {}

    def setdefault(self, key, data):
        return self._dict.setdefault(key, data)

    def get(self, key):
        return self._dict.get(key, None)

    def has_key(self, key):
        pass

    def remove_key(self, key):
        pass

    def pop(self, key):
        return self._dict.pop(key, NoOpClass)


storage = LockStorage()


async def watch_lock(nc: nats.NATS, kv: KeyValue):
    w = await kv.watchall()

    while not (nc.is_closed or nc.is_draining):
        try:
            entry = await w.updates(30)
        except asyncio.TimeoutError:
            continue

        if entry:
            if entry.operation is None:
                storage.setdefault(entry.key, asyncio.Future())
            elif entry.operation == "PURGE":
                storage.pop(entry.key).set_result(True)
            elif entry.operation == "DELETE":
                storage.pop(entry.key).set_result(True)


async def acquire(kv: KeyValue, key: str, wait: float = 0) -> bool:
    start = time.time()

    wait_future = storage.get(key)

    if wait_future:
        if wait > 0:
            try:
                await asyncio.wait_for(asyncio.shield(wait_future), wait)

                return await acquire(kv, key, wait - (time.time() - start))
            except asyncio.TimeoutError:
                return False
            except Exception:
                return False
        else:
            await wait_future

    try:
        await kv.create(key, b"")
        return True
    except KeyWrongLastSequenceError:
        await asyncio.sleep(0.1)
        return await acquire(kv, key, wait - (time.time() - start))
    except Exception as e:
        warnings.warn(f"Unexpected error occurred while acquiring lock: {e}", stacklevel=2)
        raise e


async def release(kv: KeyValue, key: str):
    await kv.purge(key)


class _NatsLock:
    def __init__(self, kv: KeyValue, key: str, wait: float = 0):
        self.kv = kv
        self.key = key
        self.wait = wait

        self._lock = False

    async def acquire(self):
        self._lock = await acquire(self.kv, self.key, self.wait)

        return self

    async def release(self):
        await release(self.kv, self.key)

    def locked(self):
        return self._lock

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.locked():
            await self.release()

    async def __aenter__(self):
        return await self.acquire()


class NatsLock:
    _kv: KeyValue | None = None
    _watch_task: asyncio.Task | None = None

    @classmethod
    async def init(cls, nc: nats.NATS, stream_name: str, max_ttl: int):
        if cls._kv:
            return

        cls._kv = await nc.jetstream().create_key_value(KeyValueConfig(stream_name, ttl=max_ttl))
        cls._watch_task = asyncio.create_task(watch_lock(nc, cls._kv))

    @classmethod
    def get_lock(cls, key: str, wait: float = 0):
        if cls._kv is None:
            msg = "Please call NatsLock.init() first."
            raise RuntimeError(msg)
        return _NatsLock(cls._kv, key, wait)

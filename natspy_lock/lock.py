import asyncio
import time
import warnings

from nats.js import JetStreamContext
from nats.js.api import KeyValueConfig
from nats.js.errors import KeyWrongLastSequenceError
from nats.js.kv import KeyValue

from natspy_lock.exceptions import ConfigMismatchError, InitialError

_lock_dict: dict[str, asyncio.Future] = {}


class NoOpClass:
    @staticmethod
    def set_result(*args, **kwargs):
        pass


async def watch_lock(kv: KeyValue):
    w = await kv.watchall()
    while True:
        try:
            entry = await w.updates(10000)
        except asyncio.TimeoutError:
            continue

        if entry:
            if entry.operation is None:
                _ = _lock_dict.setdefault(entry.key, asyncio.Future())
            elif entry.operation == "PURGE":
                _lock_dict.pop(entry.key, NoOpClass).set_result(True)


# 상태에 맞는 에러를 raise 시키는게 더 나은가??
async def acquire(kv: KeyValue, key: str, wait: float = 0):
    start = time.time()

    wait_future = _lock_dict.get(key, None)

    if wait_future is None:
        wait_future = _lock_dict.setdefault(key, asyncio.Future())

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

            return await acquire(kv, key, wait - (time.time() - start))
        except asyncio.TimeoutError:
            # noinspection PyAsyncCall
            _lock_dict.pop(key, None)
            return False
        except Exception:
            return False
    else:
        return False


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

        return self._lock

    async def release(self):
        await release(self.kv, self.key)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._lock:
            await self.release()

    async def __aenter__(self):
        return await self.acquire()


class NatsLock:
    _kv: KeyValue | None = None
    _watch_task: asyncio.Task | None = None

    @classmethod
    async def init(cls, js: JetStreamContext, stream_name: str, max_ttl: int):
        if cls._kv:
            return
        try:
            cls._kv = await js.key_value(stream_name)
        except Exception:
            cls._kv = await js.create_key_value(KeyValueConfig(stream_name, ttl=max_ttl))
        if (await cls._kv.status()).ttl != max_ttl:
            raise ConfigMismatchError
        cls._watch_task = asyncio.create_task(watch_lock(cls._kv))

    @classmethod
    def lock(cls, key: str, wait: float = 0):
        if not cls._kv:
            raise InitialError
        return _NatsLock(cls._kv, key, wait)

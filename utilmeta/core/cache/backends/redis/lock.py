from ...lock import BaseLocker
from redis.client import Redis
from typing import List
from utilmeta.utils import gen_key


class RedisLocker(BaseLocker):
    def __init__(self, con: Redis, *keys, **kwargs):
        super().__init__(*keys, **kwargs)
        from redis.lock import Lock

        self.con = con
        self.locks: List[Lock] = []

    def __enter__(self):
        import time

        start = time.time()
        for key in self.scope:
            lock = self.con.lock(
                name=self.key_func(key),
                blocking_timeout=self.blocking_timeout,
                timeout=self.timeout,
            )
            if lock.acquire(blocking=self.block, token=gen_key(32, alnum=True)):
                self.targets.append(key)
                self.locks.append(lock)
        end = time.time()
        if self.timeout:
            if (end - start) > self.timeout:
                raise TimeoutError(f"Locker acquire keys: {self.scope} timeout")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from redis.exceptions import LockError

        for lock in self.locks:
            try:
                lock.release()
            except LockError:
                continue

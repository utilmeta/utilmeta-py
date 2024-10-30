from .base import Config
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError, ALL_COMPLETED


class ThreadPool(Config):
    max_workers: Optional[int]
    timeout: Optional[int]

    def __init__(self, max_workers: Optional[int] = None, timeout: Optional[int] = None):
        super().__init__(locals())

        self._pool = ThreadPoolExecutor(self.max_workers)

    def get_result(self, func, *args, **kwargs):
        future = self._pool.submit(func, *args, **kwargs)
        return future.result()


# pool = ThreadPool()

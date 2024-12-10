from typing import Callable


class BaseLocker:
    def __init__(
        self,
        *keys,
        key_func: Callable[[str], str] = lambda x: x + "!",
        block: bool = False,
        timeout: int = None,
        blocking_timeout: int = None,
        sleep: int = 0.1
    ):
        self.key_func = key_func
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout
        self.sleep = sleep
        self.scope = keys
        self.targets = []
        self.block = block

    def __enter__(self) -> "BaseLocker":
        raise NotImplementedError

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError

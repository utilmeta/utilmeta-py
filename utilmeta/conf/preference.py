from .base import Config
from typing import Union, List, Dict, Type, Optional
from utilmeta.utils import ERROR_STATUS

DEFAULT_MAX_RETRY_LOOPS = 1000


class Preference(Config):
    max_retry_loops: int
    api_max_retry_loops: int
    client_max_retry_loops: int
    api_default_strict_response: Optional[bool]
    client_default_strict_response: Optional[bool]
    default_status: Optional[int]

    def __init__(
        self,
        max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        api_max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        client_max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        response_file_default_attachment: bool = False,
        response_json_encoder_cls=None,
        response_json_encoder_kwargs: dict = None,
        # allow_ana
        # ensure_ascii
        # sort_keys
        # skip_keys
        # expose_headers: Union[str, List[str]] = (),
        # default_status: int = 200,
        error_status: Dict[Type[Exception], int] = ERROR_STATUS,
        api_default_strict_response: Optional[bool] = None,
        client_default_strict_response: Optional[bool] = True,
        default_status: Optional[int] = 200,
    ):
        super().__init__(locals())

    @classmethod
    def get(cls) -> 'Preference':
        return cls.config() or cls()

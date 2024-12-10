from .base import Config
from typing import Dict, Type, Optional, Any
from utilmeta.utils import ERROR_STATUS

DEFAULT_MAX_RETRY_LOOPS = 1000


class Preference(Config):
    max_retry_loops: int
    api_max_retry_loops: int
    client_max_retry_loops: int
    api_default_strict_response: Optional[bool]
    # client_default_strict_response: Optional[bool]
    client_default_request_backend: Any

    default_response_status: Optional[int]
    default_aborted_response_status: int
    default_timeout_response_status: int

    orm_default_query_distinct: Optional[bool]
    orm_default_save_with_relations: bool
    # orm_default_filter_required: Optional[bool]
    # orm_default_field_fail_silently: bool

    strict_root_route: bool

    def __init__(
        self,
        strict_root_route: bool = False,
        max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        api_max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        client_max_retry_loops=DEFAULT_MAX_RETRY_LOOPS,
        # response_file_default_attachment: bool = False,
        # response_json_encoder_cls=None,
        # response_json_encoder_kwargs: dict = None,
        # allow_ana
        # ensure_ascii
        # sort_keys
        # skip_keys
        # expose_headers: Union[str, List[str]] = (),
        # default_status: int = 200,
        error_status: Dict[Type[Exception], int] = ERROR_STATUS,
        api_default_strict_response: Optional[bool] = None,
        # client_default_strict_response: Optional[bool] = True,
        client_default_request_backend=None,
        default_response_status: Optional[int] = 200,
        default_aborted_response_status: int = 503,
        default_timeout_response_status: int = 504,
        # ---------
        orm_default_save_with_relations: bool = True,
        orm_default_query_distinct: Optional[bool] = None,
        # orm_schema_integrity_error_cls: Optional[Type[Exception]] = None,
        # orm_default_filter_required: Optional[bool] = False,
        # orm_default_field_fail_silently: bool = False,
    ):
        super().__init__(locals())

    @classmethod
    def get(cls) -> 'Preference':
        return cls.config() or cls()

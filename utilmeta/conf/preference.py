from .base import Config
from typing import Dict, Type, Optional, Any, Literal
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
    default_response_streaming_chunk_size: Optional[int]
    default_aborted_response_status: int
    default_timeout_response_status: int
    default_dns_resolve_timeout: Optional[float]

    orm_default_query_distinct: Optional[bool]
    orm_default_save_with_relations: bool
    orm_default_gather_async_fields: bool

    orm_on_non_exists_required_field: Literal['error', 'warn', 'ignore'] = 'warn'
    # orm_on_non_exists_lookup_field: Literal['error', 'warn', 'ignore'] = 'error'
    orm_on_sliced_field_queryset: Literal['error', 'warn', 'ignore'] = 'warn'
    orm_on_conflict_annotation: Literal['error', 'warn', 'ignore'] = 'warn'
    orm_on_conflict_type: Literal['error', 'warn', 'ignore'] = 'warn'
    # ValueError: The annotation 'label' conflicts with a field on the model.

    orm_schema_query_max_depth: Optional[int]
    # orm_recursion: bool
    # orm_default_filter_required: Optional[bool]
    # orm_default_field_fail_silently: bool

    strict_root_route: bool
    dependencies_auto_install_disabled: bool

    error_variable_max_length: Optional[int]

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
        default_response_streaming_chunk_size: Optional[int] = None,
        default_aborted_response_status: int = 503,
        default_timeout_response_status: int = 504,
        # ---------
        orm_default_save_with_relations: bool = True,
        orm_default_query_distinct: Optional[bool] = None,
        orm_default_gather_async_fields: bool = False,
        orm_on_non_exists_required_field: Literal['error', 'warn', 'ignore'] = 'warn',
        orm_on_sliced_field_queryset: Literal['error', 'warn', 'ignore'] = 'warn',
        orm_on_conflict_annotation: Literal['error', 'warn', 'ignore'] = 'warn',
        orm_on_conflict_type: Literal['error', 'warn', 'ignore'] = 'warn',
        orm_schema_query_max_depth: Optional[int] = 100,
        dependencies_auto_install_disabled: bool = False,
        error_variable_max_length: Optional[int] = 100,
        default_dns_resolve_timeout: Optional[float] = None,
    ):
        super().__init__(locals())

    @classmethod
    def get(cls) -> "Preference":
        return cls.config() or cls()

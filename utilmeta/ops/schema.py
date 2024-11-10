import utype
from utype import Schema, Field
from utype.types import *
from . import __spec_version__
import utilmeta
from utilmeta.core.api.specs.openapi import OpenAPISchema
from .models import ServiceLog, AccessToken, Worker, WorkerMonitor, \
    ServerMonitor, InstanceMonitor, DatabaseConnection, Supervisor, DatabaseMonitor, CacheMonitor
from utilmeta.core import orm
import sys

language_version = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'


def get_current_instance_data() -> dict:
    try:
        from utilmeta import service
    except ImportError:
        return {}
    return dict(
        version=service.version_str,
        asynchronous=service.asynchronous,
        production=service.production,
        language='python',
        language_version=language_version,
        utilmeta_version=utilmeta.__version__,
        backend=service.backend_name,
        backend_version=service.backend_version
    )


class SupervisorBasic(Schema):
    base_url: str
    ident: str


class SupervisorInfoSchema(Schema):
    utilmeta: str       # spec version
    supervisor: str     # supervisor ident
    timestamp: int


class ServiceInfoSchema(Schema):
    utilmeta: str       # spec version
    service: str     # supervisor ident
    timestamp: int


class NodeInfoSchema(ServiceInfoSchema):
    node_id: str


class NodeMetadata(Schema):
    ops_api: str
    name: str
    base_url: str
    title: Optional[str] = None
    description: str = ''

    version: Optional[str] = None
    spec_version: str = __spec_version__
    production: bool = False

    language: str = 'python'
    language_version: str = language_version
    utilmeta_version: str = utilmeta.__version__


class SupervisorData(Schema):
    node_id: str
    url: Optional[str] = None
    public_key: Optional[str] = None
    ops_api: str
    ident: str
    base_url: Optional[str] = None
    backup_urls: List[str] = Field(default_factory=list)
    init_key: Optional[str] = None
    local: bool = False


class SupervisorPatch(orm.Schema[Supervisor]):
    id: int = orm.Field(no_input=True)
    node_id: str
    ident: Optional[str] = orm.Field(default=None, defer_default=True)
    url: Optional[str] = orm.Field(default=None, defer_default=True)
    base_url: Optional[str] = orm.Field(default=None, defer_default=True)
    backup_urls: List[str] = Field(default_factory=list)
    heartbeat_interval: Optional[int] = orm.Field(default=None, defer_default=True)
    disabled: bool = orm.Field(default=Field, defer_default=True)
    settings: dict = orm.Field(default_factory=dict, defer_default=True)
    alert_settings: dict = orm.Field(default_factory=dict, defer_default=True)
    task_settings: dict = orm.Field(default_factory=dict, defer_default=True)
    aggregate_settings: dict = orm.Field(default_factory=dict, defer_default=True)


class ResourceBase(Schema):
    __options__ = utype.Options(addition=True)

    description: str = ''
    deprecated: bool = False
    tags: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    remote_id: Optional[str] = Field(default=None, no_output=True)


class TableSchema(ResourceBase):
    model_name: Optional[str] = None
    model_backend: Optional[str] = None
    name: str       # table name
    ref: str        # model ref
    ident: str      # ident (name or app_label.model_name)

    base: Optional[str] = None       # base ident
    database: Optional[str] = None
    # select database alias
    fields: dict
    # relations: dict = Field(default_factory=dict)


class ServerSchema(ResourceBase):
    ip: str
    # public_ip: Optional[str] = None
    # domain: Optional[str] = None
    mac: str
    system: str = Field(required=False)
    platform: dict = Field(default_factory=dict)

    utcoffset: Optional[int] = Field(required=False)
    hostname: Optional[str] = Field(required=False)

    cpu_num: int = Field(required=False)
    memory_total: int = Field(required=False)
    disk_total: int = Field(required=False)
    max_open_files: Optional[int] = Field(required=False)
    max_socket_conn: Optional[int] = Field(required=False)
    devices: dict = Field(default_factory=dict)


class InstanceSchema(ResourceBase):
    server: ServerSchema
    version: str = Field(required=False)
    asynchronous: bool = Field(required=False)
    production: bool = Field(required=False)
    language: str = 'python'
    utilmeta_version: str = utilmeta.__version__
    language_version: str = language_version
    backend: str = Field(required=False)
    backend_version: Optional[str] = Field(required=False)


class DatabaseSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    name: str
    user: str
    server: Optional[str] = utype.Field(alias_from=['ip', 'server_ip'], default=None)   # ip
    hostname: Optional[str] = None
    ops: bool = False
    test: bool = False

    max_server_connections: Optional[int] = None


class DatabaseConnectionSchema(orm.Schema[DatabaseConnection]):
    id: int = orm.Field(default=None, defer_default=True)
    database_id: int = orm.Field(default=None, defer_default=True)
    # remote_id = CharField(max_length=100)
    status: str
    active: bool
    client_addr: str
    client_port: int
    pid: Optional[int]

    query: str
    operation: Optional[str]
    tables: List[str]

    backend_start: Optional[datetime] = orm.Field(default=None, defer_default=True)
    transaction_start: Optional[datetime] = orm.Field(default=None, defer_default=True)
    wait_event: Optional[str] = orm.Field(default=None, defer_default=True)
    query_start: Optional[datetime] = orm.Field(default=None, defer_default=True)
    state_change: Optional[datetime] = orm.Field(default=None, defer_default=True)

    data: dict = orm.Field(default_factory=dict, defer_default=True)


class CacheSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    server: Optional[str] = utype.Field(alias_from=['ip', 'server_ip'], default=None)   # ip
    hostname: Optional[str] = None

    max_memory: Optional[int] = None
    max_connections: Optional[int] = None


class ResourcesSchema(Schema):
    metadata: NodeMetadata

    openapi: Optional[OpenAPISchema] = Field(default_factory=None)
    tables: List[TableSchema] = Field(default_factory=list)
    # model

    instances: List[InstanceSchema] = Field(default_factory=list)
    databases: List[DatabaseSchema] = Field(default_factory=list)
    caches: List[CacheSchema] = Field(default_factory=list)
    tasks: list = Field(default_factory=list)


class ResourceData(utype.Schema):
    remote_id: str
    server_id: Optional[str] = utype.Field(default=None, defer_default=True)
    type: str
    ident: str
    route: str
    ref: Optional[str] = utype.Field(default=None, defer_default=True)
    data: dict = utype.Field(default_factory=dict)


class ResourcesData(utype.Schema):
    url: Optional[str] = None
    resources: List[ResourceData]
    resources_etag: str


# ---------------------------------------------------

class WebMixinSchema(orm.Schema):       # not be utype.Schema
    """
        Log data using http/https schemes
    """
    scheme: Optional[str]
    method: Optional[str]
    # replace the unit property
    request_type: Optional[str]
    response_type: Optional[str]
    request_headers: Optional[dict]
    response_headers: Optional[dict]

    user_agent: Optional[dict]
    status: Optional[int]
    length: Optional[int]
    query: Optional[dict]
    data: Union[dict, list, str, None]
    result: Union[dict, list, str, None]

    full_url: Optional[str]
    path: Optional[str]


class ServiceLogBase(orm.Schema[ServiceLog]):
    id: int
    service: str
    node_id: Optional[str]

    instance_id: Optional[int]
    endpoint_id: Optional[int]
    endpoint_ident: Optional[str]

    level: str
    time: float
    duration: Optional[int]

    user_id: Optional[str]
    ip: str

    scheme: Optional[str]
    method: Optional[str]
    status: Optional[int]
    length: Optional[int]
    path = Optional[str]


class ServiceLogSchema(WebMixinSchema, orm.Schema[ServiceLog]):
    id: int
    service: str
    node_id: Optional[str]

    instance_id: Optional[int]
    endpoint_id: Optional[int]
    endpoint_remote_id: Optional[str] = orm.Field('endpoint.remote_id')
    endpoint_ident: Optional[str]
    endpoint_ref: Optional[str]

    worker_id: Optional[int]
    worker_pid: Optional[int] = orm.Field('worker.pid')
    # -----

    level: str
    time: float
    duration: Optional[int]
    thread_id: Optional[int]
    # thread id that handle this request / invoke

    user_id: Optional[str]
    ip: str

    trace: list
    messages: list

    access_token_id: Optional[int]

    in_traffic: int
    out_traffic: int
    public: bool


class AccessTokenSchema(orm.Schema[AccessToken]):
    id: int

    issuer_id: int
    token_id: str
    issued_at: Optional[datetime]
    subject: Optional[str]
    expiry_time: Optional[datetime]

    # ACTIVITY -----------------
    last_activity: Optional[datetime]
    used_times: int
    ip: Optional[str]

    # PERMISSION ---------------
    scope: list
    revoked: bool = False


class SystemMetricsMixin(orm.Schema):
    used_memory: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    file_descriptors: int
    active_net_connections: int
    total_net_connections: int
    net_connections_info: Dict[str, int]
    open_files: Optional[int]

    # def __init__(self, cpu_percent: float, used_memory: float,
    #              memory_percent: float, disk_percent: float,
    #              net_connections_info: Dict[str, int],
    #              file_descriptors: int, active_net_connections: int,
    #              total_net_connections: int, open_files: Optional[int], **kwargs):
    #     super().__init__(locals())


class ServiceMetricsMixin(orm.Schema):
    """
    request metrics that can simply be calculated in form of incr and divide
    """
    in_traffic: Optional[int]
    out_traffic: Optional[int]

    outbound_requests: int
    outbound_rps: float
    outbound_timeouts: int
    outbound_errors: int
    outbound_avg_time: float

    queries_num: int
    query_avg_time: float
    qps: float

    # requests
    requests: int
    rps: float
    errors: int
    # error requests made from current service to target instance
    avg_time: float


class WorkerSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[Worker]):
    server_id: int
    server_remote_id: Optional[str]
    instance_id: int
    instance_remote_id: Optional[str]

    pid: int
    memory_info: dict
    threads: int
    start_time: int

    master_id: Optional[int]
    master_pid: Optional[int] = orm.Field('master__pid')
    connected: bool

    time: int

    status: Optional[str]


class WorkerMonitorSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[WorkerMonitor]):
    id: int

    time: float
    interval: Optional[int] = orm.Field(no_output=True)
    worker_id: int = orm.Field(no_output=True)
    memory_info: dict
    threads: int
    metrics: dict


class ServerMonitorSchema(SystemMetricsMixin, orm.Schema[ServerMonitor]):
    id: int

    time: float
    layer: int = orm.Field(no_output=True)
    interval: Optional[int] = orm.Field(no_output=True)
    server_id: int = orm.Field(no_output=True)
    load_avg_1: Optional[float]
    load_avg_5: Optional[float]
    load_avg_15: Optional[float]
    metrics: dict


class InstanceMonitorSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[InstanceMonitor]):
    id: int

    time: float
    layer: int = orm.Field(no_output=True)
    interval: Optional[int] = orm.Field(no_output=True)

    instance_id: int = orm.Field(no_output=True)
    threads: int

    current_workers: int
    avg_worker_lifetime: Optional[int]
    new_spawned_workers: int
    avg_workers: Optional[float]

    # metrics: dict


class DatabaseMonitorSchema(orm.Schema[DatabaseMonitor]):
    id: int

    time: datetime
    layer: int = orm.Field(no_output=True)
    interval: Optional[int] = orm.Field(no_output=True)

    database_id: int = orm.Field(no_output=True)

    used_space: int
    server_used_space: int
    active_connections: int
    current_connections: int
    server_connections: int

    new_transactions: int

    metrics: dict

    queries_num: int
    qps: Optional[float]
    query_avg_time: float
    operations: dict


class CacheMonitorSchema(orm.Schema[CacheMonitor]):
    id: int

    time: datetime
    layer: int = orm.Field(no_output=True)
    interval: Optional[int] = orm.Field(no_output=True)

    cache_id: int = orm.Field(no_output=True)

    cpu_percent: Optional[float]
    memory_percent: Optional[float]
    used_memory: Optional[int]
    file_descriptors: Optional[int]
    open_files: Optional[int]
    # used_memory = PositiveBigIntegerField(default=0)
    current_connections: int
    total_connections: int
    qps: Optional[float]

    # metrics: dict = orm.Field(no_output=True)

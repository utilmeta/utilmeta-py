import utype
from utype import Schema, Field
from utype.types import *
from . import __spec_version__
import utilmeta
from utilmeta.core.api.specs.openapi import OpenAPISchema
from .models import ServiceLog, AccessToken, Worker, WorkerMonitor, \
    ServerMonitor, DatabaseMonitor, CacheMonitor, InstanceMonitor
from utilmeta.core import orm
from django.db import models


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
    description: str

    version: Optional[str] = None
    spec_version: str = __spec_version__
    production: bool = False


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
    mac: Optional[str] = Field(required=False)
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
    asynchronous: bool = Field(required=False)
    production: bool = Field(required=False)
    language: str = 'python'
    utilmeta_version: str = utilmeta.__version__
    backend: str = Field(required=False)
    backend_version: Optional[str] = Field(required=False)


class DatabaseSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    name: str
    user: str
    server: Optional[str] = None   # ip
    hostname: Optional[str] = None
    ops: bool = False
    test: bool = False

    max_server_connections: Optional[int] = None


class CacheSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    server: Optional[str] = None   # ip
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
    time: datetime
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
    time: datetime
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


class SystemMetricsMixin(Schema):
    used_memory: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    file_descriptors: int
    active_net_connections: int
    total_net_connections: int
    net_connections_info: Dict[str, int]
    open_files: Optional[int]

    def __init__(self, cpu_percent: float, used_memory: float,
                 memory_percent: float, disk_percent: float,
                 net_connections_info: Dict[str, int],
                 file_descriptors: int, active_net_connections: int,
                 total_net_connections: int, open_files: Optional[int], **kwargs):
        super().__init__(locals())


class ServiceMetricsMixin(Schema):
    """
    request metrics that can simply be calculated in form of incr and divide
    """
    in_traffic: Optional[int]
    out_traffic: Optional[int]

    outbound_requests: int
    outbound_rps: int
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
    start_time: datetime

    master_id: Optional[int]
    connected: bool

    time: datetime

    status: Optional[str]


class WorkerMonitorSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[WorkerMonitor]):
    time: datetime
    interval: Optional[int]
    worker_id: int
    memory_info: dict
    threads: int
    metrics: dict


class ServerMonitorSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[WorkerMonitor]):
    time: datetime
    layer: int
    interval: Optional[int]
    server_id: int
    load_avg_1: Optional[float]
    load_avg_5: Optional[float]
    load_avg_15: Optional[float]
    metrics: dict


class InstanceMonitorSchema(SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[InstanceMonitor]):
    time: datetime
    layer: int
    interval: Optional[int]

    instance_id: int
    threads: int

    current_workers: int
    avg_worker_lifetime: Optional[int]
    new_spawned_workers: int
    avg_workers: Optional[float]

    metrics: dict

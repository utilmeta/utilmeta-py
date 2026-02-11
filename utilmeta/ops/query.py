import utype
from utype.types import *
from .models import (
    ServiceLog,
    AccessToken,
    Worker,
    WorkerMonitor,
    ServerMonitor,
    InstanceMonitor,
    DatabaseConnection,
    Supervisor,
    DatabaseMonitor,
    CacheMonitor,
    RequestLog,
    AlertLog
)
from .schema import DatabaseData, CacheData
from utilmeta.core import orm


class SupervisorPatch(orm.Schema[Supervisor]):
    id: int = orm.Field(no_input=True)
    node_id: str
    ident: Optional[str] = orm.Field(default=None, defer_default=True)
    url: Optional[str] = orm.Field(default=None, defer_default=True)
    base_url: Optional[str] = orm.Field(default=None, defer_default=True)
    backup_urls: List[str] = orm.Field(default_factory=list)
    heartbeat_interval: Optional[int] = orm.Field(default=None, defer_default=True)
    default_timeout: Optional[float] = orm.Field(default=None, defer_default=True)
    disabled: bool = orm.Field(default=False, defer_default=True)
    settings: dict = orm.Field(default_factory=dict, defer_default=True)
    alert_settings: dict = orm.Field(default_factory=dict, defer_default=True)
    aggregate_settings: dict = orm.Field(default_factory=dict, defer_default=True)


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


# ---------------------------------------------------


class WebMixinSchema(orm.Schema):  # not be utype.Schema
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
    endpoint_remote_id: Optional[str] = orm.Field("endpoint.remote_id")
    endpoint_ident: Optional[str]
    endpoint_ref: Optional[str]

    worker_id: Optional[int]
    worker_pid: Optional[int] = orm.Field("worker.pid")
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
    details: Optional[dict]

    def __validate__(self):
        from .api.utils import config

        if config.log.hide_ip_address:
            self.ip = "*.*.*.*" if self.ip else ""
        if config.log.hide_user_id:
            self.user_id = "***" if self.user_id else None


class RequestLogBase(orm.Schema[RequestLog]):
    id: int
    service: str
    node_id: Optional[str]

    instance_id: Optional[int]

    time: float
    duration: Optional[int]

    scheme: Optional[str]
    method: Optional[str]
    status: Optional[int]
    length: Optional[int]
    full_url = Optional[str]


class RequestLogSchema(RequestLogBase, WebMixinSchema):
    worker_id: Optional[int]
    worker_pid: Optional[int] = orm.Field("worker.pid")
    context_type: Optional[str]
    context_id: Optional[str]
    host: Optional[str]
    remote_log: Optional[str]
    asynchronous: Optional[bool]
    timeout: Optional[float]
    timeout_error: bool
    server_error: bool
    client_error: bool
    details: Optional[dict]


class AlertLogBase(orm.Schema[AlertLog]):
    id: int
    service: str
    node_id: Optional[str]
    settings_id: Optional[str]
    settings_name: Optional[str]
    severity: int
    instance_id: Optional[str]
    target_id: Optional[str]
    target_remote_id: Optional[str] = orm.Field("target.remote_id")
    time: datetime
    latest_time: datetime
    recovered_time: Optional[datetime]
    count: int


class AlertLogSchema(AlertLogBase):
    settings_data: Optional[dict]
    triggered_values: dict
    latest_alarm_time: datetime
    remote_id: Optional[int]
    remote_recovered_time: Optional[datetime]
    description: str
    message: str
    details: Optional[dict]
    impact: Optional[dict]


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
    used_space: int
    file_descriptors: int
    active_net_connections: int
    total_net_connections: int
    net_connections_info: Dict[str, int]
    open_files: Optional[int] = utype.Field(default=None, defer_default=True)

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
    server_remote_id: Optional[str] = orm.Field("server__remote_id")
    instance_id: int
    instance_remote_id: Optional[str] = orm.Field("instance__remote_id")

    pid: int
    memory_info: dict
    threads: int
    start_time: int

    master_id: Optional[int]
    master_pid: Optional[int] = orm.Field("master__pid")
    connected: bool

    time: int

    status: Optional[str]


class WorkerMonitorSchema(
    SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[WorkerMonitor]
):
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


class InstanceMonitorSchema(
    SystemMetricsMixin, ServiceMetricsMixin, orm.Schema[InstanceMonitor]
):
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
    idle_connections_percent: Optional[float] = orm.Field(default=None)
    server_connections_percent: Optional[float] = orm.Field(default=None)

    new_transactions: int

    metrics: dict

    queries_num: int
    qps: Optional[float]
    query_avg_time: float
    operations: dict


class DatabaseFullMetrics(DatabaseMonitorSchema, DatabaseData):
    pass


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


class CacheFullMetrics(CacheMonitorSchema, CacheData):
    pass

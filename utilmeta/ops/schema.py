import utype
from utype import Schema, Field
from utype.types import *
from . import __spec_version__
import utilmeta
from utilmeta.core.api.specs.openapi import OpenAPISchema
from utilmeta.utils import time_now, pop_null, pop
import sys
import time

language_version = (
    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
)


def get_current_instance_data() -> dict:
    try:
        from utilmeta import service
    except ImportError:
        return {}
    from .config import Operations

    config = service.get_config(Operations)
    return dict(
        version=service.version_str,
        asynchronous=service.asynchronous,
        production=service.production,
        language="python",
        language_version=language_version,
        utilmeta_version=utilmeta.__version__,
        spec_version=__spec_version__,
        backend=service.backend_name,
        backend_version=service.backend_version,
        cwd=str(service.project_dir),
        # host=config.host if config.host else service.host,
        port=config.port if config.host else service.host,
        address=config.address,
    )


class SupervisorBasic(Schema):
    base_url: str
    ident: str


class SupervisorInfoSchema(Schema):
    utilmeta: str  # spec version
    supervisor: str  # supervisor ident
    timestamp: int


class ServiceInfoSchema(Schema):
    utilmeta: str  # spec version
    service: str  # supervisor ident
    timestamp: int


class NodeInfoSchema(ServiceInfoSchema):
    node_id: str


class NodeMetadata(Schema):
    ops_api: str
    name: str
    base_url: str
    title: Optional[str] = None
    description: str = ""

    version: Optional[str] = None
    spec_version: str = __spec_version__
    production: bool = False

    language: str = "python"
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


class ResourceBase(Schema):
    # __options__ = utype.Options(addition=True)

    description: str = ""
    deprecated: bool = False
    tags: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    remote_id: Optional[str] = Field(default=None, no_output=True)


class TableSchema(ResourceBase):
    model_name: Optional[str] = None
    model_backend: Optional[str] = None
    name: str  # table name
    ref: str  # model ref
    ident: str  # ident (name or app_label.model_name)

    base: Optional[str] = None  # base ident
    database: Optional[str] = None
    # select database alias
    fields: dict
    # relations: dict = Field(default_factory=dict)

    model: Any = Field(no_output=True, default=None, defer_default=True)
    # any model class


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
    # max_open_files: Optional[int] = Field(required=False)
    # max_socket_conn: Optional[int] = Field(required=False)
    devices: dict = Field(default_factory=dict)
    limits: dict = Field(default_factory=dict)


class InstanceSchema(ResourceBase):
    server: ServerSchema
    version: str = Field(default=None, defer_default=True)
    asynchronous: bool = Field(default=None, defer_default=True)
    production: bool = Field(default=None, defer_default=True)
    language: str = "python"
    utilmeta_version: str = utilmeta.__version__
    language_version: str = language_version
    backend: str = Field(default=None, defer_default=True)
    backend_version: Optional[str] = Field(default=None, defer_default=True)
    cwd: Optional[str] = Field(default=None, defer_default=True)
    port: Optional[int] = Field(default=None, defer_default=True)
    address: str


class DatabaseSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    name: str
    user: str
    server: Optional[str] = utype.Field(
        alias_from=["ip", "server_ip"], default=None
    )  # ip
    hostname: Optional[str] = None
    ops: bool = False
    test: bool = False

    max_server_connections: Optional[int] = None


class DatabaseData(utype.Schema):
    max_server_connections: Optional[int] = None
    used_space: Optional[int] = None
    transactions: Optional[int] = None
    connected: bool = None


class CacheData(utype.Schema):
    pid: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    file_descriptors: Optional[int] = None
    open_files: Optional[int] = None


class CacheSchema(ResourceBase):
    alias: str
    engine: str
    port: int
    server: Optional[str] = utype.Field(
        alias_from=["ip", "server_ip"], default=None
    )  # ip
    hostname: Optional[str] = None

    max_memory: Optional[int] = None
    max_connections: Optional[int] = None


class ComputedMetricComponentData(ResourceBase):
    name: Optional[str] = Field(alias_from=['metric_name'])
    ref: Optional[str] = Field(default=None, defer_default=True)
    multiplier: float
    inverse: bool


class BaseHandlerData(ResourceBase):
    name: str
    ref: Optional[str] = Field(default=None, defer_default=True)
    title: Optional[str] = None
    parameters: Optional[dict] = Field(default=None, defer_default=True)
    return_value: Optional[Union[dict, str]] = Field(default=None, defer_default=True, alias_from=['return_type'])


class MetricData(BaseHandlerData):
    type: str = 'origin'
    max_value: Optional[int] = Field(default=None, defer_default=True)
    min_value: Optional[int] = Field(default=None, defer_default=True)
    default_threshold: Optional[int] = Field(default=None, defer_default=True)
    default_exceed: Optional[bool] = Field(default=None, defer_default=True)
    default_category: Optional[str] = Field(default=None, defer_default=True)

    metric_type: Optional[str] = Field(default=None, defer_default=True, alias_from=['metric_template'])
    value_type: Optional[str] = Field(default=None, defer_default=True)
    value_unit: Optional[str] = Field(default=None, defer_default=True, alias_from=['unit'])

    resource_type: Optional[str] = Field(default=None, defer_default=True)
    target_param: Optional[str] = Field(default=None, defer_default=True)

    time_unit: Optional[str] = Field(default=None, defer_default=True)
    source_table: Optional[str] = Field(default=None, defer_default=True, alias_from=[
        'model', 'source', 'from_model', 'from_table'])
    # for report=True only

    # aggregated
    aggregation_type: Optional[str] = Field(default=None, defer_default=True, alias_from=['aggregator'])
    aggregation_base: Optional[str] = Field(default=None, defer_default=True)
    # metric ref

    # computed
    operator: Optional[str] = Field(default=None, defer_default=True)
    components: List[ComputedMetricComponentData] = Field(default=None, defer_default=True)

    # parametrized
    function: Optional[str] = Field(default=None, defer_default=True)
    kwargs: Optional[dict] = Field(default=None, defer_default=True)


class EventData(BaseHandlerData):
    default_severity: int
    category: Optional[str]
    resource_type: str
    silent: bool = Field(default=False, defer_default=True)
    source_table: Optional[str] = Field(default=None, defer_default=True, alias_from=[
        'model', 'source', 'from_model', 'from_table'])


class ActionData(BaseHandlerData):
    idempotent: Optional[bool] = Field(default=None, defer_default=True)


class OperationsConfigSchema(Schema):
    __options__ = utype.Options(addition=True)

    worker_cycle_interval: int = utype.Field(alias_from=["worker_cycle"])
    max_retention_time: int = utype.Field(default=None, defer_default=True)
    max_sync_retries: int = utype.Field(default=None, defer_default=True)
    max_backlog: int = utype.Field(default=None, defer_default=True)
    secret_names: List[str] = Field(default_factory=list)
    trusted_hosts: List[str] = Field(default_factory=list)
    disabled_scope: List[str] = Field(default_factory=list)
    local_scope: List[str] = Field(default_factory=list)
    private_scope: List[str] = Field(default_factory=list)


class ResourcesSchema(Schema):
    __options__ = utype.Options(addition=True)

    metadata: NodeMetadata
    config: Optional[OperationsConfigSchema] = Field(default=None, defer_default=True)

    openapi: Optional[OpenAPISchema] = Field(default=None, defer_default=True)
    tables: List[TableSchema] = Field(default_factory=list)
    # model

    instances: List[InstanceSchema] = Field(default_factory=list)
    databases: List[DatabaseSchema] = Field(default_factory=list)
    caches: List[CacheSchema] = Field(default_factory=list)
    events: List[EventData] = Field(default_factory=list)
    metrics: List[MetricData] = Field(default_factory=list)
    actions: List[ActionData] = Field(default_factory=list)
    # alerts: Optional[AlertsData] = Field(default=None, defer_default=True)
    # tasks: list = Field(default_factory=list)


class ResourceData(utype.Schema):
    remote_id: str
    server_id: Optional[str] = utype.Field(default=None, defer_default=True)
    type: str
    ident: str
    route: str
    ref: Optional[str] = utype.Field(default=None, defer_default=True)
    data: dict = utype.Field(default_factory=dict)


class SupervisorSyncData(Schema):
    node_id: str
    url: Optional[str] = Field(default=None, defer_default=True)
    resources_etag: Optional[str] = Field(default=None, defer_default=True)
    heartbeat_interval: Optional[int] = Field(default=None, defer_default=True)
    settings: dict = Field(default_factory=dict, defer_default=True)
    alert_settings: dict = Field(default_factory=dict, defer_default=True)
    report_settings: dict = Field(default_factory=dict, defer_default=True)


class ResourcesData(utype.Schema):
    # url: Optional[str] = None
    # resources_etag: Optional[str] = None
    resources: List[ResourceData]
    supervisor: SupervisorSyncData


class SupervisorPatchSchema(SupervisorSyncData):
    id: int = Field(no_input=True)
    ident: Optional[str] = Field(default=None, defer_default=True)
    base_url: Optional[str] = Field(default=None, defer_default=True)
    backup_urls: List[str] = Field(default_factory=list)
    disabled: bool = Field(default=False, defer_default=True)


class ResourceDataSchema(Schema):
    id: int
    ident: str
    route: str
    service: Optional[str]
    node_id: Optional[str]
    # :type/:node/:ident
    ref: Optional[str]
    remote_id: Optional[str]
    server_id: Optional[int]
    # created_time: Optional[datetime]
    # updated_time: Optional[datetime]
    deprecated: bool


class InstanceResourceSchema(ResourceDataSchema):
    backend: Optional[str] = Field(default=None, defer_default=True)
    backend_version: Optional[str] = Field(default=None, defer_default=True)
    version: Optional[str] = Field(default=None, defer_default=True)
    spec_version: Optional[str] = Field(default=None, defer_default=True)
    asynchronous: Optional[bool] = Field(default=None, defer_default=True)
    production: Optional[bool] = Field(default=None, defer_default=True)
    language: Optional[str] = Field(default=None, defer_default=True)
    language_version: Optional[str] = Field(default=None, defer_default=True)
    utilmeta_version: Optional[str] = Field(default=None, defer_default=True)


class ServerResourceSchema(ResourceDataSchema):
    ip: Optional[str] = Field(default=None, defer_default=True)
    cpu_num: Optional[int] = Field(default=None, defer_default=True)
    memory_total: Optional[int] = Field(default=None, defer_default=True)
    disk_total: Optional[int] = Field(default=None, defer_default=True)
    system: Optional[str] = Field(default=None, defer_default=True)
    hostname: Optional[str] = Field(default=None, defer_default=True)
    platform: Optional[dict] = Field(default=None, defer_default=True)


class QuerySchema(utype.Schema):
    # id_list: list = None
    query: dict = {}
    orders: List[str] = ["pk"]
    rows: int = utype.Field(default=10, le=100, ge=1)
    page: int = utype.Field(default=1, ge=1)
    fields: list = []
    max_length: Optional[int] = None


class CreateDataSchema(utype.Schema):
    data: List[dict]
    return_fields: List[str] = utype.Field(default_factory=list)
    return_max_length: Optional[int] = None


# class PkRequired(utype.Schema):
#     __options__ = utype.Options(addition=True)
#
#     pk: Any = utype.Field(alias_from=['id'], no_output=True)


class UpdateDataSchema(utype.Schema):
    data: List[dict]


class AlertSchema(utype.Schema):
    time: float = Field(default_factory=time.time)
    latest_time: float = Field(default=None, defer_default=True)
    settings_id: Optional[str] = Field(default=None, defer_default=True)
    settings_name: Optional[str] = Field(default=None, defer_default=True, alias_from=['event_name'])
    description: str = Field(default='', defer_default=True)
    target_id: Optional[str] = Field(default=None, defer_default=True)
    alert_id: Optional[str] = Field(default=None, defer_default=True)
    event_id: Optional[str] = Field(default=None, defer_default=True)
    # custom event ID to de-duplicate alerting and incidents
    severity: int
    count: int = 1
    details: dict = utype.Field(default_factory=dict)
    impact: dict = utype.Field(default=None, defer_default=True)

    def __validate__(self):
        if not self.settings_id and not self.settings_name:
            raise ValueError(f'AlertSchema must initialized with settings_id or settings_name')

# class EventSchema(utype.Schema):
#     time: datetime = Field(default_factory=time_now)
#     event_name: str
#     # target_id: Optional[str] = Field(default=None, defer_default=True)
#     data: dict = utype.Field(default_factory=dict)


class RecoveryEventData(utype.Schema):
    id: Optional[str]
    alert_id: str
    message: str = ''
    recovered_time: float = Field(default_factory=time.time)
    latest_time: Optional[float] = Field(default=None, defer_default=True)
    count: Optional[int] = Field(default=None, defer_default=True)
    details: Optional[dict] = utype.Field(default=None, defer_default=True)


# SUPERVISOR SETTINGS -------------------------

class AlertSettingsParams(utype.Schema):
    id: Optional[str] = None
    name: Optional[str] = None
    target_id: Optional[str] = None          # resource.remote_id
    target_ident: Optional[str] = None       # resource.ident
    compress_window: Optional[int] = None
    parameters: Optional[dict] = None
    severity: int
    silent: Optional[bool] = None
    # in seconds
    # exceed or below
    min_times: Optional[int] = None
    min_duration: Optional[int] = None
    min_alarm_interval: Optional[int] = None

    @classmethod
    def default(cls):
        return cls(severity=2, silent=True)

    def get_settings_data(self) -> dict:
        d = pop_null(self)
        pop(d, 'id')
        return d

    def match_target(self, target=None):
        if not target:
            return not self.target_id and not self.target_ident
        from .models import Resource
        if isinstance(target, Resource):
            return self.target_id == target.pk or self.target_ident == target.ident
        return self.target_id == target or self.target_ident == target


class EventAlertSettingsSchema(AlertSettingsParams):
    resource_type: Optional[str] = None
    # node_id: str
    type: str = 'event'
    # metric
    # event

    # event_type: str
    # not null if type=event
    event_ref: str


class MetricAlertSettingsSchema(AlertSettingsParams):
    resource_type: Optional[str] = None
    # node_id: str
    type: str = 'metric'
    # metric
    # event

    # metric ---
    # metric_name: str
    metric_ref: str
    strategy: str
    strategy_data: Optional[dict] = None
    threshold: Optional[str] = None
    exceed: bool = True

    # latest_time before compress_window is consider a new alert
    check_interval: Optional[int] = None


class SupervisorAlertSettingsSchema(utype.Schema):
    events: List[EventAlertSettingsSchema] = utype.Field(default_factory=list)
    metrics: List[MetricAlertSettingsSchema] = utype.Field(default_factory=list)


class EndpointConditionSchema(utype.Schema):
    path: str = None
    query: dict = None
    headers: dict = None


class BehaviourEndpointSchema(utype.Schema):
    endpoint_ident: str
    endpoint_id: str
    required: bool = Field(default=False)
    condition: Optional[EndpointConditionSchema] = Field(default=None)
    # - path
    # - query
    # - headers

    @property
    def logs_q(self):
        from django.db import models
        base_q = models.Q(
            endpoint_ident=self.endpoint_ident,
        ) | models.Q(
            endpoint__ident=self.endpoint_ident,
        ) | models.Q(
            endpoint__remote_id=self.endpoint_id,
        ) | models.Q(
            endpoint_id=self.endpoint_id,
        )
        if not self.condition:
            return base_q
        if self.condition.path:
            base_q &= models.Q(path__contains=self.condition.path)
        if self.condition.query:
            # todo: handle split that does not support json query
            for key, val in self.condition.query.items():
                base_q &= models.Q(**{
                    f'query__{key}': str(val)
                })
        if self.condition.headers:
            for key, val in self.condition.headers.items():
                base_q &= models.Q(**{
                    f'request_headers__{str(key).lower()}': str(val)
                })
        return base_q


class UserBehaviourSchema(utype.Schema):
    id: str
    node_id: Optional[str] = Field(default=None, defer_default=True)
    level: int = Field(default=0)
    excluded: bool = Field(default=False)
    inactivity_threshold: Optional[int] = None
    endpoints: List[BehaviourEndpointSchema]

    @property
    def logs_q(self):
        from django.db import models
        q = models.Q()
        for endpoint in self.endpoints:
            if endpoint.required:
                q &= endpoint.logs_q
            else:
                q |= endpoint.logs_q
        return q


class ReportMetricSchema(utype.Schema):
    id: Optional[str] = None
    name: str
    ref: str
    time_unit: str
    kwargs: Optional[dict] = None


class SupervisorReportSettingsSchema(utype.Schema):
    __options__ = utype.Options(addition=True)

    utcoffset: int = 0
    # by default, report runs at UTC 00:00
    # set this offset to move to the ACTUAL 00:00 of the user timezone (may not be the server timezone)
    # service_daily_report_enabled: bool = True
    # service_hourly_report_enabled: bool = True
    report_max_batch_size: int = Field(default=100)

    ip_report_enabled: bool = True
    ip_report_limit: Optional[int] = Field(default=1000)
    agent_report_enabled: bool = True

    endpoint_hourly_report_enabled: bool = False
    endpoint_daily_report_enabled: bool = False

    system_report_enabled: bool = False
    metrics_report_enabled: bool = True
    hourly_report_expiry_hours: int = Field(default=24 * 7)
    daily_report_expiry_hours: int = Field(default=24 * 30)

    user_report_enabled: bool = False
    user_report_limit: Optional[int] = Field(default=1000)
    user_hash_id: bool = False
    # require hide the real user id
    user_inactivity_threshold: int = Field(default=60 * 10)
    user_behaviours: List[UserBehaviourSchema] = utype.Field(default_factory=list)
    # --------
    report_metrics: List[ReportMetricSchema] = utype.Field(default_factory=list)


class SupervisorSettingsSchema(utype.Schema):
    __options__ = utype.Options(addition=True)

    # max_sync_retries: int = Field(default=10)

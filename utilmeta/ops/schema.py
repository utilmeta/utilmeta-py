import utype
from utype import Schema, Field
from utype.types import *
from . import __spec_version__
import utilmeta
from utilmeta.core.api.specs.openapi import OpenAPISchema
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
        spec_version=__spec_version__,
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
    
    
class SupervisorPatchSchema(Schema):
    id: int = Field(no_input=True)
    node_id: str
    ident: Optional[str] = Field(default=None, defer_default=True)
    url: Optional[str] = Field(default=None, defer_default=True)
    base_url: Optional[str] = Field(default=None, defer_default=True)
    backup_urls: List[str] = Field(default_factory=list)
    heartbeat_interval: Optional[int] = Field(default=None, defer_default=True)
    disabled: bool = Field(default=False, defer_default=True)
    settings: dict = Field(default_factory=dict, defer_default=True)
    alert_settings: dict = Field(default_factory=dict, defer_default=True)
    task_settings: dict = Field(default_factory=dict, defer_default=True)
    aggregate_settings: dict = Field(default_factory=dict, defer_default=True)


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
    created_time: Optional[datetime]
    updated_time: Optional[datetime]
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

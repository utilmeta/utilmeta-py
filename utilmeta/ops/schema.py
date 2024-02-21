import utype
from utype import Schema, Field
from utype.types import *
from . import __spec_version__
import utilmeta
from utilmeta.core.api.specs.openapi import OpenAPISchema


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
    public_key: str
    ops_api: str
    ident: str
    base_url: Optional[str] = None
    backup_urls: List[str] = Field(default_factory=list)
    init_key: Optional[str] = None


class ResourceBase(Schema):
    __options__ = utype.Options(addition=True)

    description: str = ''
    deprecated: bool = False
    tags: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    remote_id: Optional[str] = None


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
    system: str
    platform: dict = Field(default_factory=dict)

    utcoffset: Optional[int] = None
    hostname: Optional[str]

    cpu_num: int
    memory_total: int
    disk_total: int
    max_open_files: Optional[int] = None
    max_socket_conn: Optional[int] = None
    devices: dict = Field(default_factory=dict)


class InstanceSchema(ResourceBase):
    server: ServerSchema
    asynchronous: bool = False
    production: bool = False
    language: str = 'python'
    utilmeta_version: str = utilmeta.__version__
    backend: str
    backend_version: Optional[str] = None


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
    resources: List[ResourceData]
    resources_etag: str

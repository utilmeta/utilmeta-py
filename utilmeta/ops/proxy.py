import utype

from utilmeta.core import cli, request, response

# from utilmeta.utils import url_join
from utype import Schema, Field
from utype.types import *


class RegistrySchema(Schema):
    name: str = utype.Field(alias_from=["service_name", "service_id"])
    title: Optional[str] = utype.Field(default=None, defer_default=True)
    description: str = ""
    address: str  # host + port
    # host: str = utype.Field(alias_from=['ip'])
    # port: Optional[int] = None
    # host:port
    base_url: str
    # address + base_route
    ops_api: str
    instance_id: str = utype.Field(alias_from=["resource_id"])
    # this field will be checked by the proxy
    # server_id: Optional[str] = Field(default=None, defer_default=True)
    # remote_id: Optional[str] = Field(default=None, defer_default=True)
    # server_mac = models.CharField(max_length=50, null=True)
    cwd: Optional[str] = Field(required=False)
    version: str
    # ------ PROPS
    asynchronous: bool = Field(required=False)
    production: bool = Field(required=False)
    language: str
    language_version: str = Field(required=False)
    # python / java / go / javascript / php
    utilmeta_version: str
    # python version
    backend: str = "utilmeta"
    # runtime framework
    backend_version: str = Field(required=False)
    resources: Optional[dict] = Field(default=None, defer_default=True)

    def get_metadata(self):
        from .client import NodeMetadata

        data = (self.resources or {}).get("metadata") or dict(
            ops_api=self.ops_api,
            base_url=self.base_url,
            name=self.name,
            title=self.title,
            description=self.description,
            version=self.version,
            production=self.production,
        )
        return NodeMetadata(data)


class RegistryInstanceSchema(Schema):
    id: int
    service_id: str
    node_id: Optional[str]

    address: str
    base_url: str
    ops_api: str

    resource_id: str
    server_id: Optional[str]
    remote_id: Optional[str]
    cwd: Optional[str]

    weight: float
    connected: bool
    public: bool
    # ip.is_global
    version: str

    # ------ PROPS
    asynchronous: bool
    production: bool
    language: str
    language_version: str
    # python / java / go / javascript / php
    utilmeta_version: str
    # python version
    backend: str
    backend_version: Optional[str]
    created_time: datetime
    # deleted_time = models.DateTimeField(default=None, null=True)
    deprecated: bool

    resources_etag: Optional[str]
    data: dict = Field(required=False)


class RegistryResponse(response.Response):
    result: RegistryInstanceSchema


class ProxyClient(cli.Client):
    proxy: cli.Client

    @cli.post("registry")
    def register_service(self, data: RegistrySchema = request.Body) -> RegistryResponse:
        pass

    # def proxy_request(self,
    #                   method: str, path: str = None, query: dict = None,
    #                   data=None,
    #                   headers: dict = None, cookies=None, timeout: int = None):
    #     return self.request(
    #         method=method,
    #         path=url_join('proxy', path, with_scheme=False)
    #     )

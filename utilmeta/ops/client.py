import utype

from utilmeta.core.cli import Client
from utilmeta.core import response, api
from utilmeta.core import request
from utype.types import *

from .key import encrypt_data
from .schema import (NodeMetadata, SupervisorBasic, ServiceInfoSchema, SupervisorInfoSchema, \
                     SupervisorData, ResourcesSchema, ResourcesData, NodeInfoSchema, InstanceResourceSchema,
                     SupervisorPatchSchema, OpenAPISchema, TableSchema)


class SupervisorResponse(response.Response):
    result_key = 'result'
    message_key = 'msg'
    state_key = 'state'
    count_key = 'count'


class SupervisorListResponse(SupervisorResponse):
    name = 'list'
    result: List[SupervisorBasic]


class OpenAPIResponse(response.Response):
    result: OpenAPISchema


class InstanceResponse(SupervisorResponse):
    name = 'instance'
    result: List[InstanceResourceSchema]


class TableResponse(SupervisorResponse):
    name = 'table'
    result: List[TableSchema]


class SupervisorInfoResponse(SupervisorResponse):
    name = 'info'
    result: SupervisorInfoSchema

    def validate(self):
        if super().success:
            if self.result.utilmeta:
                return True
        return False

    # success property is used to init error and state before the result is initialized
    # so it cannot access result, or will get None


class NodeInfoResponse(SupervisorResponse):
    name = 'add_node'
    result: NodeInfoSchema

    def validate(self):
        if super().success:
            if self.result.utilmeta and self.result.node_id:
                return True
        return False


class ServiceInfoResponse(SupervisorResponse):
    name = 'info'
    result: ServiceInfoSchema

    def validate(self):
        if super().success:
            if self.result.utilmeta:
                return True
        return False


class SupervisorResourcesResponse(SupervisorResponse):
    name = 'resources'
    result: ResourcesData


class ReportResult(utype.Schema):
    id: str
    created_records: int = 0


class SupervisorNodeResponse(SupervisorResponse):
    name = 'add_node'
    result: Optional[SupervisorData] = None


class SupervisorReportResponse(SupervisorResponse):
    name = 'report'
    result: ReportResult


class SupervisorBatchReportResponse(SupervisorResponse):
    name = 'batch_report'
    result: List[dict]

# class AddNodeResponse(SupervisorResponse):
#     name = 'info'
#     result: InfoSchema


class SupervisorClient(Client):
    @api.post('/')
    def add_node(self, data: NodeMetadata = request.Body) -> Union[SupervisorNodeResponse, SupervisorResponse]: pass

    @api.post('/')
    async def async_add_node(self, data: NodeMetadata = request.Body) \
            -> Union[SupervisorNodeResponse, SupervisorResponse]: pass

    @api.delete('/')
    def delete_node(self) -> SupervisorResponse: pass

    @api.post('/resources')
    def upload_resources(self, data: ResourcesSchema = request.Body) \
            -> Union[SupervisorResourcesResponse, SupervisorResponse]: pass

    @api.post('/resources')
    async def async_upload_resources(self, data: ResourcesSchema = request.Body) \
            -> Union[SupervisorResourcesResponse, SupervisorResponse]: pass

    @api.get('/list')
    def get_supervisors(self) -> Union[SupervisorListResponse, SupervisorResponse]: pass

    @api.get('/list')
    async def async_get_supervisors(self) -> Union[SupervisorListResponse, SupervisorResponse]: pass

    @api.get('/')
    def get_info(self) -> Union[SupervisorInfoResponse, SupervisorResponse]: pass

    @api.get('/')
    async def async_get_info(self) -> Union[SupervisorInfoResponse, SupervisorResponse]: pass

    @api.post('/report')
    def report_analytics(self, data: dict = request.Body) -> Union[SupervisorReportResponse, SupervisorResponse]:
        pass

    @api.post('/report')
    async def async_report_analytics(self, data: dict = request.Body)\
            -> Union[SupervisorReportResponse, SupervisorResponse]:
        pass

    @api.post('/report/batch')
    def batch_report_analytics(self, data: list = request.Body) -> (
            Union)[SupervisorBatchReportResponse, SupervisorResponse]:
        pass

    @api.post('/report/batch')
    async def async_batch_report_analytics(self, data: list = request.Body) -> (
            Union)[SupervisorBatchReportResponse, SupervisorResponse]:
        pass

    @api.post('/alert')
    def alert_incident(self):
        pass

    @api.post('/alert')
    async def async_alert_incident(self):
        pass

    # @utype.parse
    # def get_supervisors(self) -> List[SupervisorBasic]:
    #     r = self.get('/list')
    #     if r.success:
    #         return r.data
    #     return []

    def __init__(self,
                 access_key: str = None,
                 cluster_key: str = None,
                 cluster_id: str = None,
                 node_id: str = None,
                 service_id: str = None,
                 node_key: str = None,
                 **kwargs):
        super().__init__(**kwargs)

        headers = {}
        if access_key:
            # only required in ADD_NODE operation
            headers.update({
                'X-Access-Key': access_key,
            })

        if cluster_key:
            headers.update({
                'X-Cluster-Key': cluster_key
            })
        if cluster_id:
            headers.update({
                'X-Cluster-Id': cluster_id
            })

        if node_id:
            headers.update({
                'X-Node-ID': node_id
            })
            from .models import Supervisor
            supervisor: Supervisor = Supervisor.objects.filter(
                node_id=node_id,
            ).first()
            if not supervisor:
                raise ValueError(f'Supervisor for node ID [{node_id}] not exists')

            if not node_key:
                if supervisor.disabled:
                    raise ValueError('supervisor is disabled')
                if supervisor.public_key:
                    node_key = supervisor.public_key

            if not self._base_url:
                self._base_url = supervisor.base_url

        if node_key:
            headers.update({
                'X-Node-Key': node_key
            })
        if service_id:
            headers.update({
                'X-Service-ID': service_id
            })

        from .config import Operations
        config = Operations.config()
        if config:
            if config.proxy and config.proxy.forward:
                self.update_base_headers({
                    'x-utilmeta-proxy-type': 'forward'
                })
                self._base_url = config.proxy.proxy_url
            else:
                config.check_supervisor(self._base_url)
                # also check supervisor here
                # --- THIS IS A SECURITY MEASURE
                # in the worst case scenario, attacker got the ops db permission
                # and changed the base url of supervisor (to a hostile address)
                # the request will not be sent since it violate the [trusted_hosts]

        self.node_id = node_id
        self.node_key = node_key
        self.access_key = access_key
        self.cluster_key = cluster_key

        self._base_headers.update(headers)

    def process_request(self, req: request.Request):
        if req.body is not None:
            pub_key = self.node_key or self.cluster_key or self.access_key
            # nearest are prior
            if pub_key:
                try:
                    encrypted = encrypt_data(req.body, public_key=pub_key)
                except Exception as e:
                    raise ValueError(f'Invalid Operations access key, encode body failed with error: {e}')
                req.body = encrypted
                # set request body
        return req


class OperationsClient(Client):
    def __init__(
        self,
        token: str = None,
        node_id: str = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.token = token
        self.node_id = node_id
        if self.token:
            self.update_base_headers({
                'authorization': f'Bearer {self.token}'
            })
        if self.node_id:
            self.update_base_headers({
                'x-node-id': self.node_id
            })

    @api.post('/')
    def add_supervisor(self, data: SupervisorData = request.Body) -> NodeInfoResponse: pass

    @api.post('/')
    async def async_add_supervisor(self, data: SupervisorData = request.Body) -> NodeInfoResponse: pass

    @api.patch('/')
    def update_supervisor(self, data: SupervisorPatchSchema = request.Body) -> NodeInfoResponse: pass

    @api.patch('/')
    async def async_update_supervisor(self, data: SupervisorPatchSchema = request.Body) -> NodeInfoResponse: pass

    @api.post('/token/revoke')
    def revoke_token(self, id_list: List[str] = request.Body) -> SupervisorResponse[int]: pass

    @api.post('/token/revoke')
    async def async_revoke_token(self, id_list: List[str] = request.Body) -> SupervisorResponse[int]: pass

    @api.delete('/')
    def delete_supervisor(self) -> SupervisorResponse: pass

    @api.delete('/')
    async def async_delete_supervisor(self) -> SupervisorResponse: pass

    @api.get('/openapi')
    def get_openapi(self) -> OpenAPIResponse: pass

    @api.get('/openapi')
    async def async_get_openapi(self) -> OpenAPIResponse: pass

    @api.get('/data/tables')
    def get_tables(self) -> TableResponse: pass

    @api.get('/data/tables')
    async def async_get_tables(self) -> TableResponse: pass

    @api.get('/servers/instances')
    def get_instances(self) -> InstanceResponse: pass

    @api.get('/servers/instances')
    async def async_get_instances(self) -> InstanceResponse: pass

    @api.get('/')
    def get_info(self) -> Union[ServiceInfoResponse, SupervisorResponse]: pass

    @api.get('/')
    async def async_get_info(self) -> Union[ServiceInfoResponse, SupervisorResponse]: pass

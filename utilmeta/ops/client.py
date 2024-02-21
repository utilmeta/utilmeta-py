import utype

from utilmeta.core.cli import Client
from utilmeta.core import response, api
from utilmeta.core import request
from utype.types import *
from .key import encrypt_data
from .schema import NodeMetadata, SupervisorBasic, ServiceInfoSchema, SupervisorInfoSchema, \
    SupervisorData, ResourcesSchema, ResourcesData


class SupervisorResponse(response.Response):
    result_key = 'result'
    message_key = 'msg'
    state_key = 'state'
    count_key = 'count'


class SupervisorListResponse(SupervisorResponse):
    name = 'list'
    result: List[SupervisorBasic]


class SupervisorInfoResponse(SupervisorResponse):
    name = 'info'
    result: SupervisorInfoSchema

    @property
    def success(self):
        if super().success:
            if self.result.utilmeta:
                return True
        return False


class ServiceInfoResponse(SupervisorResponse):
    name = 'info'
    result: ServiceInfoSchema

    @property
    def success(self):
        if super().success:
            if self.result.utilmeta:
                return True
        return False


class SupervisorResourcesResponse(SupervisorResponse):
    name = 'resources'
    result: ResourcesData


class NodeData(utype.Schema):
    node_id: str
    url: str


class SupervisorNodeResponse(SupervisorResponse):
    name = 'add_node'
    result: NodeData


# class AddNodeResponse(SupervisorResponse):
#     name = 'info'
#     result: InfoSchema


class SupervisorClient(Client):
    @api.post('/')
    def add_node(self, data: NodeMetadata = request.Body) -> SupervisorNodeResponse: pass

    @api.post('/resources')
    def upload_resources(self, data: ResourcesSchema = request.Body) -> SupervisorResourcesResponse: pass

    @api.get('/list')
    def get_supervisors(self) -> SupervisorListResponse: pass

    @api.get('/')
    def get_info(self) -> SupervisorInfoResponse: pass
    # @utype.parse
    # def get_supervisors(self) -> List[SupervisorBasic]:
    #     r = self.get('/list')
    #     if r.success:
    #         return r.data
    #     return []

    def __init__(self,
                 access_key: str = None,
                 node_id: str = None,
                 node_key: str = None,
                 **kwargs):
        super().__init__(**kwargs)

        headers = {}
        if access_key:
            # only required in ADD_NODE operation
            headers.update({
                'X-Access-Key': access_key,
            })

        if node_id:
            headers.update({
                'X-Node-ID': node_id
            })
            if not node_key:
                from .models import Supervisor
                supervisor: Supervisor = Supervisor.filter(id=node_id).first()
                if not supervisor:
                    raise ValueError(f'Supervisor for node ID [{node_id}] not exists')
                node_key = supervisor.public_key

        if node_key:
            headers.update({
                'X-Node-Key': node_key
            })

        self.node_id = node_id
        self.node_key = node_key
        self.access_key = access_key

        self._base_headers.update(headers)

    def process_request(self, req: request.Request):
        if req.body is not None:
            pub_key = self.access_key or self.node_key
            if pub_key:
                encrypted = encrypt_data(req.body, public_key=pub_key)
                req.body = encrypted
                # set request body
        return req


class OperationsClient(Client):
    @api.post('/')
    def add_supervisor(self, data: SupervisorData = request.Body) -> ServiceInfoResponse: pass

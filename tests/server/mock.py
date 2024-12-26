from utilmeta.core import api, request
from utype.types import *
from utilmeta.ops.schema import ResourcesSchema, SupervisorData
from utilmeta.ops.client import OperationsClient
from utilmeta.ops.config import Operations
from utilmeta.ops import __spec_version__
from utilmeta.utils import exceptions
import time
import utype


class SupervisorMockAPI(api.API):
    node_id: Optional[str] = request.HeaderParam('X-Node-ID', default=None)
    service_id: Optional[str] = request.HeaderParam('X-Service-ID', default=None)
    node_key: Optional[str] = request.HeaderParam('X-Node-Key', default=None)
    access_key: Optional[str] = request.HeaderParam('X-Access-Key', default=None)

    cluster_id: Optional[str] = request.HeaderParam('X-Cluster-ID', default=None)
    cluster_key: Optional[str] = request.HeaderParam('X-Cluster-Key', default=None)

    @api.get
    def get(self):
        """
        get supervisor status
        """
        return dict(
            utilmeta=__spec_version__,
            supervisor='test',
            timestamp=int(time.time() * 1000),
        )

    @api.get
    def list(self):
        return [dict(ident='test', base_url='http://127.0.0.1:8000/api/spv', connected=True)]

    @api.post
    def resources(self, data: ResourcesSchema = request.Body):
        pass

    class NodeData(utype.Schema):
        ops_api: str
        name: str
        base_url: str
        title: Optional[str] = None
        description: str = ''

        version: Optional[str] = None
        spec_version: str = None
        production: bool = False

        language: Optional[str] = utype.Field(default=None)
        language_version: Optional[str] = utype.Field(default=None)
        utilmeta_version: Optional[str] = utype.Field(default=None)

    def post(self, data: NodeData = request.Body) -> SupervisorData:
        if not self.access_key and not self.cluster_key:
            raise exceptions.BadRequest('key required')
        from utilmeta import service
        config = service.get_config(Operations)
        node_id = 'TEST_NODE_ID'
        supervisor_data = SupervisorData(
            node_id=node_id,
            url=config.connect_url,
            public_key='TEST_PUBLIC_KEY',
            ops_api=config.ops_api,
            ident='test',
            base_url=data.base_url,
            backup_urls=[],
            init_key=self.cluster_key or self.access_key or 'TESt_INIT_KEY'
        )
        with OperationsClient(
            base_url=config.ops_api,
            node_id=node_id,
        ) as client:
            client.add_supervisor(supervisor_data)
        return supervisor_data

    def delete(self):
        if not self.access_key:
            raise exceptions.BadRequest('key required')
        from utilmeta import service
        config = service.get_config(Operations)
        node_id = 'TEST_NODE_ID'
        with OperationsClient(
            base_url=config.ops_api,
            node_id=node_id,
        ) as client:
            client.delete_supervisor()
        return node_id

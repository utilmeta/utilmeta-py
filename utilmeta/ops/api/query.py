from utilmeta.core import api
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire


class QueryAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    # scope: data.view:[TABLE_IDENT]
    @opsRequire('data.query')
    def get(self):
        pass

    @opsRequire('data.create')
    def post(self):
        pass

    @opsRequire('data.update')
    def put(self):
        pass

    @opsRequire('data.delete')
    def delete(self):
        pass

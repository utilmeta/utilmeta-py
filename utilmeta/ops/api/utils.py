from utilmeta.core import api, orm, request, response, auth
from utilmeta.utils import exceptions
from ..models import Supervisor
from ..config import Operations
from utilmeta.core.request import var
from utype.types import *


class SupervisorObject(orm.Schema[Supervisor]):
    id: Optional[int]
    service: str
    node_id: Optional[str]
    url: Optional[str] = None
    public_key: Optional[str] = None
    init_key: Optional[str] = None
    ops_api: str
    ident: Optional[str]
    base_url: Optional[str] = None
    local: bool = False


# excludes = var.RequestContextVar('_excludes', cached=True)
# params = var.RequestContextVar('_params', cached=True)
supervisor_var = var.RequestContextVar('_ops.supervisor', cached=True)
access_token_var = var.RequestContextVar('_ops.access_token', cached=True)
resources_var = var.RequestContextVar('_scopes.resource', cached=True, default=list)

config = Operations.config()


class WrappedResponse(response.Response):
    result_key = 'result'
    message_key = 'msg'
    state_key = 'state'
    count_key = 'count'


class opsRequire(auth.Require):
    def validate_scopes(self, req: request.Request):
        if config.disabled_scope and config.disabled_scope.intersection(self.scopes):
            raise exceptions.PermissionDenied(f'Operation: {self.scopes} denied by config')
        return super().validate_scopes(req)

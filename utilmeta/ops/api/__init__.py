from utilmeta.core import api, orm, request
from ..schema import SupervisorData,  AccessTokenSchema
from utilmeta.utils import exceptions, adapt_async
from ..models import Supervisor, AccessToken
from .. import __spec_version__
from ..key import decode_token
from utilmeta.core.request import var
from django.db import utils
from utype.types import *
from ..connect import save_supervisor
from utilmeta.core.api.specs.openapi import OpenAPI
from .query import QueryAPI
from .log import LogAPI
from .servers import ServersAPI
from .token import TokenAPI
from .utils import opsRequire, WrappedResponse, config, supervisor_var, \
    SupervisorObject, resources_var, access_token_var


@api.CORS(
    allow_origin='*',
    allow_headers=[
        'authorization',
        'x-node-id'
    ],
    cors_max_age=3600 * 6
)
class OperationsAPI(api.API):
    __external__ = True

    servers: ServersAPI
    data: QueryAPI
    logs: LogAPI

    token: TokenAPI
    openapi: opsRequire('api.view')(OpenAPI.as_api(private=False))
    response = WrappedResponse
    # @api.get
    # @opsRequire('api.view')
    # def openapi(self):
    #     from utilmeta import service
    #     openapi = OpenAPI(service)()

    # @orm.Atomic(config.db_alias)
    @adapt_async
    def post(self, data: SupervisorData = request.Body):
        save_supervisor(data)
        return dict(
            node_id=data.node_id,
            # this is critical
            # if the POST /api/ops redirect to GET /api/ops by 301
            # the supervisor will not notice the difference by the result data if this field is not filled
            **self.get()
        )

    def get(self):
        try:
            from utilmeta import service    # noqa
            name = service.name
        except ImportError:
            # raise exceptions.ServerError('service not initialized')
            name = None
        return dict(
            utilmeta=__spec_version__,
            service=name,
            timestamp=int(self.request.time.timestamp() * 1000),
        )

    @api.before('*', excludes=(get, post))
    def handle_token(self, node_id: str = request.HeaderParam('X-Node-ID', default=None)):
        type, token = self.request.authorization
        if not token:
            if not config.local_disabled:
                from utilmeta import service
                if not service.production and str(self.request.ip_address) == service.host == '127.0.0.1':
                    # LOCAL -> LOCAL MANAGE
                    supervisor = SupervisorObject.init(Supervisor.objects.filter(
                        service=service.name,
                        node_id=node_id,
                        disabled=False,
                        local=True,
                        ops_api=config.ops_api,
                    ))
                    if not supervisor:
                        raise exceptions.Unauthorized
                    supervisor_var.setter(self.request, supervisor)
                    var.scopes.setter(self.request, ['*'])
                    return

            raise exceptions.Unauthorized
        node_id = node_id or self.request.query.get('node')
        # node can also be included in the query params to avoid additional headers
        if not node_id:
            raise exceptions.BadRequest('Node ID required', state='node_required')
        validated = False
        from utilmeta import service
        for supervisor in SupervisorObject.serialize(
            Supervisor.objects.filter(
                service=service.name,
                node_id=node_id,
                disabled=False,
                public_key__isnull=False
            )
        ):
            data = decode_token(token, public_key=supervisor.public_key)
            if not data:
                continue
            token_node_id = data.get('nid')
            if token_node_id != node_id:
                raise exceptions.Conflict(f'Invalid node id')
            issuer = data.get('iss') or ''
            if not str(supervisor.base_url).startswith(issuer):
                raise exceptions.Conflict(f'Invalid token issuer: {repr(issuer)}')
            audience = data.get('aud') or ''
            if not config.ops_api.startswith(audience):
                # todo: log, but not force to reject
                pass

            expires = data.get('exp')
            if not expires:
                raise exceptions.UnprocessableEntity('Invalid token: no expires')

            if self.request.time.timestamp() > expires:
                raise exceptions.BadRequest('Invalid token: expired', state='token_expired')

            # SCOPE ----------------------------
            scope = data.get('scope') or ''
            scopes = scope.split(' ') if ' ' in scope else scope.split(',')
            scope_names = []
            resources = []
            for name in scopes:
                if ':' in name:
                    name, resource = name.split(':')
                    resources.append(resource)
                scope_names.append(name)
            var.scopes.setter(self.request, scope_names)
            resources_var.setter(self.request, resources)
            # -------------------------------------

            token_id = data.get('jti') or ''
            if not token_id:
                raise exceptions.BadRequest('Invalid token: id required', state='token_expired')

            try:
                token_obj = AccessTokenSchema.init(
                    AccessToken.objects.filter(
                        token_id=token_id,
                        issuer_id=supervisor.id
                    )
                )
            except orm.EmptyQueryset:
                token_obj = None

            if token_obj:
                if token_obj.revoked:
                    # force revoked
                    # e.g. the subject permissions has changed after the token issued
                    raise exceptions.BadRequest('Invalid token: revoked', state='token_expired')
                token_obj.last_activity = self.request.time
                token_obj.used_times += 1
                token_obj.save()
            else:
                try:
                    token_obj = AccessTokenSchema(
                        token_id=token_id,
                        issuer_id=supervisor.id,
                        issued_at=datetime.fromtimestamp(data.get('iat')),
                        expiry_time=datetime.fromtimestamp(expires),
                        subject=data.get('sub'),
                        last_activity=self.request.time,
                        used_times=1,
                        ip=str(self.request.ip_address),
                        scope=scopes
                    )
                    token_obj.save()
                except utils.IntegrityError:
                    raise exceptions.BadRequest('Invalid token: id duplicated', state='token_expired')

            # set context vars
            # scope
            #
            supervisor_var.setter(self.request, supervisor)
            access_token_var.setter(self.request, token_obj)
            validated = True
            break

        if not validated:
            raise exceptions.BadRequest('Supervisor not found', state='supervisor_not_found')

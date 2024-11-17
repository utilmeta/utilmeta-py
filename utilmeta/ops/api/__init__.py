from utilmeta.core import api, orm, request, response
from ..schema import SupervisorData
from ..query import SupervisorPatch, AccessTokenSchema
from utilmeta.utils import exceptions, adapt_async, Error
from ..models import Supervisor, AccessToken
from .. import __spec_version__
from ..key import decode_token
from utilmeta.core.request import var
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import EmptyResultSet
from utype.types import *
from ..connect import save_supervisor
from .data import DataAPI
from .log import LogAPI
from .servers import ServersAPI
from .token import TokenAPI
from .utils import opsRequire, WrappedResponse, config, supervisor_var, \
    SupervisorObject, resources_var, access_token_var
from ..log import request_logger, Logger


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
    data: DataAPI
    logs: LogAPI
    token: TokenAPI

    # openapi: opsRequire('api.view')(
    #     OpenAPI.as_api(private=False, external_docs=config.external_openapi)
    # ) = api.route(
    #     alias=['openapi.json', 'openapi.yaml', 'openapi.yml'],
    # )

    response = WrappedResponse
    # @api.get
    # @opsRequire('api.view')
    # def openapi(self):
    #     from utilmeta import service
    #     openapi = OpenAPI(service)()

    @api.get
    @opsRequire('api.view')
    def openapi(self):
        return response.Response(config.openapi)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger: Logger = request_logger.getter(self.request)
        if logger:
            logger.make_events_only(True)

    # @orm.Atomic(config.db_alias)
    @adapt_async(close_conn=config.db_alias)
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

    @adapt_async(close_conn=config.db_alias)
    @opsRequire('service.config')
    def patch(self, data: SupervisorPatch = request.Body):
        supervisor: SupervisorObject = supervisor_var.getter(self.request)
        if not supervisor or not supervisor.id:
            raise exceptions.NotFound('Supervisor not found', state='supervisor_not_found')
        if supervisor.node_id != data.node_id:
            raise exceptions.BadRequest('Inconsistent supervisor node_id')
        data.id = supervisor.id
        # backup_urls
        # base_url
        # public_key
        # url
        # operation_timeout
        # heartbeat_interval
        # settings: dict
        # disabled: bool
        # # -- advanced
        # alert_settings: dict
        # task_settings: dict
        # aggregate_settings: dict
        data.save()
        return dict(
            node_id=data.node_id,
            **self.get()
        )

    @adapt_async(close_conn=config.db_alias)
    @opsRequire('service.delete')
    def delete(self):
        supervisor: SupervisorObject = supervisor_var.getter(self.request)
        if supervisor:
            if supervisor.init_key:
                # this supervisor is not marked as delete
                raise exceptions.BadRequest('Supervisor not marked as deleted', state='delete_failed')
            if supervisor.node_id:
                from utilmeta import service
                from utilmeta.ops import models
                for model in models.supervisor_related_models:
                    try:
                        model.objects.filter(
                            node_id=supervisor.node_id,
                        ).update(
                            node_id=None,
                            service=service.name
                        )
                    except EmptyResultSet:
                        continue
            if config.node_id:
                from utilmeta.bin.utils import update_meta_ini_file
                update_meta_ini_file(node=None)     # clear local node_id
            Supervisor.objects.filter(pk=supervisor.id).delete()
            return 1
        raise exceptions.NotFound('Supervisor not found', state='supervisor_not_found')

    @api.before('*', excludes=(get, post))
    def handle_token(self, node_id: str = request.HeaderParam('X-Node-ID', default=None)):
        type, token = self.request.authorization
        if not token:
            if not config.local_disabled:
                from utilmeta import service
                if not service.production and str(self.request.ip_address) == service.host == '127.0.0.1':
                    # LOCAL -> LOCAL MANAGE
                    try:
                        supervisor = SupervisorObject.init(Supervisor.objects.filter(
                            node_id=node_id,
                            disabled=False,
                            local=True,
                            ops_api=config.ops_api,
                        ))
                        supervisor_var.setter(self.request, supervisor)
                    except orm.EmptyQueryset:
                        supervisor_var.setter(self.request, SupervisorObject(
                            id=None,
                            service=service.name,
                            node_id=None,
                            disabled=False,
                            ident=None,
                            local=True,
                            ops_api=config.ops_api,
                        ))
                        pass
                        # raise exceptions.Unauthorized
                    var.scopes.setter(self.request, config.local_scope)
                    return

            raise exceptions.Unauthorized
        node_id = node_id or self.request.query.get('node')
        # node can also be included in the query params to avoid additional headers
        if not node_id:
            raise exceptions.BadRequest('Node ID required', state='node_required')
        validated = False
        for supervisor in SupervisorObject.serialize(
            Supervisor.objects.filter(
                node_id=node_id,
                # we don't use service name as identifier
                # that might not be synced
                disabled=False,
                public_key__isnull=False
            )
        ):
            try:
                token_data = decode_token(token, public_key=supervisor.public_key)
            except ValueError:
                raise exceptions.BadRequest('Invalid token format', state='token_expired')
            if not token_data:
                continue
            token_node_id = token_data.get('nid')
            if token_node_id != node_id:
                raise exceptions.Conflict(f'Invalid node id')
            issuer = token_data.get('iss') or ''
            if not str(supervisor.base_url).startswith(issuer):
                raise exceptions.Conflict(f'Invalid token issuer: {repr(issuer)}')
            audience = token_data.get('aud') or ''
            if not config.ops_api.startswith(audience):
                # todo: log, but not force to reject
                pass

            expires = token_data.get('exp')
            if not expires:
                raise exceptions.UnprocessableEntity('Invalid token: no expires')

            if self.request.time.timestamp() > expires:
                raise exceptions.BadRequest('Invalid token: expired', state='token_expired')

            # SCOPE ----------------------------
            scope = token_data.get('scope') or ''
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

            token_id = token_data.get('jti') or ''
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
                        issued_at=datetime.fromtimestamp(token_data.get('iat')),
                        expiry_time=datetime.fromtimestamp(expires),
                        subject=token_data.get('sub'),
                        last_activity=self.request.time,
                        used_times=1,
                        ip=str(self.request.ip_address),
                        scope=scopes
                    )
                    token_obj.save()
                except IntegrityError:
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

    @api.handle('*')
    def handle_errors(self, e: Error):
        if isinstance(e.exception, DatabaseError):
            # do not expose the state of database error
            e.exc = exceptions.ServerError('server error')
        return self.response(request=self.request, error=e)

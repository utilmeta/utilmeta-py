from utilmeta.core import api, orm, request, response, auth
from .schema import SupervisorData
from utilmeta.utils import exceptions
from .models import Supervisor, AccessToken
from . import __spec_version__
from .config import Operations
from .key import decode_token
from utilmeta.core.request import var
from django.db import models, utils
from utype.types import *


# excludes = var.RequestContextVar('_excludes', cached=True)
# params = var.RequestContextVar('_params', cached=True)
supervisor_var = var.RequestContextVar('_supervisor', cached=True)
resources_var = var.RequestContextVar('_scopes.resource', cached=True, default=list)

config = Operations.config()


class opsRequire(auth.Require):
    def validate_scopes(self, api_inst: api.API):
        if config.disabled_scope and config.disabled_scope.intersection(self.scopes):
            raise exceptions.PermissionDenied(f'Operation: {self.scopes} denied by config')
        return super().validate_scopes(api_inst)


class QueryAPI(api.API):
    supervisor: Supervisor = supervisor_var

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


class LogAPI(api.API):
    supervisor: Supervisor = supervisor_var

    @opsRequire('log.view')
    def get(self):
        pass

    @opsRequire('log.delete')
    def delete(self):
        pass


@opsRequire('metrics.view')
class MetricsAPI(api.API):
    supervisor: Supervisor = supervisor_var


class TokenAPI(api.API):
    supervisor: Supervisor = supervisor_var

    def get(self):
        pass

    @api.post
    @opsRequire('token.revoke')
    # this token will be generated and send directly from supervisor
    def revoke(self, id_list: List[str] = request.Body) -> int:
        exists = list(AccessToken.objects.filter(
            token_id__in=id_list,
            issuer=self.supervisor
        ).values_list('token_id', flat=True))

        for token_id in set(id_list).difference({exists}):
            AccessToken.objects.create(
                token_id=token_id,
                issuer=supervisor_var,
                expiry_time=self.request.time + timedelta(days=1),
                revoked=True
            )

        if exists:
            AccessToken.objects.filter(
                token_id__in=id_list,
                issuer=self.supervisor
            ).update(revoked=True)

        return len(exists)


class OperationsAPI(api.API):
    metrics: MetricsAPI
    query: QueryAPI
    log: LogAPI

    token: TokenAPI

    class response(response.Response):
        result_key = 'result'
        message_key = 'msg'
        state_key = 'state'
        count_key = 'count'

    @orm.Atomic(config.db_alias)
    def post(self, data: SupervisorData = request.Body):
        if data.init_key:
            # from command line
            obj: Supervisor = Supervisor.objects.filter(
                init_key=data.init_key,
                ops_api=data.ops_api
            ).first()
            if not obj or obj.disabled:
                raise exceptions.NotFound('Supervisor not found or disabled')
            if obj.base_url != data.base_url:
                raise exceptions.Conflict('Supervisor base_url conflicted')
            if Supervisor.objects.filter(
                base_url=data.base_url,
                node_id=data.node_id
            ).exists():
                raise exceptions.Conflict(f'Supervisor[{data.node_id}] at {data.base_url} already exists')
            Supervisor.objects.filter(id=obj.pk).update(
                ident=data.ident,
                node_id=data.node_id,
                public_key=data.public_key,
                backup_urls=data.backup_urls,
                connected=True
            )
            return self.get()
        else:
            # from api calling
            raise NotImplementedError

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
            raise exceptions.Unauthorized
        node_id = node_id or self.request.query.get('node')
        # node can also be included in the query params to avoid additional headers
        if not node_id:
            raise exceptions.BadRequest('Node ID required', state='node_required')
        validated = False
        from utilmeta import service
        for supervisor in Supervisor.objects.filter(
            service=service.name,
            node_id=node_id,
            disabled=False,
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
            for name in scope_names:
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

            token_obj: AccessToken = AccessToken.objects.filter(
                token_id=token_id,
                issuer=supervisor
            ).first()

            if token_obj:
                if token_obj.revoked:
                    # force revoked
                    # e.g. the subject permissions has changed after the token issued
                    raise exceptions.BadRequest('Invalid token: revoked', state='token_expired')
                token_obj.last_activity = self.request.time
                token_obj.used_times = models.F('used_times') + 1
                token_obj.save(update_fields=['last_activity', 'used_times'])
            else:
                try:
                    AccessToken.objects.create(
                        token_id=token_id,
                        issuer=supervisor,
                        issued_at=datetime.fromtimestamp(data.get('iat')),
                        expiry_time=datetime.fromtimestamp(expires),
                        subject=data.get('sub'),
                        last_activity=self.request.time,
                        used_times=1,
                        ip=str(self.request.ip_address),
                        scope=scopes
                    )
                except utils.IntegrityError:
                    raise exceptions.BadRequest('Invalid token: id duplicated', state='token_expired')

            # set context vars
            # scope
            #
            supervisor_var.setter(self.request, supervisor)
            validated = True
            break

        if not validated:
            raise exceptions.BadRequest('Supervisor not found', state='supervisor_not_found')

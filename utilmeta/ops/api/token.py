from utilmeta.core import api, request, orm
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire
from ..models import AccessToken
from utilmeta.utils import exceptions, adapt_async
from utype.types import *


class AccessTokenSchema(orm.Schema[AccessToken]):
    id: int
    issuer_id: int
    token_id: str
    issued_at: Optional[datetime]
    subject: Optional[str]
    expiry_time: Optional[datetime]
    # clear tokens beyond the expiry time

    # ACTIVITY -----------------
    last_activity: Optional[datetime]
    used_times: int
    ip: Optional[str]

    # PERMISSION ---------------
    scope: List[str]
    # excludes = models.JSONField(default=list)
    # readonly = models.BooleanField(default=False)
    # -------

    revoked: bool


class TokenAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    class AccessTokenQuery(orm.Query[AccessToken]):
        id: int
        issuer_id: int = orm.Filter(no_input=True)
        token_id: str
        subject: Optional[str]
        ip: Optional[str]
        revoked: bool

    @api.get
    @opsRequire('token.view')
    @adapt_async
    def get(self, query: AccessTokenQuery) -> List[AccessTokenSchema]:
        if not self.supervisor.id or not self.supervisor.node_id:
            raise exceptions.NotFound('Supervisor not found', state='supervisor_not_found')
        query.issuer_id = self.supervisor.id
        return AccessTokenSchema.serialize(
            query
        )

    @api.post
    @opsRequire('token.revoke')
    @adapt_async
    # this token will be generated and send directly from supervisor
    def revoke(self, id_list: List[str] = request.Body) -> int:
        if not self.supervisor.id or not self.supervisor.node_id:
            raise exceptions.NotFound('Supervisor not found', state='supervisor_not_found')
        exists = list(AccessToken.objects.filter(
            token_id__in=id_list,
            issuer_id=self.supervisor.id
        ).values_list('token_id', flat=True))

        for token_id in set(id_list).difference(exists):
            AccessToken.objects.create(
                token_id=token_id,
                issuer_id=self.supervisor.id,
                expiry_time=self.request.time + timedelta(days=1),
                revoked=True
            )

        if exists:
            AccessToken.objects.filter(
                token_id__in=id_list,
                issuer_id=self.supervisor.id
            ).update(revoked=True)

        return len(exists)

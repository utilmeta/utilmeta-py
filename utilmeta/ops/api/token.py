from utilmeta.core import api, request
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire
from ..models import AccessToken
from datetime import timedelta
from typing import List


class TokenAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

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

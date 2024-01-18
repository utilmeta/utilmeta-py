from .api import session_config
import utype
from typing import Optional
from utilmeta.core import api, request
import random
from datetime import timedelta


class EmailSessionSchema(session_config.schema):
    email: Optional[str] = utype.Field(default=None, defer_default=True)
    code: Optional[str] = utype.Field(default=None, defer_default=True)
    verified: bool = utype.Field(default=False, defer_default=True)


class EmailAPI(api.API):
    @api.post
    def send_code(self, session: EmailSessionSchema, email: str = request.BodyParam):
        session.email = email
        session.code = str(random.randint(1000, 9999))
        # send mail
        session.expiry = self.request.time + timedelta(seconds=300)

    @api.post
    def verify_code(self, session: EmailSessionSchema,
                    email: str = request.BodyParam,
                    code: str = request.BodyParam):
        if session.email == email and session.code == code:
            session.verified = True
            session.expiry = None
            return True
        return False

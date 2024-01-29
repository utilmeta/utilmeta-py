from utilmeta.core import api, orm, auth, request
from utilmeta.core.auth.session.db import DBSessionSchema, DBSession
from .models import Session, User
from .schema import LoginSchema, UserSchema
from utilmeta.utils import exceptions

USER_ID = '_user_id'


class SessionSchema(DBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(user_id=self.get(USER_ID))
        return data


session_config = DBSession(
    session_model=Session,
    engine=SessionSchema,
    cookie=DBSession.Cookie(
        name='sessionid',
        age=7 * 24 * 3600,
        http_only=True
    )
)

user_config = auth.User(
    User,
    authentication=session_config,
    key=USER_ID,
    login_fields=User.username,
    password_field=User.password,
)


@session_config.plugin
class UserAPI(api.API):
    @api.post
    def login(self, data: LoginSchema):
        user = user_config.login(
            request=self.request,
            ident=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('Username of password wrong')
        return UserSchema.init(user)

    @api.post
    def signup(self, data: LoginSchema):
        if User.objects.filter(username=data.username).exists():
            raise exceptions.BadRequest('Username exists')
        data.save()
        user_config.login_user(
            request=self.request,
            user=data.get_instance()
        )
        return UserSchema.init(data.pk)

    def get(self, user: User = user_config) -> UserSchema:
        return UserSchema.init(user)

    def put(self, data: UserSchema[orm.W], user: User = user_config):
        data.id = user.pk
        data.save()
        return UserSchema.init(data.pk)

    @api.post
    def logout(self, session: SessionSchema = session_config):
        session.flush()

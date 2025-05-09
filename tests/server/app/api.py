from utilmeta.core.api import API
from utilmeta.core import request, api, auth, orm
from utilmeta.core.auth.jwt import JsonWebToken
from utilmeta.core.auth.session.cached_db import CachedDBSession
from utype import Schema
from .models import User, Session
from .schema import UserBase
from utilmeta.utils import exceptions


class UserLogin(Schema):
    username: str
    password: str


session_config = CachedDBSession(
    session_model=Session,
    cache_alias='default',
    cookie=CachedDBSession.Cookie(
        name='sessionid',
        http_only=True,
    )
)


@session_config.plugin
class UserAPI(API):
    # sessionid: str = request.CookieParam(required=True)
    # csrftoken: str = request.CookieParam(default=None)

    jwt_user = auth.User(
        User,
        authentication=JsonWebToken(
            secret_key='TEST_JWT_SECRET_KEY',
            user_token_field=User.jwt_token
        ),
        login_fields=[User.username],
        password_field=User.password,
        login_ip_field=User.last_login_ip,
        login_time_field=User.last_login_time,
    )
    session_user = auth.User(
        User,
        authentication=session_config,
        login_fields=[User.username],
        password_field=User.password,
        login_ip_field=User.last_login_ip,
        login_time_field=User.last_login_time,
    )

    @api.post
    def jwt_login(self, data: UserLogin = request.Body) -> UserBase:
        user = self.jwt_user.login(
            self.request,
            ident=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('email or password wrong')
        return UserBase.init(user)

    @api.post
    def session_login(self, data: UserLogin = request.Body) -> UserBase:
        user = self.session_user.login(
            self.request,
            ident=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('email or password wrong')
        return UserBase.init(user)

    @api.post
    def session_logout(self, session: session_config.schema):
        session.flush()

    @api.get
    def user_by_jwt(self, user: User = jwt_user) -> UserBase:
        return UserBase.init(user)

    @api.get
    def user_by_session(self, user: User = session_user) -> UserBase:
        return UserBase.init(user)

    @api.patch
    def patch(self, data: UserBase[orm.WP], user: User = session_user) -> UserBase:
        data.id = user.pk
        data.save()
        return UserBase.init(data.id)

    # @api.get
    # async def test(self, using='postgresql'):
    #     from app.schema import ArticleSchema
    #     article = ArticleSchema[orm.A](
    #         title='My new async article 2',
    #         content='my async content',
    #         creatable_field='a',
    #         # test ignore on mode 'a'
    #         author_id=1,
    #         views=10
    #     )
    #     await article.asave(using=using)
    #     return await article.aget_instance(fresh=True, using=using)

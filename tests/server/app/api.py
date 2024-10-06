from utilmeta.core.api import API
from utilmeta.core import request, api, auth, orm
from utilmeta.core.auth.jwt import JsonWebToken
from utilmeta.core.auth.session.db import DBSession
from utype import Schema
from .models import User, Session
from .schema import UserBase
from utilmeta.utils import exceptions


class UserLogin(Schema):
    username: str
    password: str


session_config = DBSession(
    session_model=Session,
    cookie=DBSession.Cookie(
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

    @api.get
    def ts(self):
        pass

    @api.get
    async def test(self):
        # from .models import Follow
        # from server import service
        # db = Follow.objects.all().connections_cls.get(Follow.objects.all().db).get_adaptor(True).get_db()
        # await db.execute("PRAGMA foreign_keys = ON;")
        # dt = str(self.request.time)
        # await db.execute(f'INSERT into follow (target_id, user_id, follow_time) VALUES (-1, -1, "{dt}")')

        from app.schema import ArticleSchema
        from app.models import Article, BaseContent
        # article = ArticleSchema[orm.A](
        #     title='My new async article 1',
        #     content='my new async content',
        #     creatable_field='a',
        #     # test ignore on mode 'a'
        #     author_id=1,
        #     views=10
        # )
        # assert article.creatable_field == 'a'
        # assert article.slug == 'my-new-async-article-1'
        # await article.asave()

        # obj = await BaseContent.objects.acreate(
        #     content='my new async content',
        #     type='article',
        #     author_id=1,
        # )
        article = await Article.objects.acreate(
            content='my new async content',
            type='article',
            author_id=1,
            title='My new async article 1',
            slug='my-new-async-article-1',
            views=10
        )
        # from asgiref.sync import sync_to_async
        # await sync_to_async(article.save_base)(raw=True)
        return article.pk
        # from utilmeta.core.orm.compiler import TransactionWrapper
        # from utilmeta.core.orm import DatabaseConnections
        # db = DatabaseConnections.get('default')
        # import sqlite3
        #
        # from app.models import Follow, User
        # from utype.types import datetime, List
        #
        # class FollowSchema(orm.Schema[Follow]):
        #     id: int
        #     user_id: int
        #     target_id: int
        #     follow_time: datetime
        #
        # class UserSchema(orm.Schema[User]):
        #     id: int
        #     username: str
        #     followings: List[int] = orm.Field(mode='raw', default=None, defer_default=True)
        #     user_followings: List[FollowSchema] = orm.Field(mode='rwa', default=None, defer_default=True)

        # wrapper = TransactionWrapper(UserSchema.__parser__.model, transaction=True)
        # await wrapper.__aenter__()
        # async with TransactionWrapper(UserSchema.__parser__.model, transaction=True) as t:
        # async with orm.Atomic('default'):
        # import aiosqlite
        #
        # async with aiosqlite.connect('sqlite//:memory') as database:
        #     await database.execute("PRAGMA foreign_keys = ON;")
        #
        #     async with database.transaction():
        #         try:
        #             await database.execute(
        #                 "INSERT INTO follow (user_id, target_id, follow_time) VALUES (1, 0, ?)",
        #                 (user_id, target_id, follow_time)
        #             )
        #         except aiosqlite.IntegrityError as e:
        #             print(f"Integrity error: {e}")

        # aiosqlite.IntegrityError
        # try:
        #     obj = await User.objects.acreate(
        #         username='async new user 3',
        #     )
        #     await Follow.objects.acreate(
        #         user=obj,
        #         target_id=0
        #     )
        #     print('HERE I AM')
        # except Exception as e:
        #     await wrapper.rollback()
        # else:
        #     try:
        #         await wrapper.commit()
        #     except Exception:
        #         await wrapper.rollback()
            # raise sqlite3.IntegrityError
        # user3 = UserSchema[orm.A](
        #     username='async new user 3',
        #     user_followings=[{'target_id': 0}]
        # )
        # await user3.asave(transaction=True, with_relations=True)

        # from asgiref.sync import sync_to_async
        # await sync_to_async(article.save_base)(raw=True)
        # await article.adelete()
        # await obj.adelete()

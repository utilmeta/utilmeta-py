import pytest
from tests.conftest import setup_service
from utilmeta.core import orm
from utilmeta.utils import exceptions, time_now
from datetime import datetime
from typing import List, Optional
from utype.types import Self


setup_service(__name__, async_param=[True])

INVALID_ID = 2147483647


class TestSchemaQuery:
    def test_serialize_users(self, service, db_using):
        from app.schema import UserSchema, UserQuery
        res = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "within_days": 1,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
            }).get_queryset(using=db_using),
        )
        assert len(res) == 2
        assert res[0]["username"] == "alice"
        assert res[0]["followers_num"] == 2
        assert set(res[0].follower_names) == {'bob', 'jack'}
        assert res[0].follower_rep.username == 'bob'
        assert res[0]["followings_num"] == 1
        assert set(res[0]["liked_slugs"]) == {"about-tech", "big-shot"}
        assert res[0]["@views"] == 103
        # assert "content" not in res[0].articles[0]  # read auth login=True not satisfied
        # assert "comments" not in res[0].articles[0]  # discard=True
        assert len(res[0].top_2_articles) == 1
        assert res[0].top_2_articles[0].author_tag["name"] == "alice"

        assert res[1]["username"] == "bob"
        # assert len(res[1]["liked_author_followers"]) == 4
        assert res[1]["followers_num"] == 2
        assert res[1]["followings_num"] == 2
        assert set(res[1]["liked_slugs"]) == {"about-tech", "this-is-a-huge-one"}
        assert res[1]["@views"] == 13
        assert len(res[1].top_2_articles) == 2
        assert res[1].top_2_articles[0].views == 10   # -views

        assert len(res[1].top_2_likes_articles) == 2
        assert res[1].top_2_likes_articles[0].liked_bys_num == 3  # -views
        assert res[1].top_2_likes_articles[0].id == 1
        assert res[1].top_2_likes_articles[1].liked_bys_num == 2

        assert res[1].top_article.id == 1
        assert res[1].top_article.liked_bys_num == 3

        assert len(res[1].top_articles) == 2
        assert res[1].top_articles[0].views == 10

        assert res[1].articles_num == 3
        assert len(res[1].articles) == 3

        # -- test one with no article
        sup = UserSchema.init(5)
        assert len(sup.articles) == 0
        assert sup.articles_num == 0
        assert sup.follower_names == []
        assert sup.follower_rep is None

    def test_scope_and_excludes(self, service, db_using):
        from app.schema import UserSchema, UserQuery
        res1 = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
                "scope": ['username', '@views']
            }), context=orm.QueryContext(using=db_using)
        )
        assert set(res1[0]) == {'username', '@views'}
        assert res1[0].sum_views == 103

        res2 = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
                "exclude": ['username', 'followers_num', 'liked_slug']
            }), context=orm.QueryContext(using=db_using)
        )
        assert 'username' not in res2[0]
        assert 'followers_num' not in res2[0]
        assert 'liked_slug' not in res2[0]
        assert res1[0].sum_views == 103

    def test_init_articles(self, service, db_using):
        from app.schema import ArticleSchema, ContentBase
        article = ArticleSchema.init(1, context=orm.QueryContext(using=db_using))
        assert article.id == article.pk == 1
        assert article.liked_bys_num == 3
        assert article.comments_num == 2
        assert article.author.username == 'bob'
        assert article.author.followers_num == 2
        assert article.author_articles_views == 13
        assert article.author_avg_articles_views == 6.5
        assert len(article.comments) == 2
        assert article.comments[0].id > article.comments[1].id
        # comments: List[CommentSchema] = orm.Field(
        #     Comment.objects.order_by('-id'),
        # )
        assert article.author_tag['name'] == 'bob'
        assert db_using in article.tags

        # test sub relation
        content = ContentBase.init(1, context=orm.QueryContext(using=db_using))
        assert content.id == 1
        assert content.article.id == 1

    def test_related_qs(self, service, db_using):
        from app.schema import UserBase, ArticleSchema
        from app.models import Article, User
        from typing import List, Optional
        from utilmeta.core import orm
        from django.db import models

        class UserSchema(UserBase):
            top_article_slug: Optional[str] = orm.Field(
                Article.objects.filter(
                    author_id=models.OuterRef('pk')
                ).order_by('-views').values('slug')[:1]
            )

            top_article: Optional[ArticleSchema] = orm.Field(
                Article.objects.filter(
                    author_id=models.OuterRef('pk')
                ).order_by('-views')[:1]
            )

            top_2_articles: List[ArticleSchema] = orm.Field(
                lambda user_id: Article.objects.filter(
                    author_id=user_id
                ).order_by('-views')[:2]
            )

            @classmethod
            def get_runtime_schema(cls, user_id):
                def get_followers_you_known(*pks):
                    mp = {}
                    for val in User.objects.filter(
                        followings__in=pks,
                        followers=user_id
                    ).values('followings', 'pk').using(db_using):
                        mp.setdefault(val['followings'], []).append(val['pk'])
                    return mp

                class user_schema(cls):
                    followers_you_known: List[cls] = orm.Field(
                        get_followers_you_known
                    )

                return user_schema

        res = UserSchema.init(2, context=orm.QueryContext(using=db_using))
        assert res.top_article.views == 10
        assert res.top_article_slug == res.top_article.slug == 'big-shot'
        assert len(res.top_2_articles) == 2
        assert res.top_2_articles[0].id == 1

        user = UserSchema.get_runtime_schema(2).init(1, context=orm.QueryContext(using=db_using))
        assert len(user.followers_you_known) == 1
        assert user.followers_you_known[0].username == 'jack'
        assert user.followers_you_known[0].followers_num == 1

    def test_queryset_generator(self, service, db_using):
        from app.models import Article
        from app.schema import ArticleQuery
        from django.db import models
        dup_qs = Article.objects.filter(models.Q(liked_bys__in=[1, 2, 3]) | models.Q(author__in=[1, 2, 3]) | models.Q(
            author__followers__in=[1, 2, 3]), pk__lte=5)

        query = ArticleQuery(limit=10)
        assert query.count(dup_qs, using=db_using) == 4
        assert query.get_queryset(dup_qs, using=db_using).count() == 4

    @pytest.mark.asyncio
    async def test_async_queryset_generator(self, service, db_using):
        from app.models import Article
        from app.schema import ArticleQuery
        from django.db import models
        dup_qs = Article.objects.filter(models.Q(liked_bys__in=[1, 2, 3]) | models.Q(author__in=[1, 2, 3]) | models.Q(
            author__followers__in=[1, 2, 3]), pk__lte=5)

        query = ArticleQuery(limit=10)
        assert await query.acount(dup_qs, using=db_using) == 4
        assert await query.get_queryset(dup_qs, using=db_using).acount() == 4

    @classmethod
    async def refresh_db(cls, using):
        db = orm.DatabaseConnections.get(using)
        db.get_adaptor(asynchronous=True)._db = None
        await db.connect()

    @pytest.mark.asyncio
    async def test_async_init_users(self, service, db_using):
        await self.refresh_db(db_using)
        from app.schema import UserSchema
        from app.models import User
        user = await UserSchema.ainit(
            User.objects.filter(
                username='alice',
            ).using(db_using),
        )
        assert user.pk == 1
        assert user.followers_num == 2
        assert user.sum_views == 103
        assert user.top_2_articles[0].author_tag["name"] == "alice"
        assert user.top_2_articles[0].views == 103
        assert set(user.follower_names) == {'bob', 'jack'}

        # --------------
        bob = await UserSchema.ainit(
            User.objects.filter(
                username='bob',
            ).using(db_using),
        )
        assert bob.pk == 2
        assert len(bob.articles) == 3
        assert bob.articles_num == 3

        assert len(bob.top_2_likes_articles) == 2
        assert bob.top_2_likes_articles[0].liked_bys_num == 3
        assert bob.top_2_likes_articles[0].id == 1
        assert bob.top_2_likes_articles[1].liked_bys_num == 2

        assert bob.top_article.id == 1
        assert bob.top_article.liked_bys_num == 3

        assert len(bob.top_articles) == 2
        assert bob.top_articles[0].views == 10

        assert bob.articles_num == 3
        assert len(bob.articles) == 3

        # ---
        sup = UserSchema.init(5, context=orm.QueryContext(using=db_using))
        assert len(sup.articles) == 0
        assert sup.articles_num == 0
        assert sup.follower_names == []

    @pytest.mark.asyncio
    async def test_async_init_users_with_sync_query(self, service, db_using):
        await self.refresh_db(db_using)
        # for django, it requires bind_service=True in @awaitable
        from app.schema import UserSchema
        from app.models import User
        user = UserSchema.init(
            User.objects.filter(
                username='alice',
            ).using(db_using)
        )
        assert user.pk == 1
        assert user.followers_num == 2
        assert user.sum_views == 103
        assert user.top_2_articles[0].author_tag["name"] == "alice"
        assert user.top_2_articles[0].views == 103

    @pytest.mark.asyncio
    async def test_async_serialize_articles(self, service, db_using):
        await self.refresh_db(db_using)
        from app.schema import ArticleSchema
        from app.models import Article
        articles = await ArticleSchema.aserialize(
            [1, 2], context=orm.QueryContext(using=db_using)
        )
        assert len(articles) == 2
        assert {a.pk for a in articles} == {1, 2}
        articles = await ArticleSchema.aserialize(
            Article.objects.filter(
                slug='big-shot'
            ).using(db_using)
        )
        assert len(articles) == 1
        assert articles[0].pk == 1
        assert articles[0].author_avg_articles_views == 6.5
        assert articles[0].author.followers_num == 2
        assert db_using in articles[0].tags

    def test_save(self, service, db_using):
        from app.schema import ArticleSchema
        from app.models import Article
        article = ArticleSchema[orm.A](
            title='My new article 1',
            content='my content',
            creatable_field='a',
            # test ignore on mode 'a'
            author_id=1,
            views=10
        )
        assert article.creatable_field == 'a'
        assert article.slug == 'my-new-article-1'
        t = time_now()
        article.save(using=db_using)
        t1 = time_now()
        inst = article.get_instance(fresh=True, using=db_using)
        assert t1 > inst.created_at > t
        assert t1 > inst.updated_at > t
        article.content = 'my new content'
        article.save(using=db_using)  # test save on mode 'a' with pk (should update instead of create)

        # inst = article.get_instance(fresh=True)
        # t2 = time_now()
        # assert t2 > inst.updated_at > t1

        with pytest.raises(exceptions.BadRequest):
            article.save(must_create=True, using=db_using)

        inst: Article = article.get_instance(fresh=True, using=db_using)
        assert inst.slug == 'my-new-article-1'
        assert inst.content == 'my new content'
        assert inst.author.id == 1
        assert inst.author.username == 'alice'

        with pytest.raises(exceptions.BadRequest):
            ArticleSchema[orm.A](
                title='My new article 1',
                content='my new content',
                creatable_field='a',
                author_id=1,
                views=10
            ).save(using=db_using)
            # save again (with must_create=True by default) will raise IntegrityError, and re-throw as BadRequest

        article.slug = 'my-new-article'
        article.save(must_update=True, using=db_using)
        inst2: Article = article.get_instance(fresh=True, using=db_using)
        assert inst2.slug == 'my-new-article'

        article2 = ArticleSchema[orm.W](
            title='My new article 2',
            content='my new content 2',
            writable_field='w',
            # test ignore on mode 'a'
        )
        with pytest.raises(orm.MissingPrimaryKey):
            article2.save(must_update=True, using=db_using)

        assert article2.updated_at > t1
        # article.pk = None
        # article.save(must_create=True)
        # assert inst.pk != article.pk

    @pytest.mark.asyncio
    async def test_async_save(self, service, db_using):
        await self.refresh_db(db_using)
        from app.schema import ArticleSchema
        from app.models import Article
        article = ArticleSchema[orm.A](
            title='My new async article 1',
            content='my async content',
            creatable_field='a',
            # test ignore on mode 'a'
            author_id=1,
            views=10
        )
        assert article.creatable_field == 'a'
        assert article.slug == 'my-new-async-article-1'
        await article.asave(using=db_using)

        article.content = 'my new async content'
        await article.asave(using=db_using)  # test save on mode 'a' with pk (should update instead of create)

        with pytest.raises(exceptions.BadRequest):
            await article.asave(must_create=True, using=db_using)

        # SQL: INSERT INTO "article" ("basecontent_ptr_id", "title",
        # "description", "slug", "views") VALUES (%s, %s, %s, %s, %s) (193,
        # 'My new async article 1', '', 'my-new-async-article-1', 10)
        # >       for idx, rec in enumerate(cursor_description):
        # E       TypeError: 'NoneType' object is not iterable

        inst: Article = await article.aget_instance(fresh=True, using=db_using)
        assert inst.slug == 'my-new-async-article-1'
        assert inst.content == 'my new async content'
        assert inst.author_id == 1

        with pytest.raises(exceptions.BadRequest):
            await ArticleSchema[orm.A](
                title='My new async article 1',
                content='my new async content',
                creatable_field='a',
                author_id=1,
                views=10
            ).asave(using=db_using)
            # save again (with must_save=True by default) will raise IntegrityError, and re-throw as BadRequest

        article.slug = 'my-new-async-article'
        await article.asave(must_update=True, using=db_using)
        inst2: Article = await article.aget_instance(fresh=True, using=db_using)
        assert inst2.slug == 'my-new-async-article'

        article2 = ArticleSchema[orm.W](
            title='My new async article 2',
            content='my new async content 2',
            writable_field='w',
            # test ignore on mode 'a'
        )
        with pytest.raises(orm.MissingPrimaryKey):
            await article2.asave(must_update=True, using=db_using)

    def test_save_with_relations(self, service, db_using):
        from app.models import Article, User, Follow, BaseContent, Comment

        class FollowSchema(orm.Schema[Follow]):
            id: int
            user_id: int
            target_id: int
            follow_time: datetime

        class UserSchema(orm.Schema[User]):
            id: int
            username: str
            followings: List[int] = orm.Field(mode='raw', default=None, defer_default=True)
            user_followings: List[FollowSchema] = orm.Field(mode='rwa', default=None, defer_default=True)

        user1 = UserSchema[orm.A](
            username='new user 1',
            followings=[1, 2]
        )
        user1.save(using=db_using)
        # test default with_relations=True
        user1_inst: User = user1.get_instance(fresh=True, using=db_using)
        assert user1_inst.username == 'new user 1'
        assert set(Follow.objects.filter(user_id=user1.pk).using(db_using).values_list('target_id', flat=True)) == {1, 2}

        user1 = UserSchema.init(user1_inst, context=orm.QueryContext(using=db_using))
        following_objs = list(user1.user_followings)
        following_objs.sort(key=lambda x: x.target_id)
        following_objs.pop(0)
        following_objs.append({'target_id': 3})

        # ----
        user2 = UserSchema[orm.A](
            username='new user 2',
            followings=[INVALID_ID, 2]
        )
        with pytest.raises(exceptions.BadRequest):
            user2.save(with_relations=True, transaction=True, using=db_using)
        assert not User.objects.filter(username='new user 2').using(db_using).exists()

        user_update1 = UserSchema[orm.W](
            id=user1.pk,
            username='new user 2',
            user_followings=following_objs,
        )
        user_update1.save(with_relations=True, using=db_using)
        user1_inst: User = user1.get_instance(fresh=True, using=db_using)
        assert user1_inst.username == 'new user 2'
        assert set(Follow.objects.filter(user_id=user1.pk).using(db_using).values_list('target_id', flat=True)) == {2, 3}

        # test with_relations=False
        user_update2 = UserSchema[orm.W](
            id=user1.pk,
            username='new user 2',
            user_followings=[]
        )
        user_update2.save(with_relations=False, using=db_using)
        assert set(Follow.objects.filter(user_id=user1.pk).using(db_using).values_list('target_id', flat=True)) == {2, 3}

        # test ignore relational errors
        following_objs.pop(0)
        following_objs.append({'target_id': INVALID_ID})
        user3 = UserSchema[orm.A](
            username='new user 3',
            user_followings=following_objs,
        )
        # 1. test transaction
        with pytest.raises(exceptions.BadRequest):
            user3.save(with_relations=True, transaction=True, using=db_using)
        assert not User.objects.filter(username='new user 3').using(db_using).exists()

        # 2. test ignore_relation_errors=True
        user3.save(with_relations=True, transaction=False, ignore_relation_errors=True, using=db_using)
        user3_inst: User = user3.get_instance(fresh=True, using=db_using)
        assert user3_inst.username == 'new user 3'
        assert set(Follow.objects.filter(user_id=user3.pk).using(db_using).values_list('target_id', flat=True)) == {3}

        class BaseContentSchema(orm.Schema[BaseContent]):
            id: int
            content: str
            type: str
            author: UserSchema
            author_id: int = orm.Field(mode='ra')
            liked_bys: List[int] = orm.Field(required=False, mode='raw')
            created_at: datetime

        class CommentData(orm.Schema[Comment]):
            on_content_id: int

        class ArticleData(orm.Schema[Article]):
            title: str
            slug: str

        class CommentSchema(BaseContentSchema[Comment]):
            on_content_id: int
            type: str = orm.Field(mode='r', default='comment')
            comments: List[Self] = orm.Field(mode='rwa')
            # nested multi-layer comments update

        class ContentSchema(BaseContentSchema):
            comments: List[CommentSchema] = orm.Field(mode='rwa')

            comment: Optional[CommentData] = orm.Field(mode='raw', default=None, defer_default=True)
            article: Optional[ArticleData] = orm.Field(mode='raw', default=None, defer_default=True)
        # test transaction=True

        content = ContentSchema[orm.A](
            type='comment',
            content='my comment 1',
            author_id=2,
            liked_bys=[1, 3],
            comment=dict(on_content_id=3),
            comments=[
                dict(author_id=1, content='cm1'),
                dict(
                    author_id=2, content='cm2',
                    comments=[
                        dict(author_id=3, content='cm3'),
                        dict(
                            author_id=4, content='cm4'
                        ),
                    ]
                ),
            ]
        )
        content.save(with_relations=True, transaction=True, using=db_using)
        comment: Comment = Comment.objects.filter(pk=content.pk).using(db_using).first()
        assert comment.on_content.pk == 3
        assert comment.author.pk == 2
        assert comment.content == 'my comment 1'
        assert set(comment.liked_bys.values_list('id', flat=True).using(db_using)) == {1, 3}
        assert set(Comment.objects.filter(
            on_content=comment).values_list('content', flat=True).using(db_using)) == {'cm1', 'cm2'}

        # test nested content creations
        assert set(Comment.objects.filter(
            on_content__content='cm2').values_list('content', flat=True).using(db_using)) == {'cm3', 'cm4'}

        # fixme: transaction won't work in bind_service (will cause the db hang)
        # fixme: OneToOneRel with primary_key: cannot set?

    # todo: add one-to-one-rel key

    @pytest.mark.asyncio
    async def test_async_save_with_relations(self, service, db_using):
        await self.refresh_db(db_using)
        from app.models import Article, User, Follow, BaseContent, Comment

        class FollowSchema(orm.Schema[Follow]):
            id: int
            user_id: int
            target_id: int
            follow_time: datetime

        class UserSchema(orm.Schema[User]):
            id: int
            username: str
            followings: List[int] = orm.Field(mode='raw', default=None, defer_default=True)
            user_followings: List[FollowSchema] = orm.Field(mode='rwa', default=None, defer_default=True)

        user1 = UserSchema[orm.A](
            username='async new user 1',
            followings=[1, 2]
        )
        await user1.asave(using=db_using)
        # test default with_relations=True

        user1_inst: User = await user1.aget_instance(fresh=True, using=db_using)
        assert user1_inst.username == 'async new user 1'
        assert {v async for v in Follow.objects.filter(user_id=user1.pk).using(db_using).values_list('target_id', flat=True)} == {1, 2}

        # -------------
        user2 = UserSchema[orm.A](
            username='new async user 2',
            followings=[INVALID_ID, 2]
        )
        with pytest.raises(exceptions.BadRequest):
            await user2.asave(with_relations=True, transaction=True, using=db_using)
        assert not await User.objects.filter(username='new async user 2').using(db_using).aexists()
        # ------------------

        user1 = await UserSchema.ainit(user1_inst, context=orm.QueryContext(using=db_using))
        following_objs = list(user1.user_followings)
        following_objs.sort(key=lambda x: x.target_id)
        following_objs.pop(0)
        following_objs.append({'target_id': 3})

        user_update1 = UserSchema[orm.W](
            id=user1.pk,
            username='async new user 2',
            user_followings=following_objs,
        )
        await user_update1.asave(with_relations=True, using=db_using)
        user1_inst: User = await user1.aget_instance(fresh=True, using=db_using)
        assert user1_inst.username == 'async new user 2'
        assert {v async for v in Follow.objects.filter(
            user_id=user1.pk).using(db_using).values_list('target_id', flat=True)} == {2, 3}

        # test with_relations=False
        user_update2 = UserSchema[orm.W](
            id=user1.pk,
            username='async new user 2',
            user_followings=[]
        )
        await user_update2.asave(with_relations=False, using=db_using)
        assert {v async for v in Follow.objects.filter(
            user_id=user1.pk).using(db_using).values_list('target_id', flat=True)} == {2, 3}

        # test ignore relational errors
        following_objs.pop(0)
        following_objs.append({'target_id': INVALID_ID})
        user3 = UserSchema[orm.A](
            username='async new user 3',
            user_followings=following_objs,
        )
        # # 1. test transaction
        with pytest.raises(exceptions.BadRequest):
            await user3.asave(with_relations=True, transaction=True, using=db_using)
        assert not await User.objects.filter(username='async new user 3').using(db_using).aexists()

        # 2. test ignore_relation_errors=True
        await user3.asave(with_relations=True, transaction=False, ignore_relation_errors=True, using=db_using)
        user3_inst: User = await user3.aget_instance(fresh=True, using=db_using)
        assert user3_inst.username == 'async new user 3'
        assert {v async for v in Follow.objects.filter(
            user_id=user3.pk).using(db_using).values_list('target_id', flat=True)} == {3}

        class BaseContentSchema(orm.Schema[BaseContent]):
            id: int
            content: str
            type: str
            author: UserSchema
            author_id: int = orm.Field(mode='ra')
            liked_bys: List[int] = orm.Field(required=False, mode='raw')
            created_at: datetime

        class CommentData(orm.Schema[Comment]):
            on_content_id: int

        class ArticleData(orm.Schema[Article]):
            title: str
            slug: str

        class CommentSchema(BaseContentSchema[Comment]):
            on_content_id: int
            type: str = orm.Field(mode='r', default='comment')
            comments: List[Self] = orm.Field(mode='rwa')

        class ContentSchema(BaseContentSchema):
            comments: List[CommentSchema] = orm.Field(mode='rwa')

            comment: Optional[CommentData] = orm.Field(mode='raw', default=None)
            article: Optional[ArticleData] = orm.Field(mode='raw', default=None)

        # test transaction=True

        content = ContentSchema[orm.A](
            type='comment',
            content='my comment 1',
            author_id=2,
            liked_bys=[1, 3],
            comment=dict(on_content_id=3),
            comments=[
                dict(author_id=1, content='cm1'),
                dict(
                    author_id=2, content='cm2',
                    comments=[
                        dict(author_id=3, content='cm3'),
                        dict(
                            author_id=4, content='cm4'
                        ),
                    ]
                ),
            ]
        )
        await content.asave(with_relations=True, transaction=True, using=db_using)
        comment: Comment = await Comment.objects.filter(pk=content.pk).using(db_using).afirst()
        assert comment.on_content_id == 3
        assert comment.author_id == 2
        assert comment.content == 'my comment 1'
        assert {v async for v in Comment.objects.filter(
            on_content=comment).using(db_using).values_list('content', flat=True)} == {'cm1', 'cm2'}
        # test nested content creations
        assert {v async for v in Comment.objects.filter(
            on_content__content='cm2').values_list('content', flat=True).using(db_using)} == {'cm3', 'cm4'}

        c = await ContentSchema.ainit(content.pk, context=orm.QueryContext(using=db_using))
        assert set(c.liked_bys) == {1, 3}

    def test_handle_recursion(self, db_using):
        from app.models import Follow, User
        from utype.types import Self
        from django.db.utils import IntegrityError

        try:
            Follow(target_id=1, user_id=1).save(using=db_using)
            # self-following
        except IntegrityError:
            # ignore
            pass

        class UserFollowerRecursion(orm.Schema[User]):
            id: int
            username: str
            followers: List[Self]
            followings: List[Self]

        user1 = UserFollowerRecursion.init(1, context=orm.QueryContext(using=db_using))
        # infinite recursion will exceed the memory and cause this process to exit
        assert user1.id == 1
        assert any([follower.id == 1 for follower in user1.followers])
        assert any([following.id == 1 for following in user1.followings])

    def test_bulk_save(self):
        pass

    @pytest.mark.asyncio
    async def test_async_bulk_save(self):
        pass

    def test_commit(self):
        pass

    @pytest.mark.asyncio
    async def test_async_commit(self):
        pass

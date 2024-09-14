import pytest
from tests.conftest import setup_service

setup_service(__name__, async_param=False)


class TestSchemaQuery:
    def test_serialize_users(self, service):
        from app.schema import UserSchema, UserQuery
        res = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "within_days": 1,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
            }).get_queryset(),
        )
        assert len(res) == 2
        assert res[0]["username"] == "alice"
        assert res[0]["followers_num"] == 2
        assert set(res[0].follower_names) == {'bob', 'jack'}
        assert res[0].follower_rep.username == 'bob'
        assert res[0]["followings_num"] == 1
        assert set(res[0]["liked_slugs"]) == {"about-tech", "some-news", "big-shot"}
        assert res[0]["@views"] == 103
        # assert "content" not in res[0].articles[0]  # read auth login=True not satisfied
        # assert "comments" not in res[0].articles[0]  # discard=True
        assert len(res[0].top_articles) == 1
        assert res[0].top_articles[0].author_tag["name"] == "alice"

        assert res[1]["username"] == "bob"
        # assert len(res[1]["liked_author_followers"]) == 4
        assert res[1]["followers_num"] == 2
        assert res[1]["followings_num"] == 2
        assert set(res[1]["liked_slugs"]) == {"about-tech", "this-is-a-huge-one"}
        assert res[1]["@views"] == 13
        assert len(res[1].top_articles) == 2
        assert res[1].top_articles[0].views == 10   # -views
        assert res[1].articles_num == 3
        assert len(res[1].articles) == 3

        # -- test one with no article
        sup = UserSchema.init(5)
        assert len(sup.articles) == 0
        assert sup.articles_num == 0
        assert sup.follower_names == []
        assert sup.follower_rep is None

    def test_scope_and_excludes(self):
        from app.schema import UserSchema, UserQuery
        res1 = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
                "scope": ['username', '@views']
            })
        )
        assert set(res1[0]) == {'username', '@views'}
        assert res1[0].sum_views == 103

        res2 = UserSchema.serialize(
            UserQuery({
                "followers_num>=": 2,
                "@page": 1,
                "order": ["-followers_num", "-views_num"],
                "exclude": ['username', 'followers_num', 'liked_slug']
            })
        )
        assert 'username' not in res2[0]
        assert 'followers_num' not in res2[0]
        assert 'liked_slug' not in res2[0]
        assert res1[0].sum_views == 103

    def test_init_articles(self, service):
        from app.schema import ArticleSchema, ContentBase
        article = ArticleSchema.init(1)
        assert article.id == article.pk == 1
        assert article.liked_bys_num == 3
        assert article.comments_num == 2
        assert article.author.username == 'bob'
        assert article.author.followers_num == 2
        assert article.author_articles_views == 13
        assert article.author_avg_articles_views == 6.5
        assert len(article.comments) == 2
        assert article.author_tag['name'] == 'bob'

        # test sub relation
        content = ContentBase.init(1)
        assert content.id == 1
        assert content.article.id == 1

    def test_related_qs(self):
        from app.schema import UserBase, ArticleSchema
        from app.models import Article, User
        from typing import List, Optional
        from utilmeta.core import orm
        from django.db import models

        class UserSchema(UserBase):
            top_article_slug: Optional[str] = orm.Field(
                Article.objects.filter(
                    author_id=models.OuterRef('pk')
                ).order_by('-views').values('slug')
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
                    ).values('followings', 'pk'):
                        mp.setdefault(val['followings'], []).append(val['pk'])
                    return mp

                class user_schema(cls):
                    followers_you_known: List[cls] = orm.Field(
                        get_followers_you_known
                    )

                return user_schema

        res = UserSchema.init(2)
        assert res.top_article.views == 10
        assert res.top_article_slug == res.top_article.slug == 'big-shot'
        assert len(res.top_2_articles) == 2
        assert res.top_2_articles[0].id == 1

        user = UserSchema.get_runtime_schema(2).init(1)
        assert len(user.followers_you_known) == 1
        assert user.followers_you_known[0].username == 'jack'
        assert user.followers_you_known[0].followers_num == 1

    @pytest.mark.asyncio
    async def test_async_init_users(self):
        from app.schema import UserSchema
        from app.models import User
        user = await UserSchema.ainit(
            User.objects.filter(
                username='alice',
            )
        )
        assert user.pk == 1
        assert user.followers_num == 2
        assert user.sum_views == 103
        assert user.top_articles[0].author_tag["name"] == "alice"
        assert user.top_articles[0].views == 103
        assert set(user.follower_names) == {'bob', 'jack'}

        # --------------
        bob = await UserSchema.ainit(
            User.objects.filter(
                username='bob',
            )
        )
        assert bob.pk == 2
        assert len(bob.articles) == 3
        assert bob.articles_num == 3

        # ---
        sup = UserSchema.init(5)
        assert len(sup.articles) == 0
        assert sup.articles_num == 0
        assert sup.follower_names == []

    @pytest.mark.asyncio
    async def test_async_init_users_with_sync_query(self):
        # for django, it requires bind_service=True in @awaitable
        from app.schema import UserSchema
        from app.models import User
        user = UserSchema.init(
            User.objects.filter(
                username='alice',
            )
        )
        assert user.pk == 1
        assert user.followers_num == 2
        assert user.sum_views == 103
        assert user.top_articles[0].author_tag["name"] == "alice"
        assert user.top_articles[0].views == 103

    @pytest.mark.asyncio
    async def test_async_serialize_articles(self):
        from app.schema import ArticleSchema
        from app.models import Article
        articles = await ArticleSchema.aserialize(
            [1, 2]
        )
        assert len(articles) == 2
        assert {a.pk for a in articles} == {1, 2}
        articles = await ArticleSchema.aserialize(
            Article.objects.filter(
                slug='big-shot'
            )
        )
        assert len(articles) == 1
        assert articles[0].pk == 1
        assert articles[0].author_avg_articles_views == 6.5
        assert articles[0].author.followers_num == 2

    def test_commit(self):
        pass

    @pytest.mark.asyncio
    async def test_async_commit(self):
        pass

    def test_save(self):
        pass

    @pytest.mark.asyncio
    async def test_async_save(self):
        pass

    @pytest.mark.asyncio
    async def test_async_bulk_save(self):
        pass

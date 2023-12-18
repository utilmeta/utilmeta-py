import pytest
from tests.config import setup_service

setup_service(__name__)


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

    def test_init_articles(self, service):
        from app.schema import ArticleSchema
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

    @pytest.mark.asyncio
    async def test_async_init_users(self):
        pass

    @pytest.mark.asyncio
    async def test_async_serialize_articles(self):
        pass

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

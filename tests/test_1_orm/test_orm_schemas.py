import utype.utils.exceptions

from utilmeta.core import orm
import pytest
from django.db import models
from tests.conftest import setup_service
import sys

#
setup_service(__name__, async_param=False)

from utype.types import *


class TestORMSchemas:
    def test_incorrect_related_model(self):
        from app.models import User
        from app.schema import ContentSchema

        with pytest.raises(Exception):
            class UserSchema(orm.Schema[User]):
                followers: List[ContentSchema]

    def test_multiple_single_field_type(self):
        from app.models import User

        class UserTestSchema(orm.Schema[User]):
            follower_names = orm.Field('followers.username')

        ft = UserTestSchema.__parser__.get_field('follower_names').type
        assert getattr(ft, '__origin__', None) == list
        assert ft([1, 2]) == ['1', '2']

        with pytest.raises(utype.utils.exceptions.ParseError):
            ft(['a' * 30])

    def test_non_exists_fields(self):
        from app.models import User, Article

        with pytest.raises(Exception):
            class UserSchema(orm.Schema[User]):
                not_exists_field: str = orm.Field('not_exists_field')

        with pytest.raises(Exception):
            class UserSchema2(orm.Schema[User]):
                not_exists_addon: str = orm.Field('username.not_exists')

        with pytest.raises(Exception):
            class UserSchema3(orm.Schema[User]):
                not_exists_rel_field: str = orm.Field('articles.not_exists')

        with pytest.raises(Exception):
            class ArticleSchema(orm.Schema[Article]):
                not_exists_fk_field: str = orm.Field('author.not_exists')

        with pytest.raises(Exception):
            class ArticleSchem2(orm.Schema[Article]):
                not_exists_lk: str = orm.Field('author__contains')

        with pytest.raises(Exception):
            class Article_(orm.Schema[Article]):
                id: int
                not_exists: int = models.Count('not_exists')
                # not exists

    if sys.version_info >= (3, 9):
        def test_transform_fields(self):
            from app.models import User, Article

            class ArticleTestSchema(orm.Schema[Article]):
                created_year = orm.Field('created_at.year')
                first_tag: str = orm.Field('tags__0')

            from utype.types import Year
            assert issubclass(ArticleTestSchema.__parser__.get_field('created_year').type, Year)

            class UserLatestSchema(orm.Schema[User]):
                latest_article_year: int = models.Max('contents__article__created_at__year')

        def test_lookup_fields(self):
            from app.models import User, Article

            with pytest.raises(TypeError):
                class ArticleTestSchema(orm.Schema[Article]):
                    author_name: int = orm.Field('author.username')
                    # invalid declaration

            with pytest.raises(TypeError):
                class ArticleTestSchema2(orm.Schema[Article]):
                    title: int
                    # invalid declaration

            class ArticleTestSchema3(orm.Schema[Article]):
                created_at: float       # timestamp

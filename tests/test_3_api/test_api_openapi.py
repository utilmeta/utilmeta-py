import utype

from utilmeta.core import api, request, file, orm
from utilmeta.core.api.specs.openapi import OpenAPI
from utilmeta.core.response import Response
from tests.conftest import setup_service


setup_service(__name__, backend='django')


class TestOpenAPI:
    def test_multiple_properties_query(self):
        from app.models import Article, User
        from utilmeta import service

        class QueryAPI(api.API):    # noqa
            class ArticleQuery(orm.Query[Article]):
                slug: str

            class UserQuery(orm.Query[User]):
                username: str

            @api.get
            def query(self,
                      article_query: ArticleQuery,
                      user_query: UserQuery):
                pass

        generator = OpenAPI(service)
        generator.from_api(QueryAPI)
        query_doc: dict = generator.paths['/query']['get']
        assert query_doc.get('operationId') == 'query'
        params = query_doc.get('parameters')
        slug = None
        username = None
        for param in params:
            if param.get('name') == 'slug':
                slug = param
            elif param.get('name') == 'username':
                username = param
        assert slug
        assert username

    def test_multiple_properties_body(self):
        from app.models import Article, User
        from utilmeta import service

        class QueryAPI(api.API):    # noqa
            class ArticleSchema(orm.Schema[Article]):
                slug: str
                author_id: int

            class ArticlePart2(utype.Schema):
                operation: str
                params: dict

            @api.post
            def query(self,
                      data: ArticleSchema = request.Json,
                      data_part2: ArticlePart2 = request.Json,
                      form: ArticleSchema = request.Form):
                pass

        generator = OpenAPI(service)
        generator.from_api(QueryAPI)
        query_doc: dict = generator.paths['/query']['post']
        assert (query_doc.get('requestBody')['content'] ==
                {'application/json': {'schema': {'allOf': [{'$ref': '#/components/schemas/QueryAPI.ArticleSchema'},
                                                           {'$ref': '#/components/schemas/QueryAPI.ArticlePart2'}]}},
                 'multipart/form-data': {'schema': {'$ref': '#/components/schemas/QueryAPI.ArticleSchema'}}})

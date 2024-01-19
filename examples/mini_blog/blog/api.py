from utilmeta.core import api, orm
from .models import User, Article
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str

class ArticleAPI(api.API):
    async def get(self, id: int) -> ArticleSchema:
        return await ArticleSchema.ainit(id)

    # @api.get
    # async def exists(self, id: int) -> bool:
    #     return await Article.objects.filter(id=id).aexists()

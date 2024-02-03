from utype.types import *
from utilmeta.core import orm, auth
from .models import User, Article, Comment, BaseContent
from utype import Field
from utilmeta.core.orm.backends.django import expressions as exp
from utilmeta.utils import awaitable
import sys


__all__ = ["UserSchema", "ArticleSchema", "CommentSchema",
           "ContentSchema", 'UserBase', 'UserQuery', 'ArticleQuery']


class UserBase(orm.Schema[User]):
    id: int = orm.Field(mode='ra')
    username: str
    password = orm.Field(mode='wa')
    avatar: str = orm.Field(mode='rw')
    followers_num: int = orm.Field(exp.Count('followers'))
    followings_num: Annotated[int, exp.Count('followings')]
    signup_time: datetime


class ContentSchema(orm.Schema[BaseContent]):
    id: int = orm.Field(mode='ra')
    content: str = orm.Field(
        auth={'r': auth.Require()}
    )  # test read auth, test common field mount
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.now, no_input=True)       # last modified
    public: bool = orm.Field(auth={
        'w': orm.Relate('author'),
        'a': auth.Require()
    }, default=True)
    type: str
    liked_bys_num: int = orm.Field(exp.Count("liked_bys"))
    comments_num: int = orm.Field(exp.Count("comments"))
    author_id: int = orm.Field(mode='ra')  # test with author
    liked: bool = False


class CommentSchema(ContentSchema[Comment]):
    type: Literal["comment"] = "comment"
    on_content_id: int = orm.Field(mode='ra', alias="@content")
    creator: UserBase = orm.Field(
        "author", alias="@author",
        # mount=True
    )  # test one-to mount and without module
    comments: List["CommentSchema"]
    # recursively


class ArticleSchema(ContentSchema[Article]):
    type: Literal["article"] = "article"
    content = orm.Field(auth={
        'w': orm.Relate('author'),
        'r': auth.Require()
    })

    author: UserBase = Field(description='author field')
    author_name: str = orm.Field("author.username", alias="author.name")
    author__signup_time: datetime = orm.Field(no_output=True)  # test __ in field name

    author_contents_num: int = exp.Count("author__contents")  # multi lookup expr
    # test expr as default value

    author_articles_views: Annotated[int, exp.Sum(
        "author__contents__article__views"
    )] = 0  # multi lookup expr

    author_avg_articles_views: float = orm.Field(
        exp.Avg(  # multi lookup expr with filter
            "author__contents__article__views",
            filter=exp.Q(author__contents__article__views__gt=0),
        ),
        round=2,
    )
    # test field rule

    is_author: bool = False  # readonly reserve field
    # slug: str = orm.Field(readonly=True, allow_creation=True, no_input=True)
    slug: str = orm.Field(no_input='wa')
    title: str

    # if sys.version_info >= (3, 9):
    #     tags: List[str] = orm.Field(default_factory=list)

    views: int = orm.Field(mode='ra')  # test allow_creation
    # views_min: int = orm.Field("views", operator="-", alias="views-")
    # operator is not allowed in creation

    # created_at_date: date = orm.Field("created_at.date")  # with addon
    # fixme: async -no such function: django_datetime_cast_date
    # possible workaround: ignore __date in serialization, use the [date] type to convert datetime to date

    writable_field: str = orm.Field(mode='w', default=None)
    creatable_field: str = orm.Field(mode='a', default=None)

    comments: List[CommentSchema] = orm.Field(
        default_factory=list,
        fail_silently=False,
    )  # mount with module

    @property
    @Field(dependencies=['author.name', 'author__signup_time'])
    def author_tag(self) -> Dict[str, Any]:
        return dict(
            name=self.author_name,  # test alias dependency
            time=self.author__signup_time,
        )

    def __validate__(self):
        if 'slug' not in self:
            self.slug = '-'.join([''.join(filter(str.isalnum, v)) for v in self.title.split()]).lower()

    @classmethod
    def get_runtime_schema(cls, user_id):
        class article_schema(cls):
            following_likes: int = exp.SubqueryCount(
                User.objects.filter(
                    followers=user_id,
                    likes=exp.OuterRef('pk')
                )
            )
        return article_schema


class UserSchema(UserBase):
    @classmethod
    def get_top_articles(cls, *pks):
        pk_map = {}
        for pk in pks:
            pk_map.setdefault(pk, list(
                Article.objects.filter(author_id=pk).order_by('-views')[:2].values_list('pk', flat=True)))
        return pk_map

    @classmethod
    @awaitable(get_top_articles)
    async def get_top_articles(cls, *pks):
        pk_map = {}
        for pk in pks:
            pk_map.setdefault(pk, [val async for val in Article.objects.filter(
                author_id=pk).order_by('-views')[:2].values_list('pk', flat=True)])
        return pk_map

    top_articles: List[ArticleSchema] = orm.Field(get_top_articles)
    # field point to contents but module is subclass of contents.related_model
    # so field.related_model is orm.model if module is provided so that limit can be correctly applied

    liked_slugs: List[str] = orm.Field("likes__article__slug")

    sum_views: int = orm.Field(
        exp.Sum("contents__article__views"),
        alias="@views",
    )
    articles_num: int = orm.Field(exp.Count("contents", filter=exp.Q(contents__type="article")))
    combined_num: int = orm.Field(exp.Count("contents") * exp.Count("followers"))

    # @property
    # def total_views(self) -> int:
    #     return sum([article.views for article in self.articles])


class UserQuery(orm.Query[User]):
    username: str
    username_like: str = orm.Filter(query=lambda v: exp.Q(username__icontains=v))
    followers: int
    followings: int
    follower_name: str = orm.Filter("followers.username")
    within_days: int = orm.Filter(query=lambda v: exp.Q(
        signup_time__gte=datetime.now() - timedelta(days=v)
    ))
    signup_date: date = orm.Filter('signup_time.date')
    followers_num: int = orm.Filter(exp.Count("followers"))
    followers_num_gte: int = orm.Filter(
        exp.Count("followers"),
        query=lambda v: exp.Q(followers_num_gte__gte=v),
        alias='followers_num>='
    )
    # ugly though...

    order: List[str] = orm.OrderBy({
        "followers_num": orm.Order(field=exp.Count("followers")),
        "likes_num": orm.Order(field=exp.Count("likes")),
        "views_num": orm.Order(
            field=exp.Sum("contents__article__views"), nulls_first=True, asc=False
        ),
        "popularity": orm.Order(
            field=-exp.Count("followers") * exp.Sum("contents__article__views"),
            desc=False,
        ),
        User.signup_time: orm.Order()
        # test combined expression
    })

    page: int = orm.Page(alias='@page')
    rows: int = orm.Limit(alias='@rows')
    scope: Union[dict, list] = orm.Scope()
    exclude: Union[dict, list] = orm.Scope(excluded=True)


class ArticleQuery(orm.Query[Article]):
    id: int
    author: str = orm.Filter('author.username')

    keyword: str = orm.Filter('content__icontains')
    within_days: int = orm.Filter(query=lambda v: exp.Q(
        created_at__gte=datetime.now() - timedelta(days=v)
    ))

    search: str = orm.Filter(query=lambda v: exp.Q(content__icontains=v))

    liked: str = orm.Filter('liked_bys.username')

    order: List[str] = orm.OrderBy({
        "comments_num": orm.Order(field=exp.Count("comments")),
        "liked_num": orm.Order(field=exp.Count("liked_bys")),
        Article.views: orm.Order(),
        Article.created_at: orm.Order(),
    })

    offset: int = orm.Offset(alias='@offset')
    limit: int = orm.Limit(alias='@limit')
    scope: dict = orm.Scope()

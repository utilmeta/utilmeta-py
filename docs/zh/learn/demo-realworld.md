# 案例教程 - Realworld 博客项目

这个章节的案例教程将带你使用 UtilMeta 实现一个经典的博客项目的 API 接口，提供的功能包括
* 用户的注册，登录，获取，更新信息，关注，取关
* 文章的创建，修改，喜欢，推荐，文章评论的创建和删除

别紧张，实现出以上全部功能的 UtilMeta 代码不到 600 行，下面将一步步从创建项目开始教会你如何实现它

::: Tip
我们将会按照  [Realworld API 文档](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints) 的要求开发这个案例项目，项目的完整源代码在 [案例源码 Github](https://github.com/utilmeta/utilmeta-py-realworld-example-app)
:::

## 1. 创建项目

### 安装依赖

在创建项目之前，请先安装本案例教程所需的依赖库
```shell
pip install utilmeta starlette django databases[aiosqlite]
```

::: tip
本教程的技术选型为
* 使用 Starlette 作为 HTTP backend，开发异步接口
* 使用 Django ORM 作为数据模型库
* 使用 SQLite 作为数据库
* 使用 JWT 进行用户鉴权
:::
### 创建项目

使用如下命令创建一个新的 UtilMeta 项目

```shell
meta setup utilmeta-realworld-blog --temp=full
```

接着按照提示输入或跳过，在提示选择 backend 时输入 starlette

```
Choose the http backend of your project 
 - django (default)
 - flask
 - fastapi
 - starlette
 - sanic
 - tornado
>>> starlette
```

::: tip
由于我们的项目包含多种接口和模型逻辑，为了方便更好地组织项目，我们在创建命令中使用了 `--temp=full` 参数创建完整的模板项目（默认创建的是单文件的简单项目）
::: 

我们可以看到这个命令创建出的项目结构如下
```
/config
	conf.py
	env.py
	service.py
/domain
/service
	api.py
main.py
meta.ini
```

其中，我们建议的组织方式为
* `config`：存放配置文件，环境变量，服务运行参数等
* `domain`：存放领域应用，模型与 RESTful 接口
* `service`：整合内部接口与外部服务
* `main.py`：运行入口文件，调试时使用 `python main.py` 即可直接运行服务
* `meta.ini`：元数据声明文件，`meta` 命令行工具通过识别这个文件的位置确定项目的根目录

## 2. 编写数据模型

对于博客这样以数据的增删改查为核心的 API 系统，我们往往从数据模型开始开发，通过对  [API 文档] 的分析我们可以得出需要编写用户，文章，评论等模型

### 创建领域应用

由于我们使用 Django 作为 ORM 底层实现，我们就依照 django 组织 app 的方式来组织我们的项目，我们可以简单把博客项目分成【用户】【文章】两个领域应用

首先使用如下命令为项目添加一个名为 user 的用户应用
```shell
meta add user
```
命令运行后你可以看到在 `domain` 文件夹下创建了一个新的文件夹，结构如下

```
/domain
	/user       # new folder
		/migrations
		api.py
		models.py
		schema.py
```

博客的用户模型以及用户和鉴权的相关接口将会放在这个文件夹中

::: tip
即使你不熟悉 Django 的 app 用法也没有关系，你可以简单理解为一个分领域组织代码的文件夹，领域的划分标准由你来确定
:::

我们再添加一个名为 article 的文章应用
```shell
meta add article
```

### 用户模型

我们将按照 [API 文档：User](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#users-for-authentication) 中对用户数据结构的说明编写数据模型，我们打开 `domain/user/models.py`，编写
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField, AwaitableModel

class User(AwaitableModel):
    username = models.CharField(max_length=40, unique=True)
    password = PasswordField(max_length=100)
    email = models.EmailField(max_length=60, unique=True)
    token = models.TextField(default='')
    bio = models.TextField(default='')
    image = models.URLField(default='')
```


::: tip AwaitableModel
`AwaitableModel` 是 UtilMeta 为 Django 查询在异步环境执行所编写的模型基类，它的底层使用 `encode/databases` 集成了各个数据库的异步引擎，能够使得 Django 真正发挥出异步查询的性能
:::

### 文章与评论模型

我们可以观察到文章与评论的数据模型有着相似的结构，我们就可以利用 Django 模型类的继承用法来减少编码量

基础模型 `domain/article/models.py`
```python
from django.db import models
from utilmeta.core.orm.backends.django import models as amodels

class BaseContent(amodels.AwaitableModel):
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author_id: int

    class Meta:
        abstract = True
        ordering = ['-created_at']

class Tag(amodels.AwaitableModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Article(BaseContent):
    slug = models.SlugField(db_index=True, max_length=255, unique=True)
    title = models.CharField(db_index=True, max_length=255)
    description = models.TextField()
    author = models.ForeignKey(
	    'user.User', on_delete=models.CASCADE, related_name='articles')
    tags = models.ManyToManyField(Tag, related_name='articles')

class Comment(BaseContent):
    article = models.ForeignKey(
	    Article, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(
	    'user.User', on_delete=models.CASCADE, related_name='comments')
```

### 添加关系模型

博客项目需要记录用户之间的关注关系与用户与文章之间的喜欢关系，所以我们需要添加 `Favorite` 和 `Follow` 中间表模型来记录用户，文章之间的关系

我们再次打开 `domain/user/models.py`，创建关系表并为 `User` 表添加多对多关系字段
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField, AwaitableModel, ACASCADE

class User(AwaitableModel):
    username = models.CharField(max_length=40, unique=True)
    password = PasswordField(max_length=100)
    email = models.EmailField(max_length=60, unique=True)
    token = models.TextField(default='')
    bio = models.TextField(default='')
    image = models.URLField(default='')

	# new
    followers = models.ManyToManyField(
        'self', related_name='followed_bys', through='Follow', 
        through_fields=('following', 'follower'),
        symmetrical=False
    )
    favorites = models.ManyToManyField(
	    'article.Article', through='Favorite', related_name='favorited_bys')

class Favorite(AwaitableModel):
    user = models.ForeignKey(User, related_name='article_favorites', on_delete=ACASCADE)
    article = models.ForeignKey(
	    'article.Article', related_name='user_favorites', on_delete=ACASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'article')


class Follow(AwaitableModel):
    following = models.ForeignKey(
	    User, related_name='user_followers', on_delete=ACASCADE)
    follower = models.ForeignKey(
	    User, related_name='user_followings', on_delete=ACASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('following', 'follower')
```


* `User`：用户模型
* `Favorite`：文章的喜欢模型
* `Follow`：关注模型

::: tip
例子中的 `ACASCADE` 是 UtilMeta 为 Django 在异步环境下执行所开发的异步级联删除函数
:::

### 接入数据库

当我们编写好数据模型后即可使用 Django 提供的迁移命令方便地创建对应的数据表了，由于我们使用的是 SQLite，所以无需提前安装数据库软件，只需要运行以下两行命令即可完成数据库的创建

```shell
meta makemigrations
meta migrate
```

当看到以下输出时即表示你已完成了数据库的创建

```
Operations to perform:
  Apply all migrations: article, contenttypes, user
Running migrations:
  Applying article.0001_initial... OK
  Applying user.0001_initial... OK
  Applying article.0002_initial... OK
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
```

::: tip
以上的命令是 Django 的数据库迁移命令，`makemigrations` 会把数据模型的变更保存为迁移文件，而 `migrate` 命令则会把迁移文件转化为创建或调整数据表的 SQL 语句执行
:::


完成以上命令后你会在项目文件夹中看刚刚创建好名为 `db` 的 SQLite 数据库，如果你想知道数据库是如何配置的，请打开 `config/conf.py` 文件，你会在其中找到如下代码

```python
service.use(DatabaseConnections({
	'default': Database(
		name='db',
		engine='sqlite3',
	)
}))
```

这部分代码就是用来声明数据库的连接配置的


## 3. 开发用户接口与鉴权

### 实现 JWT 鉴权

UtilMeta 内置的鉴权组件中已经有了 JWT 鉴权的实现，我们只需声明相应的参数即可获得 JWT 鉴权能力，我们在 `config` 文件夹中创建一个名为 `auth.py` 的文件，编写鉴权相关的配置

```python
from .env import env
from utilmeta.core import api, auth
from utilmeta.core.auth import jwt
from utilmeta.core.request import var
from domain.user.models import User

class API(api.API):
    user_config = auth.User(
        User,
        authentication=jwt.JsonWebToken(
            key=env.JWT_SECRET_KEY,
            user_token_field=User.token
        ),
        login_fields=User.email,
        password_field=User.password,
    )

    async def get_user(self) -> User:
        return await self.user_config.getter(self.request)

    async def get_user_id(self) -> int:
        return await var.user_id.get(self.request)
```

我们通过创建一个 API 基类来 

之后我们编写的需要鉴权的接口类都可以继承这个 API 类，这样接口函数可以通过 `await self.get_user()` 获取当前的请求用户


任何一个需要用户登录才能访问的接口，你都可以直接在接口参数中声明 `user: User = API.user_config`，这样你就可以通过 `user` 直接拿到当前请求用户的实例

### 用户 API

```python
from utilmeta.core import orm
from .models import User

class UserSchema(orm.Schema[User]):
    id: int = orm.Field(no_input=True)
    username: str = orm.Field(regex='[A-Za-z0-9_]{1,20}')
    email: str
    password: str = orm.Field(mode='wa')
    token: str = orm.Field(mode='r')
    bio: str
    image: str
```


```python
from utilmeta.core import response, request, api, orm
from config.auth import API
from .schema import UserSchema

class UserResponse(response.Response):
    result_key = 'user'
    result: UserSchema

class UserAPI(API):
    response = UserResponse

    @api.get
    async def get(self):      # get current user
        user_id = await self.get_user_id()
        if not user_id:
            raise exceptions.Unauthorized('authentication required')
        return await UserSchema.ainit(user_id)

    @api.put
    async def put(self, user: UserSchema[orm.WP] = request.BodyParam):
        user.id = await self.get_user_id()
        await user.asave()
        return await self.get()
```

* `UserSchema.ainit`
* `asave`

## 4. 开发文章与评论接口




### 编写文章 Schema

Query Schema 是 UtilMeta ORM 的核心用法，你只需要编写一个简单的类，即可将你需要的增改查模板声明出来并直接使用，我们以文章模型为例来示范 Schema 的用法

```python
from utype.types import *
from utilmeta.core import orm
from utilmeta.core.orm.backends.django import expressions as exp
from .models import Article
from domain.user.schema import ProfileSchema

class ArticleSchema(orm.Schema[Article]):
    id: int = orm.Field(no_input=True)
    body: str
    created_at: datetime
    updated_at: datetime
    author: ProfileSchema
    author_id: int = orm.Field(mode='a', no_input=True)
    
    slug: str = orm.Field(no_input='aw', default=None, defer_default=True)
    title: str = orm.Field(default='', defer_default=True)
    description: str = orm.Field(default='', defer_default=True)
    tag_list: List[str] = orm.Field(
	    'tags.name', mode='rwa', no_output='aw', default_factory=list)
    favorites_count: int = exp.Count('favorited_bys')
    
```

* `author`: **关系 Schema 字段**

* `tag_list`: **多级查询字段**

* `favorites_count`: **表达式字段**

::: tip 表达式字段
还记得你在 User 模型中声明的 `favorites = models.ManyToManyField('article.Article', related_name='favorited_bys')` 字段吗？你可以灵活地使用这些关系名称或反向关系来创建表达式字段，如 ArticleSchema 中的 `favorites_count` 字段使用 `exp.Count('favorited_bys')` 表示【喜欢这个文章的用户的数量】
:::


#### 字段模式
`mode` 参数可以用来声明一个字段适用的模式（场景），在数据 ORM 中常用的场景有
* `'r'`：查询：作为数据库查询的结果返回
* `'w'`：更新：
* `'a'`：创建：

你可以组合模式字母来表示字段支持多种模式，默认

::: tip
即使你没有声明模式，UtilMeta 也会根据 ORM 模型的特性自动为字段赋予模式，比如类似 `created_at` 这样被自动创建的字段就无法被修改，也无需在创建中提供，其模式会自动被赋予为 `'r'`（只读），你可以通过显式声明 `mode` 参数来覆盖默认的模式赋予
:::


所以
```python
author_id: int = orm.Field(mode='a', no_input=True)
```

其中的含义为
* 这个字段只适用于模式 `'a'` (创建数据) 
* 这个字段无需输入

从实际开发角度来理解，一个文章的作者字段应该在文章创建时传入当前请求的用户，而忽略客户端可能提供的其他值，并且也不应该允许被修改，实际在接口开发中，会在数据保存前对该字段进行赋值，如

```python
@api.post
async def create_article( 
	article: ArticleSchema[orm.A] = request.BodyParam, 
	user: User = API.user_config
):
	article.author_id = user.pk
	await article.asave()
```

::: tip
`no_input=True` 参数会忽略该字段在 Schema 初始化中提供的数据，即客户端传递的数据，但是仍然允许开发者在函数逻辑中自行赋值
:::

#### 运行时 Schema
在博客项目中，我们需要对每个文章返回【当前用户是否喜欢】这一信息，然而这样的查询由于涉及到运行时的动态请求，无法直接在类中声明出来，那怎么根据运行时请求来构造查询呢？

一个简单的技巧是编写一个类函数，输入需要处理的运行时参数，然后在函数中进行类继承，增加或调整查询的字段后再返回新的类，比如

```python
class ArticleSchema(orm.Schema[Article]):
	...
    favorited: bool = False
    
    @classmethod
    def get_runtime(cls, user_id):
        if not user_id:
            return cls

        class ArticleRuntimeSchema(cls):
            favorited: bool = exp.Exists(
				Favorite.objects.filter(article=exp.OuterRef('pk'), user=user_id)
			)
            
        return ArticleRuntimeSchema
```

我们编写了 `get_runtime` 类函数，以用户的 ID 作为输入生成相应的查询字段，这样我们在 API 函数中就可以使用 `ArticleSchema.get_runtime(user_id)`这样的方式来动态获得 Schema 类了

### 编写文章 API


[单个文章](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#single-article)：当请求或更新单个文章或创建文章时返回
```json
{
  "article": {..}
}
```

[多个文章](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#multiple-articles)：当请求文章列表时返回
```json
{
  "articles": [..],
  "articlesCount": 2
}
```

对于 API 文档这样的要求，我们可以很轻松的使用 UtilMeta 的响应模板来处理

```python
class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    result: List[ArticleSchema]

class SingleArticleResponse(response.Response):
    result_key = 'article'
    result: ArticleSchema
```


#### 文章查询接口

```python
class ArticleAPI(API):
    class ListArticleQuery(orm.Query[Article]):
        tag: str = orm.Filter('tags.name')
        author: str = orm.Filter('author.username')
        favorited: str = orm.Filter('favorited_bys.username')
        offset: int = orm.Offset(default=0)
        limit: int = orm.Limit(default=20, le=100)

    @api.get
    async def get(self, query: ListArticleQuery) -> MultiArticlesResponse:
        count = await query.acount()
        schema = ArticleSchema.get_runtime(
            await self.get_user_id()
        )
        return MultiArticlesResponse(
            result=await schema.aserialize(
                query.get_queryset()
            ),
            count=count
        )
```


### 评论接口

```python
@api.route('{slug}/comments')
class CommentAPI(API):
    slug: str = request.SlugPathParam

    class ListResponse(response.Response):
        result_key = 'comments'
        name = 'list'
        result: List[CommentSchema]

    class ObjectResponse(response.Response):
        result_key = 'comment'
        name = 'object'
        result: CommentSchema

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article: Optional[Article] = None

    @api.get
    async def get(self) -> ListResponse:
        return self.ListResponse(
            await CommentSchema.aserialize(
                Comment.objects.filter(article=self.article)
            )
        )

    @api.post
    async def post(self, comment: CommentSchema[orm.A] = request.BodyParam,
                   user: User = API.user_config) -> ObjectResponse:
        comment.article_id = self.article.pk
        comment.author_id = user.pk
        await comment.asave()
        return self.ObjectResponse(
            await CommentSchema.ainit(comment.pk)
        )

    @api.delete('/{id}')
    async def delete_comment(self, id: int, user: User = API.user_config):
        comment = await Comment.objects.filter(
            id=id,
        ).afirst()
        if not comment:
            raise exceptions.NotFound('comment not found')
        if comment.author_id != user.pk:
            raise exceptions.PermissionDenied('permission denied')
        await comment.adelete()

    @api.before('*')
    async def handle_article_slug(self):
        article = await Article.objects.filter(slug=self.slug).afirst()     
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article

class ArticleAPI(API):
    comments: CommentAPI
    ...
```

我们需要将评论 API 的路径配置到 `articles/{slug}/comments`，所以我们直接使用装饰器 `@api.route('{slug}/comments')` 来装饰 `CommentAPI`

其中 `{slug}` 为标识文章的路径参数，并且在 API 中实现了名为 `handle_article_slug` 的钩子，在接口函数执行前统一将对应的文章查询出来

::: tip API 公共参数
由于在评论 API 中，所有的接口都需要接收 `{slug}` 路径参数，我们就可以将这个参数直接声明到 API 类中，在函数中直接使用 `self.slug` 获取，这样的参数称为 API 公共参数，它们同样会被整合到生成的 API 文档中
:::


我们将 CommentAPI 挂载到了 ArticleAPI

## 4. 接口整合与错误处理

我们已经编写好了所有的接口，

```python
from domain.user.api import UserAPI, ProfileAPI, AuthenticationAPI
from domain.article.api import ArticleAPI
from utilmeta.core import api

class RootAPI(api.API):
    user: UserAPI
    users: AuthenticationAPI
    profiles: ProfileAPI
    articles: ArticleAPI
```

## 5. 自动生成 OpenAPI 文档

```python
from utilmeta.core import api
from utilmeta.core.api.specs.openapi import OpenAPI

class RootAPI(api.API):
    docs: OpenAPI.as_api('openapi.json')    # new

	...
```

## 6. 运行与部署

### 时间配置

```python
from utilmeta.conf.time import Time

def configure(service: UtilMeta):
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%S.%fZ"
    ))
```

Time 可以配置 API 使用的时区，UTC，以及输出的时间格式



### 博客前端
博客的前端开发部署并不属于 UtilMeta 的范畴，但是教程这里简单示范如何在本地安装并运行案例中博客项目的前端代码，从而可以直接使用并调试你的 API

::: tip
这一小节需要你有一定的关于前端 npm 的准备知识，并需要有本地 node.js 运行环境
:::


我们使用 [Vue3 的客户端实现](https://github.com/mutoe/vue3-realworld-example-app) 进行客户端演示，首先我们将项目 clone 下来
```shell
git clone git@github.com:mutoe/vue3-realworld-example-app.git
```

打开  `.env` 文件，将其中的 API 地址修改为刚刚运行起来的博客 API 
```env
BASE_URL=/api
VITE_API_HOST=http://127.0.0.1:8000
```

然后我们进入项目中安装依赖并运行项目

```shell
cd vue3-realworld-example-app
npm install
npm dev
```

看到以下提示说明项目已启动

```
➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

我们可以点击访问 [http://localhost:5173/](http://localhost:5173/) 来打开博客的客户端

接下来你就可以体验一下自己编写的博客了~

# Realworld 博客项目

这个章节的案例教程将带你使用 UtilMeta 实现一个经典的博客项目的 API 接口，提供的功能包括

* 用户的注册，登录，获取，更新信息，关注，取关
* 文章的创建，修改，喜欢，推荐，文章评论的创建和删除

别紧张，实现出以上全部功能的 UtilMeta 代码不到 600 行，下面将一步步从创建项目开始教会你如何实现它

!!! tip
	我们将会按照  [Realworld API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/) 的要求开发这个案例项目，项目的完整源代码在 [案例源码 Github](https://github.com/utilmeta/utilmeta-py-realworld-example-app)

## 1. 创建项目

### 安装依赖

在创建项目之前，请先安装本案例教程所需的依赖库
```shell
pip install utilmeta starlette django databases[aiosqlite]
```

!!! abstract "技术选型"
	
	* 使用 Starlette 作为 HTTP backend，开发异步接口
	* 使用 Django ORM 作为数据模型库
	* 使用 SQLite 作为数据库
	* 使用 JWT 进行用户鉴权

### 创建命令

使用如下命令创建一个新的 UtilMeta 项目

```shell
meta setup realworld --temp=full
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

!!! tip "模板参数"
	由于我们的项目包含多种接口和模型逻辑，为了方便更好地组织项目，我们在创建命令中使用了 `--temp=full` 参数创建完整的模板项目（默认创建的是单文件的简单项目）


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

对于博客这样以数据的增删改查为核心的 API 系统，我们往往从数据模型开始开发，通过对  [API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/) 的分析我们可以得出需要编写用户，文章，评论等模型

### 创建领域应用

由于我们使用 Django 作为 ORM 底层实现，我们就依照 django 组织 app 的方式来组织我们的项目，我们可以简单把博客项目分成【用户】【文章】两个领域应用

首先使用如下命令为项目添加一个名为 user 的用户应用
```shell
meta add user
```
命令运行后你可以看到在 `domain` 文件夹下创建了一个新的文件夹，结构如下

```  hl_lines="2"
/domain
	/user
		/migrations
		api.py
		models.py
		schema.py
```

博客的用户模型以及用户和鉴权的相关接口将会放在这个文件夹中

!!! tip
	即使你不熟悉 Django 的 app 用法也没有关系，你可以简单理解为一个分领域组织代码的文件夹，领域的划分标准由你来确定

我们再添加一个名为 article 的文章应用，将会用于存放文章与评论的模型和接口
```shell
meta add article
```

### 用户模型

我们将按照 [API 文档：User](https://realworld-docs.netlify.app/specifications/backend/api-response-format/#users-for-authentication) 中对用户数据结构的说明编写数据模型，我们打开 `domain/user/models.py`，编写用户的模型
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

!!! abstract "AwaitableModel"
	`AwaitableModel` 是 UtilMeta 为 Django 查询在异步环境执行所编写的模型基类，它的底层使用 [encode/databases](https://github.com/encode/databases) 集成了各个数据库的异步引擎，能够使得 Django 真正发挥出异步查询的性能

### 文章与评论模型

我们按照 [API 文档：Article](https://realworld-docs.netlify.app/specifications/backend/api-response-format/#single-article) 编写文章与评论模型，打开 `domain/article/models.py`，编写
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

class Tag(amodels.AwaitableModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Article(BaseContent):
    slug = models.SlugField(db_index=True, max_length=255, unique=True)
    title = models.CharField(db_index=True, max_length=255)
    description = models.TextField()
    author = models.ForeignKey(
	    'user.User', on_delete=amodels.ACASCADE, related_name='articles')
    tags = models.ManyToManyField(Tag, related_name='articles')

class Comment(BaseContent):
    article = models.ForeignKey(
	    Article, related_name='comments', on_delete=amodels.ACASCADE)
    author = models.ForeignKey(
	    'user.User', on_delete=models.CASCADE, related_name='comments')
```

!!! tip "模型继承"
	可以观察到文章与评论的数据模型有着相似的结构，我们就可以利用 Django 模型类的继承用法来减少重复的字段声明

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

	# new +++
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

我们新增了两个模型

* `Favorite`：文章的喜欢关系模型
* `Follow`：用户之间的关注关系模型

同时也在 User 模型中添加了对应的多对多关系字段 `followers` 和 `favorites`，将会用于接下来的查询接口的编写

!!! tip
	例子中的 `ACASCADE` 是 UtilMeta 为 Django 在异步环境下执行所开发的异步级联删除函数

### 接入数据库

当我们编写好数据模型后即可使用 Django 提供的迁移命令方便地创建对应的数据表了，由于我们使用的是 SQLite，所以无需提前安装数据库软件，只需要在项目目录中运行以下两行命令即可完成数据库的创建

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

!!! tip "数据库迁移命令"
	以上的命令是 Django 的数据库迁移命令，`makemigrations` 会把数据模型的变更保存为迁移文件，而 `migrate` 命令则会把迁移文件转化为创建或调整数据表的 SQL 语句执行


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

Realworld 博客项目需要使用 JWT 作为请求鉴权的方式，即处理用户登录与识别当前请求的用户
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
            secret_key=env.JWT_SECRET_KEY,
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

我们通过创建一个新的 API 基类来声明鉴权相关的配置，这样需要鉴权的 API 类都可以直接继承这个新的 API 基类，在它们的接口函数中可以通过 `await self.get_user()` 获取当前的请求用户

任何一个需要用户登录才能访问的接口，你都可以直接在接口参数中声明 `user: User = API.user_config`，这样你就可以通过 `user` 直接拿到当前请求用户的实例

!!! tip
	关于鉴权方面的详细说明可以参考 [接口与用户鉴权](../../guide/auth) 这篇文档

#### 环境变量管理

类似 `JWT_SECRET_KEY` 这样重要的密钥我们一般不会将它硬编码到代码中，而是使用环境变量的方式定义，UtilMeta 提供了一套环境变量声明模板，我们可以打开 `config/env.py` 编写

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

这样我们可以将 JWT 的密钥定义在运行环境的 `CONDUIT_JWT_SECRET_KEY` 变量中，并且使用 `env.JWT_SECRET_KEY` 访问即可

### 用户鉴权 API

对于用户而言，我们需要实现用户的注册，登录，查询与更新当前用户数据的接口，这其实与上一篇教程 [编写用户登录注册 API](tutorials/user-auth) 的方法一致，我们就直接展示对应的代码

=== "domain/user/api.py"
	```python
	from utilmeta.core import response, request, api, orm
	from config.auth import API
	from .schema import UserSchema
	
	class UserResponse(response.Response):
		result_key = 'user'
		result: UserSchema
	
	class UserAPI(API):
		response = UserResponse
	
		async def get(self):      # get current user
			user_id = await self.get_user_id()
			if not user_id:
				raise exceptions.Unauthorized('authentication required')
			return await UserSchema.ainit(user_id)
	
		async def put(self, user: UserSchema[orm.WP] = request.BodyParam):
			user.id = await self.get_user_id()
			await user.asave()
			return await self.get()
	
	class AuthenticationAPI(API):
	    response = UserResponse
	
	    async def post(self, user: UserRegister = request.BodyParam):        # signup
	        if await User.objects.filter(username=user.username).aexists():
	            raise exceptions.BadRequest(f'duplicate username: {repr(user.username)}')
	        if await User.objects.filter(email=user.email).aexists():
	            raise exceptions.BadRequest(f'duplicate email: {repr(user.username)}')
	        await user.asave()
	        await self.user_config.login_user(
	            request=self.request,
	            user=user.get_instance(),
	        )
	        return await UserSchema.ainit(user.pk)
	
	    @api.post
	    async def login(self, user: UserLogin = request.BodyParam):
	        user_inst = await self.user_config.login(
	            self.request, ident=user.email, password=user.password)
	        if not user_inst:
	            raise exceptions.PermissionDenied('email or password wrong')
	        return await UserSchema.ainit(user_inst)
	```
	
=== "domain/user/schema.py"
	```python
	from utilmeta.core import orm
	from .models import User, Follow
	from utilmeta.core.orm.backends.django import expressions as exp
	from utype.types import EmailStr
	
	class UsernameMixin(orm.Schema[User]):
		username: str = orm.Field(regex='[A-Za-z0-9][A-Za-z0-9_]{2,18}[A-Za-z0-9]')
	
	class UserBase(UsernameMixin):
		bio: str
		image: str
	
	class UserLogin(orm.Schema[User]):
		email: str
		password: str
	
	class UserRegister(UserLogin, UsernameMixin): pass
	
	class UserSchema(UserBase):
		id: int = orm.Field(no_input=True)
		email: EmailStr
		password: str = orm.Field(mode='wa')
		token: str = orm.Field(mode='r')
	```


我们编写的 AuthenticationAPI 继承自之前在 `config/auth.py` 中定义的 API 类，在用户注册的 `post` 接口中，当用户完成注册后使用了 `self.user_config.login_user` 方法直接将用户登录当前的请求（即生成对应的 JWT Token 然后更新用户的 `token` 字段）

另外由于 [API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/#authentication)中对于请求与响应体结构的要求，我们声明请求体参数使用的是 `request.BodyParam`，这样参数名 `user` 会作为对应的模板键，而我们的响应也使用了响应模板中的 `result_key` 指定了 `'user'` 作为结果的模板键，于是用户接口的请求和响应的结构就与文档一致了

```json
{
  "user": {
    "email": "jake@jake.jake",
    "token": "jwt.token.here",
    "username": "jake",
    "bio": "I work at statefarm",
    "image": null
  }
}
```

### Profile API
根据 [API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/#get-profile)，Realworld 博客项目还需要开发一个获取用户详情，关注与取消关注的 Profile 接口

=== "domain/user/api.py"
	```python
	# new +++
	from .schema import ProfileSchema
	from .models import Follow
	
	class ProfileResponse(response.Response):
	    result_key = 'profile'
	    result: ProfileSchema
	
	@api.route('profiles/{username}')
	class ProfileAPI(API):
	    username: str = request.PathParam(regex='[A-Za-z0-9_]{1,60}') 
	    response = ProfileResponse
	
	    def __init__(self, *args, **kwargs):
	        super().__init__(*args, **kwargs)
	        self.profile: Optional[User] = None
	
	    @api.get
	    async def get(self, user: Optional[User] = API.user_config):
	        return await ProfileSchema.get_runtime(user).ainit(self.profile)
	
	    @api.post
	    async def follow(self, user: User = API.user_config):
	        await Follow.objects.aget_or_create(following=self.profile, follower=user)
	        return await self.get(user)
	
	    @api.delete(follow)
	    async def unfollow(self, user: User = API.user_config):
	        await Follow.objects.filter(following=self.profile, follower=user).adelete()
	        return await self.get(user)
	
	    @api.before('*')
	    async def handle_profile(self):
	        profile = await User.objects.filter(username=self.username).afirst()
	        if not profile:
	            raise exceptions.NotFound(f'profile({repr(self.username)}) not found')
	        self.profile = profile
	```
=== "domain/user/schema.py"
	```python
	class ProfileSchema(UserBase):
		following: bool = False
	
		@classmethod
		def get_runtime(cls, user):
			if not user:
				return cls
	
			class ProfileRuntimeSchema(cls):
				following: bool = orm.Field(
					exp.Exists(
						Follow.objects.filter(
						following=exp.OuterRef('pk'), follower=user)
					)
				)
	
			return ProfileRuntimeSchema
	```


首先在 `domain/user/api.py` 中，ProfileAPI 使用 API 类公共参数复用了路径参数 `username` ，并在 `handle_profile` 预处理钩子中将其查询得到目标用户实例赋值给 `self.profile`，在 API 接口函数 `get`, `follow`, `unfollow` 中只需要使用 `self.profile` 访问目标用户实例即可完成对应的逻辑，另外 `follow` 与 `unfollow` 接口还在返回时复用了 `get` 接口的序列化逻辑

!!! tip "钩子函数"
	钩子函数是 UtilMeta API 类中的特殊函数，可以在给定的 API 接口执行前/后/出错时调用，从而更好的复用逻辑，具体用法可以参考 [APi 类与路由](guide/api-route) 中的【钩子机制】

另外对于接口需要返回的 Profile 对象，[API 文档](https://realworld-docs.netlify.app/specifications/backend/api-response-format/#profile) 中需要返回一个并非来着用户模型的动态字段 `following`，这个字段应该返回【**当前请求的用户**】是否关注了目标用户，所以它的查询表达式无法在 Schema 类中直接编写

所以在 `domain/user/schema.py` 中，我们为 `ProfileSchema` 定义一个动态查询函数 `get_runtime`，传入当前请求的用户，根据请求用户生成对应的查询表达式，再返回新的类即可

在 ProfileAPI 的 get 接口中，你可看到动态查询函数的调用方式

```python hl_lines="4"
class ProfileAPI(API):
    @api.get
    async def get(self, user: Optional[User] = API.user_config):
        return await ProfileSchema.get_runtime(user).ainit(self.profile)
```

## 4. 开发文章与评论接口

### 文章接口结构

根据 [API 文档 | 文章接口](https://realworld-docs.netlify.app/specifications/backend/endpoints/#get-article) 部分的定义，我们可以先开发接口的基本结构
```python
from utilmeta.core import api, request, orm, response
from config.auth import API
from typing import List, Optional

class ArticleSchema(orm.Schema[Article]):
    pass

class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    result: List[ArticleSchema]

class SingleArticleResponse(response.Response):
    result_key = 'article'
    result: ArticleSchema
    
class ArticleAPI(API):
    class BaseArticleQuery(orm.Query[Article]):
        offset: int
        limit: int

    class ListArticleQuery(BaseArticleQuery):
        tag: str
        author: str
        favorited: str

    async def get(self, query: ListArticleQuery) -> MultiArticlesResponse: pass

    @api.get
    async def feed(self, query: BaseArticleQuery) -> MultiArticlesResponse: pass

    @api.get('/{slug}')
    async def get_article(self) -> SingleArticleResponse: pass

    @api.post('/{slug}/favorite')
    async def favorite(
        self, user: User = API.user_config) -> SingleArticleResponse: pass

    @api.delete('/{slug}/favorite')
    async def unfavorite(
        self, user: User = API.user_config) -> SingleArticleResponse: pass

    @api.put('/{slug}')
    async def update_article(self, 
        article: ArticleSchema[orm.WP] = request.BodyParam, 
        user: User = API.user_config) -> SingleArticleResponse: pass

    @api.delete('/{slug}')
    async def delete_article(self, user: User = API.user_config): pass

    async def post(self, 
        article: ArticleSchema[orm.A] = request.BodyParam, 
        user: User = API.user_config) -> SingleArticleResponse: pass
```


!!! tip
	对着给定的 API 文档进行开发，可以先按照文档定义接口的名称，路径，输入输出，然后再补充相关的逻辑

### 编写文章 Schema

我们编写的文章接口需要围绕文章数据进行增删改查，这时我们可以使用 UtilMeta 的 Schema 查询轻松完成，你只需要编写一个简单的类，即可将你需要的增改查模板声明出来并直接使用，我们以文章为例
```python
from utype.types import *
from utilmeta.core import orm
from .models import Article
from domain.user.schema import ProfileSchema
from django.db import models

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
	    'tags.name', alias='tagList',
	    mode='rwa', no_output='aw', default_factory=list
	)
    favorites_count: int = orm.Field(
        models.Count('favorited_bys'),
        alias='favoritesCount'
    )
```

在我们编写的这个 Schema 类中，有很多种类的字段，我们一一说明

* `author`: **关系 Schema 字段**，它是一个外键字段，并且使用类型声明指定了另一个 Schema 类，在查询时，`author` 将会把文章作者用户的信息按照 ProfileSchema 的声明查询出来

!!! tip "关系查询字段"
	外键，多对多，一对多等关系字段都支持 Schema 关系查询，比如例子中 `author` 外键字段的反向关系是用户的文章字段 `articles`，在用户的 Schema 中声明 `articles: List[ArticleSchema]` 即可查询用户的所有文章

* `tag_list`: **多级关系查询字段**，有时你只需要将关系表中的一个字段查询出来，就可以用这样的用法，这个字段声明了 `orm.Field('tags.name')` 会沿着 `tags` - `name` 的路径进行查询，最终查询的是文章对应的标签的名称列表 

* `favorites_count`: **表达式字段**：还记得你在 User 模型中声明的 `favorites = models.ManyToManyField('article.Article', related_name='favorited_bys')` 字段吗？你可以灵活地使用这些关系名称或反向关系来创建表达式字段，`favorites_count` 字段就使用 `models.Count('favorited_bys')` 查询【喜欢这个文章的用户的数量】

另外对于 `tag_list` 和 `favorites_count` 字段，我们使用 `alias` 参数为它们指定了用于输入输出的真实名称（符合 API 文档中要求的驼峰命名）

#### 字段模式
你可以看到在上面的例子中，很多字段都指定了 `mode` 这一参数，`mode` 参数可以用来声明一个字段适用的模式（场景），从而可以在不同的场景中表现出不同的行为，在数据的增删改查中常用的场景有

* `'r'`：**查询**：作为数据库查询的结果返回
* `'w'`：**更新**：作为请求的数据，需要更新数据库的现有记录
* `'a'`：**创建**：作为请求的数据，需要在数据库中新建记录

你可以组合模式字母来表示字段支持多种模式，默认 UtilMeta 会根据模型字段的性质自动赋予模式

!!! tip "自动模式赋予"
	即使你没有声明模式，UtilMeta 也会根据模型字段的特性自动为字段赋予模式，比如类似 `created_at` 这样被自动创建的字段就无法被修改，也无需在创建中提供，其模式会自动被赋予为 `'r'`（只读），你可以通过显式声明 `mode` 参数来覆盖默认的模式赋予

举例来说，字段
```python
author_id: int = orm.Field(mode='a', no_input=True)
```
其中的含义为

* 这个字段只适用于模式 `'a'` (创建数据) 
* 这个字段无需输入

从实际开发角度来理解，一个文章的作者字段应该指定为当前请求的用户，而忽略客户端可能提供的其他值，并且也不应该允许被修改，所以我们会在数据保存前对该字段进行赋值，如
```python
class ArticleAPI(API):
    @api.post
    async def post(self, article: ArticleSchema, user: User = API.user_config):
        article.author_id = user.pk
        await article.asave()
```

!!! tip
	`no_input=True` 参数会忽略该字段在 Schema 初始化中提供的数据，即客户端传递的数据，但是仍然允许开发者在函数逻辑中自行赋值

**模式生成**

你可以直接使用 `YourSchema['<mode>']` 来快速生成对应模式的 Schema 类，UtilMeta 的 `orm` 模块提供了几个常用的模式

* `orm.A`：即 `'a'` 模式，常用于 POST 方法创建新的对象
* `orm.W`：即 `'w'` 模式，常用于 PUT 方法更新对象
* `orm.WP`：忽略必传（`required`）属性的 `'w'` 模式，常用于 PATCH 方法部分更新对象

所以你可以直接使用 `ArticleSchema[orm.A]` 来生成创建模式下的 ArticleSchema 类，作为创建文章接口的数据输入

!!! tip
	当然，如果你认为使用模式的方式复杂度较高，你也可以把不同接口的输入输出拆分成独立的 Schema 类
#### 动态查询字段
在博客项目中，我们需要对每个文章返回【当前用户是否喜欢】这一信息，我们依然可以利用运行时 Schema 函数的方法来处理这样的动态查询
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

我们编写的 `get_runtime` 类函数，以用户的 ID 作为输入生成相应的查询字段，这样我们在 API 函数中就可以使用 `ArticleSchema.get_runtime(user_id)`这样的方式来动态获得 Schema 类了

### 文章查询接口

我们以查询文章列表的接口为例了解如何使用 UtilMeta 编写查询接口，参考 [API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/#list-articles) 
```python
class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    result: List[ArticleSchema]
    
class ArticleAPI(API):
    # new +++
    class ListArticleQuery(orm.Query[Article]):
        tag: str = orm.Filter('tags.name')
        author: str = orm.Filter('author.username')
        favorited: str = orm.Filter('favorited_bys.username')
        offset: int = orm.Offset(default=0)
        limit: int = orm.Limit(default=20, le=100)

    async def get(self, query: ListArticleQuery) -> MultiArticlesResponse:
        schema = ArticleSchema.get_runtime(
            await self.get_user_id()
        )
        return MultiArticlesResponse(
            result=await schema.aserialize(query),
            count=await query.acount()
        )
```

我们的查询接口需要支持通过 `tag`, `author`, `favorited` 等参数过滤数据，也需要支持使用 `offset`, `limit` 来控制返回数量，可以看到我们只需要编写一个 Query 模板即可完成，其中

* `tag`：使用 `orm.Filter('tags.name')` 指定查询的目标字段，当请求的查询参数中包含 `tag` 参数时，就会增加相应的过滤查询，与 `author`, `favorited` 等字段原理一致
* `offset`：使用 `orm.Offset` 定义了一个标准的起始量字段，默认为 0
* `limit`：使用 `orm.Limit` 定义了结果的返回数量限制，默认为 20，最高为 100

!!! tip "分片控制参数"
	`offset` 和 `limit` 是 API 开发中常用的结果分片控制参数，当请求同时提供 `offset` 和 `limit` 时，最后生成的查询集用 Python 切片的方式可以表示为 `queryset[offset: offset + limit]`，这样客户端可以一次只查询结果中的一小部分，并且根据结果的数量调整下一次查询的 `offset`

`orm.Query` 模板类作为 API 函数参数的类型声明默认将自动解析请求的查询参数，它有几个常用方法

* `get_queryset()`：根据查询参数生成对应的查询集，如果你使用 Django 作为 ORM 库，那么得到的就是 Django QuerySet，这个查询集将会应用所有的过滤与分页参数，你可以直接把它作为序列化方法的输入得到对应的数据

* `count()`：忽略分页参数获取查询的总数，这个方法在分页查询时很有用，因为客户端不仅需要得到当前请求的数据，还需要得到查询对应的结果总数，这样客户端才可以正确显示分页的页数，或者知道有没有查询完毕，这个方法的异步实现为 `acount`

由于接口需要返回查询的文章总数，所以在 `get` 方法中，我们不仅调用 `schema.aserialize` 将生成的目标查询集进行序列化，还调用了 `query.acount()` 返回文章的总数，再结合 MultiArticlesResponse 中定义的响应体结构，我们就可以得到文档要求的如下响应

```json
{
    "articles": [],
    "articlesCount": 0
}
```

#### 使用钩子复用接口逻辑

我们阅读文章部分的 API 接口文档可以发现，有很多接口都有着重复的逻辑，例如

* 在 创建文章 / 更新文章 接口，都需要根据请求数据中的标题为文章生成新的 `slug` 字段
* 查询 / 更新 / 喜欢 / 取消喜欢 / 删除 接口，都需要根据 `slug` 路径参数查询对应的文章是否存在
* 查询 / 更新 /  喜欢 / 取消喜欢 / 创建 接口，都需返回目标文章对象或者新创建出的文章对象

对于这些重复的逻辑，我们都可以使用 **钩子函数** 来完成复用，示例如下
```python
class SingleArticleResponse(response.Response):
    result_key = 'article'
    result: ArticleSchema

class ArticleAPI(API):
    @api.get('/{slug}')
    async def get_article(self): pass

    @api.post('/{slug}/favorite')
    async def favorite(self): pass

    @api.delete('/{slug}/favorite')
    async def unfavorite(self): pass

    @api.put('/{slug}')
    async def update_article(self): pass

    @api.delete('/{slug}')
    async def delete_article(self): pass
        
    async def post(self): pass
 
    # new ++++
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = []
        self.article: Optional[Article] = None
        
    @api.before(get_article, favorite, unfavorite, update_article, delete_article)
    async def handle_slug(self, slug: str = request.SlugPathParam):
        article = await Article.objects.filter(slug=slug).afirst()
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article

    @api.before(post, update_article)
    async def gen_tags(self, article: ArticleSchema[orm.A] = request.BodyParam):
        for name in article.tag_list:
            slug = '-'.join([''.join(filter(str.isalnum, v)) 
                for v in name.split()]).lower()
            tag, created = await Tag.objects.aupdate_or_create(
                slug=slug, defaults=dict(name=name))
            self.tags.append(tag)

    @api.after(get_article, favorite, unfavorite, update_article, post)
    async def handle_response(self) -> SingleArticleResponse:
        if self.tags:
            # create or set tags relation in creation / update
            await self.article.tags.aset(self.tags)
        schema = ArticleSchema.get_runtime(
            await self.get_user_id()
        )
        return SingleArticleResponse(
            await schema.ainit(self.article)
        )
```

我们在例子中定义了几个钩子函数

* `handle_slug`：使用 `@api.before` 装饰器定义的预处理钩子，在使用了 `slug` 路径参数的接口执行前调用，查询出对应的文章并赋值给 `self.article`，对应的接口函数可以使用这个实例属性对目标文章直接进行访问
* `gen_tags`：在创建或更新文章接口前执行的预处理钩子，通过解析 ArticleSchema 的 `tag_list` 字段生成一系列的 tag 实例并存储在 `self.tags` 属性中
* `handle_response`：使用 `@api.after` 装饰器定义的响应处理钩子，在获取/更新/创建了单个文章对象的接口后执行，其中如果检测到 `gen_tags` 钩子生成的 `tags` 实例，则会对文章对象进行关系赋值，并且会将 `self.article` 实例使用 ArticleSchema 的动态子类进行序列化并返回

### 评论接口

接下来我们开发评论接口，从 [评论接口的 API 文档](https://realworld-docs.netlify.app/specifications/backend/endpoints/#add-comments-to-an-article) 可以发现，评论接口都是以 `/api/articles/:slug/comments` 作为路径开端的，并且路径位于文章接口的子目录，也就是说评论接口的 API 类需要挂载到文章接口的 API 类上，我们在 `domain/article/api.py` 中添加评论接口的代码

```python
from utilmeta.core import api, request, orm, response
from config.auth import API
from .models import Article, Comment
from .schema import CommentSchema

# new +++
class CommentSchema(orm.Schema[Comment]):
	id: int = orm.Field(mode='r')
	article_id: int = orm.Field(mode='a', no_input=True)
	body: str
	created_at: datetime
	updated_at: datetime
	author: ProfileSchema
	author_id: int = orm.Field(mode='a', no_input=True)
	
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

	async def get(self) -> ListResponse:
		return self.ListResponse(
			await CommentSchema.aserialize(
				Comment.objects.filter(article=self.article)
			)
		)

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
```

我们需要将评论 API 的路径配置到 `articles/{slug}/comments`，所以我们直接使用装饰器 `@api.route('{slug}/comments')` 来装饰 CommentAPI，这样当我们把 CommentAPI 挂载到 ArticleAPI 上时，就会直接将 ArticleAPI 的路径延申 `{slug}/comments` 作为 CommentAPI 的路径

评论接口路径中的 `{slug}` 是标识文章的路径参数，我们在 CommentAPI 中实现了名为 `handle_article_slug` 的预处理钩子，在接口函数执行前统一将对应的文章查询出来

!!! tip "API 公共参数"
	由于在评论 API 中，所有的接口都需要接收 `{slug}` 路径参数，我们就可以将这个参数直接声明到 API 类中，在函数中直接使用 `self.slug` 获取，这样的参数称为 API 公共参数，它们同样会被整合到生成的 API 文档中

你可以在 [这里](https://github.com/utilmeta/utilmeta-py-realworld-example-app/blob/master/conduit/domain/article/api.py) 浏览文章与评论接口的完整示例代码
## 5. 接口整合与错误处理

我们已经编写好了所有的接口，接下来只需要按照文档把它们整合在一起即可，我们使用 API 类挂载的方式为编写好的 API 接口赋予路径，打开 `service/api.py` 编写根 API 代码
```python
import utype
from utilmeta.utils import exceptions, Error
from domain.user.api import UserAPI, ProfileAPI, AuthenticationAPI
from domain.article.api import ArticleAPI
from domain.article.models import Tag
from utilmeta.core import api, response
from typing import List

class TagsSchema(utype.Schema):
	tags: List[str]

class ErrorResponse(response.Response):
	message_key = 'msg'
	result_key = 'errors'

@api.CORS(allow_origin='*')
class RootAPI(api.API):
    user: UserAPI
    users: AuthenticationAPI
    profiles: ProfileAPI
    articles: ArticleAPI
    
    @api.get
    async def tags(self) -> TagsSchema:
        return TagsSchema(
            tags=[name async for name in Tag.objects.values_list('name', flat=True)]
        )

    @api.handle('*', Exception)
    def handle_errors(self, e: Error) -> ErrorResponse:
        detail = None
        exception = e.exception
        if isinstance(exception, exceptions.BadRequest):
            status = 422
            detail = exception.detail
        else:
            status = e.status
        return ErrorResponse(detail, error=e, status=status)
```

我们声明了 `handle_errors` 错误处理钩子，使用 `@api.handle('*', Exception)` 表示会处理所有接口的所有错误，根据 [API 文档 | 错误处理](https://realworld-docs.netlify.app/specifications/backend/error-handling/) 的要求我们将校验失败的错误类型 `exceptions.BadRequest` 的响应状态码调整为 422 （默认为 400），并且通过错误实例的 `detail` 属性获取详细的报错信息

比如当我们试图访问 `GET /api/articles?limit=x` 时，响应结果就会清晰的反映出出错的参数和原因
```json
{
  "errors": {
    "name": "query",
    "field": "Query",
    "origin": {
      "name": "limit",
      "value": "x",
      "field": "Limit",
      "schema": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100
      },
      "msg": "invalid number: 'x'"
    }
  },
  "msg": "BadRequest: parse item: ['query'] failed: parse item: ['limit'] failed: invalid number: 'x'"
}
```

另外在我们编写的根 API 上使用了 `@api.CORS` 装饰器为所有的 API 接口指定了跨源策略，我们使用 `allow_origin='*'` 允许所有的前端源地址进行访问

!!! tip "CORS 跨源请求处理"
	跨域请求（或跨源请求）指的是前端浏览器的源地址（协议+域名+端口）与后端 API 的源地址不同的请求，此时浏览器使用一套 CORS 机制来进行资源访问控制
	
	UtilMeta 的 CORS 插件会自动对跨域请求做出处理，包括响应 OPTIONS 方法，根据声明和配置返回正确的 `Access-Control-Allow-Origin` 与 `Access-Control-Allow-Headers` 响应头
	
	关于 CORS 的详细说明可以参考 [这篇 MDN 文档](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/CORS)
## 6. 配置与运行

### 配置时间与连接选项
由于 API 文档给出的输出时间是类似 `"2016-02-18T03:22:56.637Z"` 的格式，我们打开 `config/conf.py`，添加时间配置的代码
```python hl_lines="19-23"
from utilmeta import UtilMeta
from config.env import env

def configure(service: UtilMeta):
	from utilmeta.ops.config import Operations
    from utilmeta.core.server.backends.django import DjangoSettings
    from utilmeta.core.orm import DatabaseConnections, Database
    from utilmeta.conf.time import Time

    service.use(DjangoSettings(
        apps_package='domain',
        secret_key=env.DJANGO_SECRET_KEY
    ))
    service.use(DatabaseConnections({
        'default': Database(
            name='conduit',
            engine='sqlite3',
        )
    }))
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%S.%fZ"
    ))
    service.use(Operations(
	    route='ops',
	    database=Database(
	        name='realworld_utilmeta_ops',
	        engine='sqlite3',
	    ),
	))
```

Time 配置类可以配置 API 使用的时区，UTC，以及输出的时间格式
### 环境变量
还记得我们在 JWT 鉴权部分引入一个名为 JWT_SECRET_KEY 的环境变量吗？我们需要设置它，否则项目无法正常运行，我们打开 `config/env.py` 可以看到我们声明的环境变量
```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

在运行前，你需要先设置这一密钥，命令可以参考如下

=== "Windows"
	```shell
	set CONDUIT_JWT_SECRET_KEY <YOUR_KEY>
	```
=== "Linux"
	```shell
	export CONDUIT_JWT_SECRET_KEY=<YOUR_KEY>
	```

### 运行项目

接下来我们就可以运行项目了，我们可以看到在项目的根目录有一个 `main.py` 文件，其中的代码如下
```python
from config.service import service

service.mount('service.api.RootAPI', route='/api')
app = service.application()

if __name__ == '__main__':
    service.run()
```

所以我们只需要执行
```shell
python main.py
```

即可运行项目，由于我们使用的是 `starlette` 作为运行时实现提供异步接口，UtilMeta 会使用 `uvicorn` 来运行项目，当你看到如下输出即可表示项目运行成功 
```
INFO:     Started server process [26428]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

我们的服务运行在本机的 8000 端口，这个设置可以在 `config/service.py` 中找到与调整
```python
from utilmeta import UtilMeta
from config.conf import configure
from config.env import env
import starlette

service = UtilMeta(
    __name__,
    name='conduit',
    description='Realworld DEMO - conduit',
    backend=starlette,
    production=env.PRODUCTION,
    version=(1, 0, 0),
    host='0.0.0.0' if env.PRODUCTION else '127.0.0.1',
    port=80 if env.PRODUCTION else 8000,
    asynchronous=True
)
configure(service)
```

!!! warning "端口冲突"
	如果你正在本地运行多个项目都使用了同一端口，你可能会看到端口冲突的报错信息
	```
	[Errno 10048] error while attempting to bind on address 
	('127.0.0.1', 8000): 通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
	```
	此时你只需要调整一下你的服务端口再重启项目即可


### 连接并管理

当你的博客服务开发好后，你可以按照 [运维与监控管理文档](../guide/ops) 来连接并观测管理你的 API 服务，UtilMeta 平台为 Realworld 案例项目也提供了一个公开的案例管理地址，你可以点击 [https://beta.utilmeta.com/realworld](https://beta.utilmeta.com/realworld) 访问


### 博客前端
博客的前端开发部署并不属于 UtilMeta 的范畴，但是教程这里简单示范如何在本地安装并运行案例中博客项目的前端代码，从而可以直接使用并调试你的 API

!!! tip
	这一小节需要你有一定的关于前端 npm 的准备知识，并需要有本地 node.js 运行环境


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

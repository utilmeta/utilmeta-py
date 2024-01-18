# 接口与用户鉴权

大多数有着 “用户” 或者 “权限” 概念的 API 服务都离不开接口和用户的鉴权，也就是根据请求的信息得出请求的权限或者所属的用户，UtilMeta 内置了一个简便的鉴权机制方便开发者快速实现鉴权功能，本篇文档将介绍相关的用法

## 用户鉴权
用户鉴权是最常见的鉴权需求，也就是将请求识别出一个用户实例，在 [用户注册登录 API](../../tutorials/user-auth) 教程中有着一步步实现 一个最简单的用户鉴权接口的方法，这一部分我们详细说明其中的用法和原理
### 用户模型
在实现用户鉴权前，我们首先要有 “用户” 这一概念，它往往是一个数据库中的用户表，所以我们首先要开发好用户表对应的用户模型，以 Django 模型为例

```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)
```

这就是一个简单的用户模型，其中定义了用户名，密码，注册时间字段

!!! tip "PasswordField"
	用户的密码字段可以使用 UtilMeta 提供的 `PasswordField` 字段，它会自动对输入的明文密码进行哈希加密

### 鉴权参数

有了用户模型，我们就可以进行鉴权参数的配置了，用户的鉴权配置通过实例化一个 `utilmeta.core.auth.User` 组件完成，例如

```python
from utilmeta.core import auth
from .models import User

user_config = auth.User(
    User,
    authentication=...,
    login_fields=User.username,
    password_field=User.password,
)
```

`auth.User` 组件中支持的参数有

* `user_model`：第一个参数，传入用户模型，比如例子中我们传入定义好的 User 类
* `authentication`：传入一个鉴权方法，比如 Session, JWT 的配置等，我们稍后介绍

**用户字段配置**

* `field`：标识用户的字段，默认是主键 ID
* `login_fields`：用于登录的字段，应该是每个用户唯一的，比如用户名，邮箱等
* `password_field`：密码字段
* `login_time_field`：记录最近登录时间的字段，可以在用户登录后自动更新
* `login_ip_field`：记录最近登录 IP 的自动，可以在用户登录后自动更新

**用户鉴权的原理**

无论是 Session 还是 JWT，实现用户鉴权的原理都是在它们存储的数据中插入一条标识当前请求用户 ID 的键值对，然后在解析请求时从其中的数据中读出，你可以使用 `auth.User` 的  `key` 参数指定标识用户的键名称，默认为 `'_user_id'`

### 在 API 中的使用

当你完成了用户鉴权配置后，你就可以在 API 函数中使用它来接收当前请求的用户对象了，比如

```python hl_lines="7"
from utilmeta.core import api, auth
from .models import User

user_config = auth.User(...)

class UserAPI(api.API):
    def get(self, user: User = user_config) -> UserSchema:
        return UserSchema.init(user)
```

你只需要把用户鉴权配置作为用户参数的默认值，即可使用这个参数接收到当前请求识别出的用户对象

当然，这样的用户参数声明也意味着请求 **必须** 能够识别出一个已登录用户，否则 UtilMeta 的鉴权组件会自动拒绝请求并返回 `401 Unauthorized` 响应，表示请求没有提供鉴权信息

那如果你要声明可选的用户鉴权，可以使用 `Optional` 声明参数类型，比如

```python hl_lines="8"
from utilmeta.core import api, auth
from .models import User
from typing import Optional

user_config = auth.User(...)

class UserAPI(api.API):
    def get(self, user: Optional[User] = user_config) -> Optional[UserSchema]:
	    if not user:
	        return None
        return UserSchema.init(user)
```

这样，如果用户未登录，接口就会返回 `null`，而如果用户已登录，则会返回使用 UserSchema 序列化的用户对象
#### 用户登录

如果你在 `auth.User` 配置中指定了 `login_fields` 和 `password_field`，就可以使用它提供的 `login` 函数快速实现登录逻辑，比如


=== "异步 API"
	```python hl_lines="20"
	import utype
	from utilmeta.utils import exceptions
	from utilmeta.core import api, auth, request
	from .models import User
	
	class LoginSchema(utype.Schema):
	    username: str
	    password: str
	
	user_config = auth.User(
	    User,
	    authentication=...,
	    login_fields=User.username,
	    password_field=User.password,
	)
	
	class UserAPI(api.API):
	    @api.post
	    async def login(self, data: LoginSchema = request.Body):
	        user = await user_config.alogin(
	            request=self.request,
	            token=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return await UserSchema.ainit(user)
	```
=== "同步 API"
	```python hl_lines="20"
	import utype
	from utilmeta.utils import exceptions
	from utilmeta.core import api, auth, request
	from .models import User
	
	class LoginSchema(utype.Schema):
	    username: str
	    password: str
	
	user_config = auth.User(
	    User,
	    authentication=...,
	    login_fields=User.username,
	    password_field=User.password,
	)
	
	class UserAPI(api.API):
	    @api.post
	    def login(self, data: LoginSchema = request.Body):
	        user = user_config.login(
	            request=self.request,
	            token=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return UserSchema.init(user)
	```

登录函数 `login` （异步方法为 `alogin`）接收的参数如下

* `request`：接收当前的请求对象，即 `self.request`
* `token`：接收用于登录的用户标识，比如用户名，邮箱等，登录字段取决于 `auth.User` 中配置的 `login_fields` 参数
* `password`：接收用户的密码（未加密）

登录函数会从你的用户表中寻找与 `token` 匹配的用户记录，并将用户输入的密码（加密后）与用户记录中的密码进行比对，如果用户存在且密码比对通过，则会将匹配的用户对象登录当前请求并返回，否则会返回 None，所以你如果检测到 `login` 函数返回的结果为 None，就可以返回 “用户名或密码错误” 的响应了

!!! tip
	对于登录接口，在请求登录失败时不建议返回详细的具体信息，比如 “用户名不存在”， “密码错误”，因为这会给暴力破解密码的攻击者提供可用的信息

**`login_user`：直接登录用户**

有时你只需要将一个用户对象登录到现有请求中即可，比如在注册时，或者使用第三方 OAuth 登录时，这时你可以使用 `auth.User` 配置的 `login_user` 函数（异步方法为 `alogin_user`）直接登录用户，比如

=== "异步 API"
	```python hl_lines="12"
	from utilmeta.core import api, auth, request
	from .models import User
	
	user_config = auth.User(...)
	
	class UserAPI(api.API):
	    @api.post
	    async def signup(self, data: LoginSchema = request.Body):
	        if await User.objects.filter(username=data.username).aexists():
	            raise exceptions.BadRequest('Username exists')
	        await data.asave()
	        await user_config.alogin_user(
	            request=self.request,
	            user=data.get_instance()
	        )
	        return await UserSchema.ainit(data.pk)
	```
=== "同步 API"
	```python hl_lines="12"
	from utilmeta.core import api, auth, request
	from .models import User
	
	user_config = auth.User(...)
	
	class UserAPI(api.API):
	    @api.post
	    def signup(self, data: LoginSchema = request.Body):
	        if User.objects.filter(username=data.username).exists():
	            raise exceptions.BadRequest('Username exists')
	        data.save()
	        user_config.login_user(
	            request=self.request,
	            user=data.get_instance()
	        )
	        return UserSchema.init(data.pk)
	```

!!! note
	将用户对象登录当前请求其实就行把用户的 ID 写入 Session 数据或者 JWT 数据中（取决于你使用的鉴权方式）

#### 用户登出

用户登出的方式取决于使用的鉴权方式

* 如果你使用 Session 进行鉴权，那么登出其实就是使用 `session.flush()` 方法清空当前 Session 数据，将在下文介绍
* 如果你使用 JWT 进行鉴权，那么其实没有 “服务端登出” 这个概念，客户端可以丢弃 token 实现用户登出，无需 API 参与

## Session 鉴权

服务端 Session 是一种常用的用户会话保持和鉴权方式，通常根据请求的 Cookie 值对应在服务端的缓存/文件/数据库中存储一个数据对象，你可以在 API 函数中根据实际的业务需要对其中的数据进行更新，这就是 Session 的原理

UtilMeta 根据 Session 的存储策略的不同，提供以下几种 Session 配置

* **缓存**：使用缓存（如 redis）作为 Session 的存储
```python
from utilmeta.core.auth.session.cache import CacheSession
```

* **数据库**：使用关系数据库作为 Session 的存储
```python
from utilmeta.core.auth.session.db import DBSession
```

* **缓存+数据库 (fallback)**：同时在缓存与数据库中存储，查询时先查询缓存，命中时直接返回，未命中或者缓存无法访问时查询数据库中的对应记录
```python
from utilmeta.core.auth.session.cached_db import CachedDBSession
```

* 文件：即将支持

### 配置 Session 参数

选择好使用哪种存储的 Session 配置后即可通过实例化来配置 Session 参数，下面是使用 `CachedDBSession` 配置的例子

```python
from utilmeta.core import auth
from utilmeta.core.auth.session.cached_db import CachedDBSession
from utilmeta.conf.http import Cookoe
from .models import Session

session_config = CachedDBSession(
	session_model=Session,
	cache_alias='default',
	cookie=Cookie(
		http_only=True,
		secure=True,
		age=3600 * 24 * 30,
	),
	save_every_request=False,
	expire_at_browser_close=False,
)

user_config = auth.User(
	authentication=session_config
)
```

Session 配置中的参数有

* `session_model`：如果存储使用了数据库（`db` / `cached_db`），则需要传入一个 Session 表对应的模型，我们稍后会介绍其中的字段
* `cache_alias`：如果存储使用了缓存（`cache` / `cached_db`），则需要传入一个缓存连接的名称，我们稍后会介绍缓存连接的配置
* `cookie`：配置 Session 的 Cookie 
* `save_every_request`：是否每次请求后都存储
* `expire_at_browser_close`：是否在用户浏览器关闭时失效

#### Session 在接口中的使用

由于 Session 的使用依赖于 Cookie 的设置和传递，你需要把 Session 设置的插件注入 API 中，这样 Session 配置才会自动处理响应并添加正确的 `Set-Cookie` 响应头，使用方式如下

```python
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(api.API):
    pass
```

只需要在一个 API 类中使用 `@session_config.plugin` 装饰器，Session 就会应用于其中定义和挂载的所有接口，所以如果你需要为服务中的所有 API 启用 Session 的话，可以直接注入到 **根 API** 上

!!! tip
	UtilMeta 使用接口注入的方式而不是全局配置来接入额外的功能（如 Session），这样你可以为不同的接口指定不同的功能配置 

那么如何在接口中获取请求对应的 session 数据呢？类似获取当前用户的用法，直接在函数参数中声明即可，例如

```python
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(API):
    @api.get
    def user_id(self, session: session_config.schema = session_config):
        return session.get('_user_id')
```

你可以使用 `session_config.schema` 获取 Session 配置对应的数据类型作为 session 参数的类型注解，并用 Session 配置作为参数的默认值

在函数中你将会得到一个 Session 数据对象，它的使用方式类似 `dict` 字典，也有一些 Session 的属性与方法

**Session 属性**

* `session_key`：获取 Session 的标识 ID
* `expiry_age`：获取 Session 的过期时间，默认是 Cookie 的 `age`
* `modified`：返回 Session 数据是否在当前请求中被修改过

**Session 方法**

* `flush()`：清空所有的 Session 数据并删除记录，也就是对应的 `sessionid` 会立即无效，可以用于 **用户登出**
* `cycle_key()`：为当前的 Session 数据替换一个新的标识 ID（保持数据不变）

这些方法也都有对应的异步方法，只需要在名称前加上 `a` 即可，如 `aflush()`, `acycle_key()`


!!! tip
	Session 配置可以传入 `auth.User` 的 `authentication` 参数用于用户鉴权，但这并不是 Session 的唯一用途，你可以配置出 Session 但仅在接口函数中使用（像上文的例子一样）

#### 配置缓存连接

UtilMeta 使用了类似 Django 语法的缓存连接配置方式，下面是配置 redis 缓存的例子
```python
from utilmeta import UtilMeta
from config.env import env

def configure(service: UtilMeta):
    from utilmeta.core.cache import CacheConnections
    from utilmeta.core.cache.backends.redis import RedisCache
    service.use(CacheConnections({
        'default': RedisCache(
            port=env.REDIS_PORT,
            db=env.REDIS_DB,
            password=env.REDIS_PASSWORD
        )
    }))
```

其中可以传入 `host`, `port`, `db`, `password` 参数来定义 redis 连接，这个连接的名称就是 `'default'`，你可以把它传入到 Session 配置的 `cache_alias` 参数中，Session 就会使用这个缓存来存储数据

#### 配置 Cookie

你可以使用 `utilmeta.conf.http.Cookie` 组件来配置 Session 中的 Cookie 行为，支持的参数有

* `name`：Cookie 的名称，在 Session 鉴权中默认为 `'sessionid'`
* `age`：指定 Cookie 的过期时间，单位是秒数
* `domain`：指定 Cookie 的域名，如果指定了一个域名例如 `utilmeta.com`，那么这个 cookie 只会对 utilmeta.com 以及类似 `ops.utilmeta.com` 这样的子域名起作用
* `path`：指定 Cookie 作用的路径（客户端显示的路径），例如当设为 `/docs` 时，只会作用于 `/docs` 与 `/docs/(.*)`

* `secure`：如果设为 True，那么 cookie 只会在 HTTPS 连接中发送
* `http_only`：如果设为 True，那么 cookie 将无法别客户端的 javascript 访问或修改，只会在 HTTP 请求中传递，对于 session cookie，为了安全建议设为 True
* `same_site`：指定是否/何时通过跨站点请求发送 cookie，有三个可能的值：`Strict`、`Lax` 和 `None`

!!! tip
	这些配置参数都对应着 Cookie 中的属性，详细的用法可以参考 [MDN - HTTP Cookie 文档](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Cookies), 配置好的 cookie 会在响应时返回，类似
	
	```
	Set-Cookie:
	sessionid=xxx; expires=Thu, 25 Jan 2024 10:04:34 GMT; HttpOnly; Max-Age=604800; Path=/; SameSite=Lax
	```
### Session 模型与扩展

对于使用数据库存储的 Session 鉴权，比如 `DBSession` 或 `CachedDBSession`，需要指定一个 Session 模型来完成与数据库的交互，UtilMeta 已经提供了一个 Session 基类供你继承，其中包含了基本的字段如下

```python
class AbstractSession(AwaitableModel):
    session_key = models.CharField(max_length=60, unique=True)
    encoded_data = models.TextField(null=True)
    
    created_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=None, null=True)
    expiry_time = models.DateTimeField(default=None, null=True)
    deleted_time = models.DateTimeField(default=None, null=True)    # already expired

    class Meta:
        abstract = True
```

* `session_key`：存储 session 的访问标识，即 Cookie 中携带的 `sessionid`
* `encoded_data`：存储编码后的 Session 数据
* `created_time`：Session 的创建时间
* `last_activity`：Session 最近的使用时间
* `expiry_time`：Session 的过期时间
* `deleted_time`：Session 的删除时间，默认为 None，当 Session 删除时会将此字段置为删除的时间，之后就不会被查询到，但可以用于数据留底

继承这个 Session 基类以后，你可以扩展其中的字段，比如记录 session 的 IP，用户 ID 等，例如

```python
from utilmeta.core.orm.backends.django.models import AbstractSession

class Session(AbstractSession):
    user = models.ForeignKey(
        User, on_delete=amodels.ACASCADE, 
        related_name='sessions', 
        default=None, null=True
    )
    ip = models.GenericIPAddressField(default=None, null=True)

    class Meta:
        db_table = 'session'
```

当你扩展了 Session 数据时，当然需要在存储 Session 时为你增加的字段传入数据，你可以使用如下的方式
```python hl_lines="15"
from utilmeta.core.auth.session.cached_db import CachedDBSession, CachedDBSessionSchema
from .models import Session

class SessionSchema(CachedDBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(
            user_id=self.get('_user_id'),
            ip=str(self._request.ip_address),
        )
        return data

session_config = CachedDBSession(
	session_model=Session,
	engine=SessionSchema,
	...
)
```

对于所有的 XXSession 配置都有一个对应的 XXSessionSchema 实现了对应的存储引擎，通过继承其中的 `get_session_data` 你就可以添加自定义的字段数据，比如例子中我们演示了如何添加【当前请求用户 ID】与 【当前请求 IP】的字段，在这个方法中，你可以使用 `self._request` 获取运行时的请求对象

在继承了 SessionSchema 类后，要记得把新的类传递给 Session 配置的 `engine` 参数

### 声明 Session 数据

如果你的服务端 Session 数据有着确定的字段名称和类型的话，你可以把它们声明出来，这样即可以利用 IDE 的属性提示方便开发，又可以避免 Session 中出现脏数据，下面是一个使用 Session 声明数据进行 Email 验证码校验的接口例子

```python
import utype
import random
from typing import Optional
from utilmeta.core import api, request
from .auth import session_config

class EmailSessionSchema(session_config.schema):
    email: Optional[str] = utype.Field(default=None, defer_default=True)
    code: Optional[str] = utype.Field(default=None, defer_default=True)
    verified: bool = utype.Field(default=False, defer_default=True)

class EmailAPI(api.API):
    @api.post
    def send_code(self, session: EmailSessionSchema, email: str = request.BodyParam):
        session.email = email
        session.code = str(random.randint(1000, 9999))
        # send mail
        session.expiry = self.request.time + timedelta(seconds=300)
        
    @api.post
    def verify_code(self, session: EmailSessionSchema,
                    email: str = request.BodyParam,
                    code: str = request.BodyParam):
        if session.email == email and session.code == code:
            session.verified = True
            session.expiry = None
            return True
        return False
```

在 session 配置中有一个 `schema` 属性可以访问其对应的 Schema 类，我们可以通过继承 `session_config.schema` 来自定义 Session 数据，比如例子中的 EmailSessionSchema

其中我们定义了 `email`, `code`,  `verified` 字段，可以在 API 函数中直接访问与赋值，例子中就使用了了这些字段实现了邮箱验证码的发送和校验功能

除此之外，SessionSchema 还内置了一个 `expiry` 属性，你可以通过赋值来调整 Session 的过期时间，它可以接受 `datetime` 或者能转化为 `datetime` 类型的时间戳与字符串，在 `send_code` 接口中，我们将发送邮件后的 Session 过期时间设为请求时间后的 300 秒，也就是 5 分钟后这个会话就会过期，请求就需要重新发送验证码

你可以通过把 `expiry` 设为 None 从而使这个 Session 不过期，在 `verify_code` 接口中，当验证码校验成功时，我们把 `expiry` 设为 None 从而使得这个校验成功的状态可以保持，但是实际上 Session 是否过期也取决于 Cookie 的 `age`，当 Cookie 到期后客户端会丢弃相应的 Cookie 键值对从而使得之后的请求无法访问到对应的 Session 数据

!!! tip
	Session 中的 Schema 类其实继承自 `utype.Schema`，所以其用法与 [utype 中的 Schema](https://utype.io/zh/guide/cls/) 是一致的

**教程参考**

在 [用户注册登录 API](../../tutorials/user-auth) 教程中，有使用 Session 鉴权实现一个最简单的用户鉴权接口的过程可以参考

## JWT 鉴权

Json Web Token (JWT) 技术也是一种常用的鉴权方式，它通过一个把包含用户标识的数据使用密钥加密后的 token 来实现鉴权，一般使用请求的 `Authorization` 请求头携带，比如

```
Authorization: Bearer JWT_TOKEN_VALUE
```

配置 JWT 鉴权的方式如下

```python
from .env import env
from utilmeta.core import auth
from utilmeta.core.auth import jwt
from domain.user.models import User

user_config = auth.User(
	User,
	authentication=jwt.JsonWebToken(
		key=env.JWT_SECRET_KEY,
		user_token_field=User.token
	),
)
```

我们使用 `utilmeta.core.auth.jwt.JsonWebToken` 来配置 JWT 鉴权，支持的参数有

* `key`：必填项，传入一个 JWT 密钥，用于数据的加密和解密，这个密钥很重要，应当慎重管理，理论上如果泄露的话客户端可以构造任意权限的请求
* `algorithm`：JWT 加密算法，默认为 `'HS256'`
* `audience`：JWT 的受众字符串，如果指定则会写入 JWT 的 `'aud'` 字段，并在解密时进行校验，如果 `audience`不符合 JWT 的要求，则会返回 403 响应
* `user_token_field`：你可以指定一个用户模型中的字段，每当为用户生成新的 JWT 时，都将会更新到用户的对应字段

!!! tip
	合理指定 `audience` 可以避免在 JWT 用于不属于它权限访问的接口


**教程参考**

在 [Realworld 博客项目](../../tutorials/realworld-blog) 教程中，有使用 JWT 鉴权实现博客应用的 API 的过程可以参考

## 其他鉴权方式

即将支持的鉴权方式

* HTTP Basic Auth
* Signature Auth (数字签名)
* OAuth2

### 自定义鉴权方式

如果你不满足于 UtilMeta 提供的标准鉴权方式，也可以自行定义鉴权方式，用法如下

```python
from utilmeta.core.auth.base import BaseAuthentication
from utilmeta.core.request import Request

class CustomAuth(BaseAuthentication):
    def getter(self, request: Request):
        pass
```

其中 `getter` 函数只需要接收当前请求对象作为参数，然后返回当前用户 ID 的值即可，其中可以实现你自行定义的鉴权逻辑

然后再将你自定义的鉴权类 `CustomAuth` 实例化并传入 `auth.User` 的 `authentication` 参数中即可

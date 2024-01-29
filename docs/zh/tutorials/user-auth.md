# 用户注册登录 API

这个案例我们将会用 UtilMeta 搭建起一个提供用户注册，登录，查询，修改信息的 API，这样的接口是大多数应用的标配，我们也会学习到如何使用 UtilMeta 处理数据库查询与鉴权

!!! abstract "技术选型"

	* 使用 Django 作为 HTTP 与 ORM backend
	* 使用 SQLite 作为数据库
	* 使用 Session 来处理用户的登录状态

## 1. 创建项目

我们使用 `meta setup` 命令来创建一个新项目
```shell
meta setup demo-user
```
在提示选择 backend 的时候输入 `django`

项目创建好后，我们需要先对服务的数据库连接进行配置，打开 `server.py`，插入以下代码

```python
service = UtilMeta(...)

# new +++++
from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database

service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
))

service.use(DatabaseConnections({
    'default': Database(
        name='db',
        engine='sqlite3',
    )
}))
```

在插入的代码中，我们声明了 Django 的配置信息与数据库连接的配置
由于 Django 使用 app (应用) 的方式来管理数据模型，接下来我们使用如下的命令来创建一个名为 `user` 的 app 

```shell
meta add user
```

可以看到在我们的项目文件夹中新创建出了一个 `user` 文件夹，其中包括
```
/user
    /migrations
    api.py
    models.py
    schema.py
```

其中 `migrations` 文件夹是 Django 用来处理数据库迁移文件的，`models.py` 是我们编写数据模型的地方

应用创建完成后，我们将 `server.py` 的 Django 设置中插入一行代码来指定 app 

```python
service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
    apps=['user']     # new
))
```

至此我们完成了项目的配置和初始化

## 2. 编写用户模型

用户的登录注册 API 当然是围绕 “用户” 进行的了，在开发 API 之前，我们先来编写用户的数据模型，我们打开 `user/models.py`，编写
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import AbstractSession, PasswordField

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)

class Session(AbstractSession):
    user = models.ForeignKey(
        User, related_name='sessions', 
        null=True, default=None, 
        on_delete=models.CASCADE
    )
```

可以看到除了 User 模型外，我们还编写了一个用户记录用户会话和登录状态的 Session 模型，我们将通过这个模型实现用户的登录与鉴权

!!! tip "PasswordField"
	用户模型的 `password` 字段使用的 PasswordField 会自动对输入的明文密码进行哈希加密，如果你希望自行实现密码的加密与校验，也可以使用 CharField 字段声明

### 初始化数据库

当我们编写好数据模型后即可使用 Django 提供的迁移命令方便地创建对应的数据表了，由于我们使用的是 SQLite，所以无需提前安装数据库软件，只需要运行以下两行命令即可完成数据库的创建

```shell
meta makemigrations
meta migrate
```

当看到以下输出时即表示你已完成了数据库的创建

```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying user.0001_initial... OK
```

数据库迁移命令根据 `server.py` 中的数据库配置，在项目文件夹中创建了一个名为 `db` 的 SQLite 数据库，其中已经完成了 User 和 Session 模型的建表

## 3. 配置 Session 与用户鉴权

编写完用户鉴权相关的模型，我们就可以开始开发鉴权相关的逻辑了，我们在 user 文件夹中新建一个 `auth.py` 文件，编写 Session 与用户鉴权的配置
```python
from utilmeta.core import auth
from utilmeta.core.auth.session.db import DBSessionSchema, DBSession
from .models import Session, User

USER_ID = '_user_id'

class SessionSchema(DBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(user_id=self.get(USER_ID))
        return data

session_config = DBSession(
    session_model=Session,
    engine=SessionSchema,
    cookie=DBSession.Cookie(
        name='sessionid',
        age=7 * 24 * 3600,
        http_only=True
    )
)

user_config = auth.User(
    user_model=User,
    authentication=session_config,
    key=USER_ID,
    login_fields=User.username,
    password_field=User.password,
)
```

在这段代码中，SessionSchema 是处理和存储 Session 数据的核心引擎，`session_config` 是声明 Session 配置的组件，定义了我们刚编写的 Session 模型以及引擎，并且配置了相应的 Cookie 策略

!!! tip
	为了简化案例，我们选择了基于数据库的 Session 实现（DBSession），实际开发中，我们常常使用 Redis 等缓存作为 Session 的存储实现，或者使用 缓存+数据库 的方式，这些实现方式 UtilMeta 都支持，你可以在 [Session 鉴权文档](../../guide/auth/#session) 中找到更多的使用方式


另外在代码中我们也声明了 `user_config` 用户鉴权配置，其中的参数

* `user_model`：指定鉴权的用户模型，就是我上一节中编写好的 User 模型
* `authentication`：指定鉴权策略，我们传入 `session_config` 来声明用户鉴权使用 Session 进行
* `key`：在 Session 数据中保存当前用户 ID 的名称
* `login_fields`：能用于登录的字段，如用户标识名，邮箱等，需要是唯一的
* `password_field`：用户的密码字段，声明这些可以让 UtilMeta 自动帮你处理登录校验逻辑

## 4. 编写用户 API

### 注册接口

我们首先来编写用户的注册接口，注册接口应该接收用户名，密码字段，校验用户名没有被占用后完成注册，并返回新注册的用户数据

我们打开 `user/api.py` 编写注册接口

```python
from datetime import datetime
from utilmeta.core import api, orm
from utilmeta.utils import exceptions
from .models import User
from . import auth

class SignupSchema(orm.Schema[User]):
    username: str
    password: str
    
class UserSchema(orm.Schema[User]):
    id: int
    username: str
    signup_time: datetime

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self, data: SignupSchema = request.Body) -> UserSchema:
        if User.objects.filter(username=data.username).exists():
            raise exceptions.BadRequest('Username exists')
        data.save()
        auth.user_config.login_user(
            request=self.request,
            user=data.get_instance()
        )
        return UserSchema.init(data.pk)
```
注册接口中的逻辑为

1. 检测请求中的 `username` 是否已被注册
2. 调用 `data.save()` 方法保存数据
3. 为当前请求使用 `login_user` 方法登录新注册的用户
4. 使用 `UserSchema.init(data.pk)` 将新用户的数据初始化为 UserSchema 实例后返回

!!! abstract "声明式 ORM"
	UtilMeta 开发了一套高效的声明式 ORM 查询体系，也可以称为 Schema Query, 我们在声明 Schema 类时便使用 `orm.Schema[User]` 绑定了模型，这样我们就可以通过  Schema 类的方法来实现数据的增删改查了，你可以在 [数据查询与 ORM 文档](../../guide/schema-query) 中查看它的更多用法

另外我们发现在 UserAPI 类被施加了 `@auth.session_config.plugin` 这一装饰器插件，这是 Session 配置应用到 API 上的方式，这个插件能在每次请求结束后对请求所更新的 Session 数据进行保存，并返回对应的 `Set-Cookie`

### 登录登出接口

接下来我们编写用户的登录与登出接口

```python
from datetime import datetime
from utilmeta.core import api, orm, request
from utilmeta.utils import exceptions
from .models import User
from . import auth
import utype

class LoginSchema(utype.Schema):
    username: str
    password: str

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self): ...

    # new ++++
    @api.post
    def login(self, data: LoginSchema = request.Body) -> UserSchema:
        user = auth.user_config.login(
            request=self.request,
            ident=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('Username of password wrong')
        return UserSchema.init(user)

    @api.post
    def logout(self, session: auth.SessionSchema = auth.session_config):
        session.flush()
```

在登录接口中，我们直接调用了鉴权配置中的 `login()` 方法来完成登录，由于我们已经配置好了登录字段与密码字段，UtilMeta 可以自动帮我们完成密码校验与登录，如果成功登录，便返回相应的用户实例
所以当返回为空时，我们便抛出错误返回登录失败，而成功登录后，我们调用 `UserSchema.init` 放将登录的用户数据返回给客户端

!!! tip
	这样简化的登录方式并不是强制的，如果你希望更自由的控制登录，可以自行实现相应的逻辑

而对于登出接口，我们只需拿到当前的 session，并将其中的数据清空即可，我们这里调用的是 `session.flush()` 清空数据 

!!! tip
	在配置 Session 后，你在任意接口都可以使用类似示例中的 `logout` 接口的方式拿到当前的 Session 数据，你得到的就是你声明的 SessionSchema 实例，你可以像操作其他 Schema 实例或者字典一样操作它

### 用户信息的获取与更新

当我们了解了 Schema Query 的用法后，编写用户信息的获取与更新接口就非常简单了，如下
```python
from datetime import datetime
from utilmeta.core import api, orm, request
from utilmeta.utils import exceptions
from .models import User
from . import auth
import utype

class UserUpdateSchema(orm.Schema[User]):
    id: int = orm.Field(no_input=True)
    username: str = orm.Field(required=False)
    password: str = orm.Field(required=False)

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self): ...
    @api.post
    def login(self): ...
    @api.post
    def logout(self): ...

    # new ++++
    def get(self, user: User = auth.user_config) -> UserSchema:
        return UserSchema.init(user)

    def put(self, data: UserUpdateSchema = request.Body, 
            user: User = auth.user_config) -> UserSchema:
        data.id = user.pk
        data.save()
        return UserSchema.init(data.pk)
```

当我们声明了用户鉴权配置后，在任何一个需要用户登录才能访问的接口，我们都可以在接口参数中声明 `user: User = auth.user_config` 从而拿到当前请求用户的实例，如果请求没有登录，则 UtilMeta 会自动处理并返回 `401 Unauthorized`

在 `get` 接口中，我们直接将当前的请求用户的数据用 `UserSchema` 初始化并返回给客户端
在 `put` 接口中，我们将当前用户的 ID 赋值给接收到 UserUpdateSchema 实例的 `id` 字段，然后保存并返回更新后的用户数据

由于我们不能允许请求用户任意指定要更新的用户 ID，所以对于请求数据的 `id` 字段我们使用了 `no_input=True` 的选项，这其实也是一种常见的权限策略，即一个用户只能更新自己的信息

!!! tip "API 核心方法"
	当你的函数直接使用 get/put/patch/post/delete 等 HTTP 动词进行命名时，它们就会自动绑定对应的方法，路径与 API 类的路径保持一致，这些方法称为这个 API 类的核心方法

至此我们的 API 就全部开发完成了
### 整合 API

为了使我们开发的 UserAPI 能够提供访问，我们需要把它 挂载 到服务的根 API 上，我们回到 `server.py`，修改 RootAPI 的声明
```python  hl_lines="6"
# new +++
service.setup()
from user.api import UserAPI

class RootAPI(api.API):
    user: UserAPI
	
service.mount(RootAPI, route='/api')
```

我们将开发好的 UserAPI 挂载到了 RootAPI 的 `user` 属性，意味着 UserAPI 的路径被挂载到了 `/api/user`

!!! tip
	对于使用 Django 的 API 服务，请在导入任何模型或 API 前加入 `service.setup()`，这样 django 才能正确识别所有的数据模型

## 5. 运行 API

在项目文件夹中使用如下命令即可将 API 服务运行起来
```
meta run
```

或者你也可以使用
```shell
python server.py
```

当你看到如下输出时表示服务已成功启动

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

!!! tip
	你可以通过调整 `server.py` 中的 UtilMeta 服务声明里的 `host` 和 `port` 参数来改变 API 服务监听的地址

## 6. 调试 API

启动好 API 服务后我们就可以调试我们的接口了，我们可以使用 UtilMeta 自带的客户端测试工具方便地调试接口，我们在项目目录中新建一个 `test.py` 文件，写入调试 API 的代码

```python
from server import service

if __name__ == '__main__':
    with service.get_client(live=True) as client:
        r1 = client.post('user/signup', data={
            'username': 'user1',
            'password': '123123'
        })
        r1.print()
        r2 = client.get('user')
        r2.print()
```

其中编写了用户注册接口和获取当前用户接口的调试代码，当我们启动服务并运行 `test.py` 时，我们可以看到的输出类似

```json
Response [200 OK] "POST /api/user/signup"
application/json (76)
{'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T12:29:33.684594'}

Response [200 OK] "GET /api/user"
application/json (76)
{'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T12:29:33.684594'}
```

这说明我们的注册接口和获取用户的接口开发成功，首先注册接口返回了正确的结果，然后注册接口登录了新注册的用户，所以之后访问用户获取接口也得到了同样的结果

!!! tip
	在 `with` 代码块中，客户端会记忆响应中 `Set-Cookie` 所存储的 cookies 并发送到接下来的请求中，所以我们可以看到与真实的浏览器类似的会话效果

UtilMeta 服务实例的 `get_client` 方法用于获取一个服务的客户端实例，你可以直接调用这个实例的 `get`, `post` 等方法发起 HTTP 请求，将会得到一个 `utilmeta.core.response.Response` 响应，这与我们在 API 服务中生成的响应类型一致，其中常用的属性有

* `status`：响应的状态码
* `data`：解析后的响应数据，如果是 JSON 响应体，则会得到一个 `dict` 或 `list` 类型的数据
* `headers`：响应头
* `request`：响应对应的请求对象，有请求的方法，路径等参数信息

!!! tip
	`get_client` 方法中的 `live` 参数如果没有开启，则是直接调用对应的接口函数进行调试，无需启动服务

所以你也可以使用这个客户端编写单元测试，比如
```python
from server import service

def test_signup():
    with service.get_client(live=True) as client:
        r1 = client.post('user/signup', data={
            'username': 'user1',
            'password': '123123'
        })
        assert r1.status == 200
        assert isinstance(r1.data, dict)
        assert r1.data.get('username') == 'user1'
```

我们还可以测试登录，登出与更新接口，比如在登出后 cookies 应该被清空，之后获取当前用户也应该返回空，最后完整的调试代码与对应的输出如下
```python
from server import service

if __name__ == '__main__':
    with service.get_client(live=True) as client:
        r1 = client.post('user/signup', data={
            'username': 'user1',
            'password': '123123'
        })
        r1.print()
        # Response [200 OK] "POST /api/user/signup"
        # application/json (75)
        # {'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T13:29:03.336134'}
        r2 = client.get('user')
        r2.print()
        # Response [200 OK] "GET /api/user"
        # application/json (75)
        # {'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T13:29:03.336134'}
        r3 = client.post('user/logout')
        r3.print()
        # Response [200 OK] "POST /api/user/logout"
        # text/html (0)
        r4 = client.get('user')
        r4.print()
        # Response [401 Unauthorized] "GET /api/user"
        # text/html (0)
        r5 = client.post('user/login', data={
            'username': 'user1',
            'password': '123123'
        })
        # Response [200 OK] "POST /api/user/login"
        # application/json (75)
        # {'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T13:29:03.336134'}
        r5.print()
        r6 = client.get('user')
        r6.print()
        # Response [200 OK] "GET /api/user"
        # application/json (75)
        # {'username': 'user1', 'id': 1, 'signup_time': '2024-01-29T13:29:03.336134'}
        r7 = client.put('user', data={
            'username': 'user-updated',
            'password': '123456'
        })
        r7.print()
        # Response [200 OK] "PUT /api/user"
        # application/json (82)
        # {'username': 'user-updated', 'id': 1, 'signup_time': '2024-01-29T13:44:30.095711'}
```

## 案例源码

本案例的源码可以参考 [github](https://github.com/utilmeta/utilmeta-py/tree/main/examples/user_auth)

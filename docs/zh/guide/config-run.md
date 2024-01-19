# 配置运行与部署

本篇文档将介绍如何配置和运行 UtilMeta 项目，以及在生产环境中的部署

## 服务初始化参数

```python
from utilmeta import UtilMeta

service = UtilMeta(__name__, ...)
```

UtilMeta 服务的第一个参数接收当前模块的名称（`__name__`），此外支持的参数有

* `backend`：传入运行时框架的模块或者名称，如 `backend='flask'`
* `name`：服务的名称，应该反映着服务的领域和业务，之后会用户服务的注册，发现与检测等功能
* `description`：服务的描述
* `production`：是否处于生产状态，默认为 False，在部署的生产环境中应该置为 True，找个参数会影响底层框架的运行配置，比如 `django` 的 `PRODUCTION` 设置，与 flask / starlette / fastapi / sanic 的 `debug` 参数

* `host`：服务运行时监听的主机 IP，默认为 `127.0.0.1`，也可以设置为运行主机的 IP 或者 `0.0.0.0` (公开访问)
* `port`：服务运行时监听的端口号，默认取决于运行时框架，比如 flask 使用的是 `5000`，其他框架一般使用的是 `8000`

* `version`：指定服务当前的版本号，你可以传入一个字符串，如 `'1.0.2'`，也可以传入一个元组，比如 `(0, 1, 0)`，版本号的规范建议遵守 [语义版本标准](https://semver.org/)
* `asynchronous`：强制指定服务是否提供异步接口，默认由运行时框架的特性决定
* `api`：传入 UtilMeta 的根 API 类或它的引用字符串 
* `route`：传入 UtilMeta 的根 API 挂载的路径字符串，默认为 `'/'`，即挂载到根路径

当你初始化 UtilMeta 后，除了直接导入外，你还可以用这种方式导入当前进程的 UtilMeta 服务实例

```python
from utilmeta import service
```

!!! warning
	一个进程中只能定义一个 UtilMeta 服务实例

### 选择 `backend` 框架

目前 UtilMeta 内置支持的运行时框架有

* `django`
* `flask`
* `starlette`
* `fastapi`
* `sanic`
* `tornado`

!!! tip
	如果你还希望支持更多的运行时框架实现，请在 UtilMeta 框架的 [Issues](https://github.com/utilmeta/utilmeta-py/issues) 中提出

你使用 `backend` 参数指定的框架需要先安装到你的 Python 环境中，然后你可以使用类似如下的方式将包导入后传入 `backend` 参数

=== "django"
	```python hl_lines="7"
	import django
	from utilmeta import UtilMeta
	
	service = UtilMeta(
		__name__, 
		name='demo',
		backend=django
	)
	```
=== "flask"
	```python hl_lines="7"
	import flask
	from utilmeta import UtilMeta
	
	service = UtilMeta(
		__name__, 
		name='demo',
		backend=flask
	)
	```
=== "starlette"
	```python hl_lines="7"
	import starlette
	from utilmeta import UtilMeta
	
	service = UtilMeta(
		__name__, 
		name='demo',
		backend=starlette
	)
	```
=== "sanic"
	```python hl_lines="7"
	import sanic
	from utilmeta import UtilMeta
	
	service = UtilMeta(
		__name__, 
		name='demo',
		backend=sanic
	)
	```
#### 注入自定义应用

一些运行时框架往往会提供开发者一个同名的应用类，比如 `Flask`, `FastAPI`, `Sanic`，其中可以定义一些初始化参数，如果你需要对其中的参数进行配置，则可以把定义出的应用实例传入 `backend` 参数，比如

```python
from fastapi import FastAPI

fastapi_app = FastAPI(debug=False)

service = UtilMeta(
    __name__,
    name='demo',
    backend=fastapi_app,
)
```

!!! tip
	你还可以使用这种方式在 UtilMeta 框架项目中接入其他运行时框架的接口，详细的用法可以参考 [从现有项目迁移](../migration) 这篇文档

### 异步服务

不同的运行时框架对于异步的支持程度不同，如果没有显式指定 `asynchronous` 参数，服务接口是否为异步取决于各自的特性，如
 
* **Django**：同时支持 WSGI 与 ASGI，但是 `asynchronous` 默认为 False
!!! tip
	对于使用 Django 作为 `backend` 的服务，如果开启 `asynchronous=True` 则会得到一个 ASGI 应用，否则会得到一个 WSGI 应用

* **Flask**：支持 WSGI，处理异步函数需要将其先转化为同步函数，`asynchronous` 默认为 False
* **Sanic**：支持 ASGI，`asynchronous` 默认为 True
* **Tornado**：自行基于 `asyncio` 实现了 HTTP Server，`asynchronous` 默认为 True
* **Starlette/FastAPI**：支持 ASGI，`asynchronous` 默认为 True

如果你希望编写异步（`async def` ）接口，请选择一个默认支持异步的运行时框架，这样可以发挥出你的异步接口的性能，如果你选择的运行时框架默认不启用异步（如 `django` / `flask`），则需要开启  `asynchronous=True` 选项，否则将无法执行其中的异步函数

## 服务的方法与钩子

实例化的 UtilMeta 服务还有一些方法或钩子可以使用

### `use(config)` 注入配置

服务实例的 `use` 方法可以用于注入配置，例如
```python
from utilmeta import UtilMeta
from config.env import env

def configure(service: UtilMeta):
    from utilmeta.core.server.backends.django import DjangoSettings
    from utilmeta.core.orm import DatabaseConnections, Database
    from utilmeta.conf.time import Time

    service.use(DjangoSettings(
        apps_package='domain',
        secret_key=env.DJANGO_SECRET_KEY
    ))
    service.use(DatabaseConnections({
        'default': Database(
            name='db',
            engine='sqlite3',
        )
    }))
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%S.%fZ"
    ))
```

UtilMeta 内置的常用配置有

* `utilmeta.core.server.backends.django.DjangoSettings`：配置 Django 项目，如果你的服务以 Django 作为运行时框架，或者需要使用 Django 模型的话就需要使用这个配置项
* `utilmeta.core.orm.DatabaseConnections`：配置数据库连接
* `utilmeta.core.cache.CacheConnections`：配置缓存连接
* `utilmeta.conf.time.Time`：配置服务的时区与接口中的时间格式

!!! warning
	一个类型的配置只能使用 `use` 注入一次


### `setup()` 配置的安装

一些服务的配置项需要在服务启动前进行安装与准备，比如对于使用 Django 模型的服务，`setup()` 会调用 `django.setup` 函数完成模型的发现，你需要在调用这个方法之后才能导入你定义的  Django 模型以及依赖这些模型的接口与 Schema 类，比如

```python
from utilmeta import UtilMeta
from config.conf import configure 
import django

service = UtilMeta(..., backend=django)
configure(service)
service.setup()

from user.models import *
```

否则会出现类似如下的错误
```python
django.core.exceptions.ImproperlyConfigured: 
Requested setting INSTALLED_APPS, but settings are not configured, ...	
```

当然对于使用 Django 的项目，最佳实践是使用引用字符串来指定根 API，这样在服务配置文件中就不需要包含对 Django 模型的导入了，例如

=== "main.py"  
	```python
	from utilmeta import UtilMeta
	import django
	
	service = UtilMeta(
		__name__,
	    name='demo',
	    backend=django,
		api='service.api.RootAPI',
		route='/api',
	)
	```
=== "service/api.py"  
	```python
	from utilmeta.core import api
	
	class RootAPI(api.API):
	    @api.get
	    def hello(self):
	        return 'world'
	```

### `application()` 获取 WSGI/ASGI 应用

你可以通过调用服务的 `application()` 方法返回它生成的 WSGI / ASGI 应用，比如在 Hello World 示例中

```python hl_lines="18"
from utilmeta import UtilMeta
from utilmeta.core import api
import django

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=django,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    service.run()
```

这个生成的 `app` 的类型取决于服务实例指定的 `backend` ，如

* `flask`: 返回一个 Flask 实例
* `starlette`：返回一个 Starlette 实例
* `fastapi`：返回一个 FastAPI 实例
* `sanic`：返回一个 Sanic 实例
* `django`：默认返回一个 WSGIHandler，如果指定了 `asynchronous=True`，则会返回一个 ASGIHandler
* `tornado`：返回一个 `tornado.web.Application` 实例

如果你使用 uwsgi 和 gunicorn 等 WSGI 服务器部署 API 服务的话，其中都需要指定一个 WSGI 应用，你只需要将对应的配置项设为 `app` 的引用即可，比如

=== "gunicorn.py"
	```python
	wsgi_app = 'server:app'
	```
=== "uwsgi.ini"
	```ini
	[uwsgi]
	module = server.app
	```

!!! warning "使用 `sanic`"
	当你使用 `sanic` 作为运行时框架时，即使不使用 WSGI 服务器，也需要在启动服务的文件中声明 `app = service.application()`，因为  `sanic` 会启动新的进程来处理请求，如果没有 `application()` 对接口的加载，新的进程将检测不到任何路由

### `@on_startup` 启动钩子

你可以使用服务实例的 `@on_startup` 装饰器装饰一个启动钩子函数，在服务进程启动前调用，可以用于进行一些服务的初始化操作，如

```python hl_lines="10"
from utilmeta import UtilMeta
import starlette

service = UtilMeta(
    __name__,
    name='demo',
    backend=starlette,
)

@service.on_startup
async def on_start():
    import asyncio
    print('prepare')
    await asyncio.sleep(0.5)
    print('done')
```

对于支持异步的 `backend` 框架，如 Starlette / FastAPI / Sanic / Tornado，你可以使用异步函数作为启动钩子函数，否则你需要使用同步函数，比如 Django / Flask

### `@on_shutdown` 终止钩子

你可以使用服务实例的 `@on_shutdown` 装饰器装饰一个终止钩子函数，在服务进程结束前调用，可以用于进行一些服务进程的清理操作，如

```python hl_lines="10"
from utilmeta import UtilMeta
import starlette

service = UtilMeta(
    __name__,
    name='demo',
    backend=starlette,
)

@service.on_shutdown
def clean_up():
    # clean up
    print('done!')
```

## 环境变量管理

在实际后端开发中，你往往需要使用很多密钥，比如数据库密码，第三方应用密钥，JWT 密钥等等，这些信息如果硬编码到代码中有泄露的风险，很不安全，并且这些密钥信息在开发，测试和生产环境中也往往有着不同的配置，所以更适合使用环境变量来管理

UtilMeta 提供了一个内置环境变量组件 `utilmeta.conf.Env` 便于你管理这些变量与密钥信息，使用的方式如下

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    DJANGO_SECRET_KEY: str = ''
    COOKIE_AGE: int = 7 * 24 * 3600

    # cache -----
    REDIS_DB: int = 0
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str

    # databases ---------
    DB_HOST: str = ''
    DB_USER: str  
    DB_PASSWORD: str
    DB_PORT: int = 5432

env = ServiceEnvironment(sys_env='DEMO_')
```

通过继承 `utilmeta.conf.Env` 类，你可以在其中声明服务需要的环境变量，环境变量在解析时会忽略大小写，但我们建议使用大写的方式与其他属性进行区分，你可以为每个变量声明类型与默认值，`Env` 会将变量转化为你声明的类型，在获取不到对应的变量时使用你指定的默认值

`Env` 子类在实例化时可以指定环境变量的来源，如

### `sys_env` 系统环境变量

你可以指定一个前缀，从而会在系统环境变量中拾取 **前缀+名称** 的变量，比如例子中指定的前缀为 `'DEMO_'`，那么系统环境变量中的 `DEMO_DB_PASSWORD` 将会被解析为环境变量数据中的 `DB_PASSWORD` 属性

如果你不需要指定任何前缀，可以使用 `sys_env=True` 
### `file` 配置文件

除了从系统环境变量中拾取外，你还可以使用 `file` 参数指定一个 JSON 或 INI 格式的配置文件

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    pass

env = ServiceEnvironment(file='/path/to/config.json')
```

在文件中声明对应的环境变量，如

=== "json"
	```json
	{
	    "DB_USER": "my_user",
	    "DB_PASSWORD": "my_password"
	}
	```
=== "ini"
	```ini
	DB_USER=my_user
	DB_PASSWORD=my_password
	```

!!! tip
	如果你使用的是配置文件，请把配置文件放在项目目录之外，或者在 `.gitignore` 中把它从版本管理中排除

## 运行服务

UtilMeta 服务实例提供了一个 `run()` 方法用于运行服务，我们已经看到过它的用法了
```python hl_lines="21"
from utilmeta import UtilMeta
from utilmeta.core import api
import django

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=django,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    service.run()
```

我们一般在 ` __name__ == '__main__'` 的版块内调用 `service.run()`，这样你就可以通过使用 python 执行这一文件从而运行服务，例如

```
python server.py
```

 `run()` 方法会根据服务实例的 `backend` 执行对应的运行策略，比如

* **Django**：通过调用 `runserver` 命令运行服务，不建议在生产环境中使用
* **Flask**：直接调用 Flask 应用的 `run()` 方法运行服务 
* **Starlette/FastAPI**：将使用 `uvicorn` 运行服务
* **Sanic**：直接调用 Sanic 应用的 `run()` 方法运行服务 
* **Tornado**：使用 `asyncio.run` 运行服务

### 自定义运行

对于 Flask, Sanic 等框架，你可以通过 `service.application()` 获取到生成的 Flask 应用与 Sanic 应用，所以你也可以直接调用它们的 `run()` 方法从而传入对应框架支持的参数

```python hl_lines="21"
from utilmeta import UtilMeta
from utilmeta.core import api
import flask

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=flask,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    app.run(
        debug=False,
        port=8000
    )
```

## 部署服务

通过 `run()` 方法我们可以在调试时快速运行一个可访问服务实例，但是在实际部署时，我们往往需要额外的配置从而使得服务稳定地运行在我们期望的地址，并且充分发挥运行环境的性能

Python 开发的 API 服务常用的一种部署架构为

![ BMI API Doc ](https://utilmeta.com/assets/image/server-deploy.png)

将你开发的 API 服务使用 uwsgi / gunicorn 等 WSGI 服务器或 Daphne 等 ASGI 服务器运行，它们会更高效地进行多进程（worker）管理和请求分发

然后使用一个反向代理服务（如 Nginx）将 API 的根路由解析到 WSGI/ASGI 服务器提供的端口，同时可以代理图片或 HTML 等静态文件，然后根据需要对外提供 80 端口的 HTTP 服务或 443 端口的 HTTPS 服务

但是由于不同的运行时框架的特性不同，我们建议根据你使用的 `backend` 选择部署策略

* **Django**：默认生成  WSGI 应用，可以使用 uWSGI / Gunicorn 部署，如果是异步服务生成的 ASGI 应用，也可以使用 Daphne ASGI 服务器部署
* **Flask**：生成  WSGI 应用，可以使用 uWSGI / Gunicorn 部署
* **Sanic**：自身就是一个多进程服务应用，可以直接使用 Nginx 代理
* **Starlette/FastAPI**：可以使用搭载了 Uvicorn worker 的 Gunicorn 部署
* **Tornado**：自身就是一个异步服务应用，可以直接使用 Nginx 代理

!!! tip
	有些框架如 Sanic 和 Tornado，本身就可以直接运行可靠的高性能服务，所以无需使用 WSGI / ASGI 服务器，可以直接运行并接入 Nginx 代理

### uWSGI

使用 uWSGI 之前需要先安装
```
pip install uwsgi
```

之后可以使用 `ini` 文件编写 uwsgi 的配置文件，如
```ini
[uwsgi]
module = server:app
chdir = /path/to/your/project
daemonize = /path/to/your/log
workers = 5
socket=127.0.0.1:8000
```

其中重要的参数包括

* `chdir`：指定服务的运行目录，一般是项目的根目录
* `module`：指定你服务的 WSGI 应用，相对服务的运行目录，假设你的 WSGI 应用位于 `server.py` 中的 `app` 属性，就可以使用 `server:app` 定义
* `daemonize`：设置日志文件地址
* `workers`：设置服务运行的进程数量，一般可以设为服务器的 CPU 数 x  2 + 1
* `socket`：uwsgi 服务监听的 socket 地址，用于与前置的 Nginx 等代理服务器通信

uwsgi 服务器的运行命令如下

```
uwsgi --ini /path/to/your/uwsgi.ini
```

### Gunicorn

使用 Gunicorn 之前需要先安装
```
pip install gunicorn
```

之后可以直接使用 Python 文件编写 Gunicorn 的配置文件，如

```python
wsgi_app = 'server:app'
bind = '127.0.0.1:8000'
workers = 5
accesslog = '/path/to/your/log/access.log'
errorlog = '/path/to/your/log/error.log'
```

其中主要的参数有

* `wsgi_app`：指定你服务的 WSGI 应用的引用，假设你的 WSGI 应用位于 `server.py` 中的 `app` 属性，就可以使用 `server:app` 定义
* `bind`：服务监听的地址，用于与前置的 Nginx 等代理服务器通信
* `workers`：设置服务运行的进程数量，一般可以设为服务器的 CPU 数 x  2 + 1
* `accesslog`：设置服务的访问日志地址
* `errorlog`：设置服务的运行于错误日志地址

此外你还可以使用 `worder_class` 属性指定工作进程的实现，可以根据接口的类型优化运行效率，如

* `'uvicorn.workers.UvicornWorker'`：适合异步接口的，如 Starlette / FastAPI，需要先安装 `uvicorn`
* `'gevent'`：适合同步接口，如 Django / Flask，会使用 `gevent` 库中的协程（green thread）提高接口的并发性能，需要先安装 `gevent`

gunicorn 服务器的运行命令如下

```
gunicorn -c /path/to/gunicorn.py
```

### Nginx

对于使用 uWSGI 的 API 服务，假设运行在 8000 端口，Nginx 的配置大致为

```nginx
server{
    listen 80;
    server_name example.com;
    charset utf-8;
    include /etc/nginx/proxy_params;
    
    location /api/{
        include /etc/nginx/uwsgi_params;
        uwsgi_pass 127.0.0.1:8000;
    }
}
```

对于 Gunicorn 或者其他直接运行的服务，假设运行在 8000 端口，Nginx 的配置大致为

```nginx
server{
    listen 80;
    server_name example.com;
    charset utf-8;
    include /etc/nginx/proxy_params;
    
    location /api/{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header REMOTE_ADDR $remote_addr;
    }
}
```

!!! tip
	为了使得 API 服务能够获取到请求的来源 IP（而不是反向代理服务的 IP），我们需要使用 `proxy_set_header` 将对应的请求头参数传递过去

你应该把配置好的 nginx 文件放置在 ·`/etc/nginx/sites-enabled/` 中从而启用对应的配置，可以使用如下命令检测配置是否有问题

```
nginx -t
```

如果没有问题，就可以使用如下命令重启 nginx 服务使得更新的配置生效

```
nginx -s reload
```

## 监控与管理

UtilMeta 即将支持全周期的 API 管理能力，包括

* API 文档与调试
* 日志查询
* 接口监控，服务器监控
* 报警通知，事件管理
* 定时任务调度

目前平台已开放 Beta 版本的 waitlist，可以 [UtilMeta 官网](https://utilmeta.com/zh) 中加入

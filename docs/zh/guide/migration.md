# 从现有项目迁移

UtilMeta 是一个 **渐进式** 的元框架，也就意味着它可以从现有的 Python 项目中渐进式地接入，也可以整合其他 Python 框架项目的接口，本篇文档将分别介绍对应的用法

## UtilMeta 接口接入现有项目

UtilMeta 项目中所有的 API 接口都以 API 类（`utilmeta.core.api.API`）的形式存在，API 类有一个方法就是用于将 UtilMeta 接口转化为其他框架的路由函数的，这个方法如下

`API.__as__(backend, route: str, asynchornous: bool = None)`

其中的参数为

* `backend`：可以传入 `django`, `tornado` 等包的引用，也可以传入 `flask`, `starlette`, `fastapi`, `sanic` 的核心应用
* `route`：传入这个接口对应的路由路径，如 `/v2`
* `asynchornous`：是否提供异步接口，如果为 True，则 UtilMeta API 类会被转化为一个异步函数，否则会被转化为一个同步函数，默认为 None，由 `backend` 的特性决定

UtilMeta 接口渐进式接入现有项目就只需要这一个方法即可，下面是不同框架的接入示例
### Django

接入 Django 项目，只需将 `API.__as__` 方法的返回结果作为 `urlpatterns` 中的一个元素即可，如
```python hl_lines="20"
import django
from django.urls import re_path
from django.http.response import HttpResponse
from utilmeta.core import api, response

class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

def django_test(request, route: str):
    return HttpResponse(route)

urlpatterns = [
    re_path('test/(.*)', django_test),
    CalcAPI.__as__(django, route='/calc'),
]
```

我们将 CalcAPI 挂载到了 `/calc` 路由上，当我们访问 `GET /calc/add?a=1&b=2` 就可以得到如下 JSON 响应
```json
{"data": 3, "msg": ""}
```

### Flask

Flask 应用中会使用 `Flask(__name__)` 初始化一个应用，你只需要把这个应用传递到 `API.__as__` 方法的第一个参数即可

```python hl_lines="20"
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

from utilmeta.core import api, response

class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

CalcAPI.__as__(app, route='/calc')

if __name__ == '__main__':
    app.run()
```

当启动项目访问 [http://127.0.0.1:5000/](http://127.0.0.1:5000/) 时你可以看到屏幕上出现了 `Hello, World!`，这是来自 Flask 的接口，而请求 [http://127.0.0.1:5000/calc/add?a=-1&b=2](http://127.0.0.1:5000/calc/add?a=-1&b=2)，你就可以看到 UtilMeta 接口的返回

```json
{"data": 1, "msg": ""}
```

### Starlette (FastAPI)

类似于 Flask，当接入 FastAPI (Starlette) 应用时，只需要把应用传入 `API.__as__` 方法即可，如 
```python hl_lines="20"
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}

from utilmeta.core import api, response

class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

CalcAPI.__as__(app, route='/calc')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app)
```

当你访问 [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1) 时会访问 FastAPI 的接口，得到 `{"item_id":"1"}`

当你访问 [http://127.0.0.1:8000/calc/add?a=1.5&b=2.1](http://127.0.0.1:8000/calc/add?a=1.5&b=2.1) 时会访问 UtilMeta 的结果，得到
```json
{"data": 3, "msg": ""}
```

!!! tip
	得到这样的结果是因为参数 `a`, 和 `b` 在计算前都被转化为了声明的 `int` 整数类型

### Sanic
与 Flask 或 FastAPI 类似的用法
```python  hl_lines="21"
from sanic import Sanic
from sanic.response import text

app = Sanic("MyHelloWorldApp")

@app.get("/")
async def hello_world(request):
    return text("Hello, world.")

from utilmeta.core import api, response

class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

CalcAPI.__as__(app, route='/calc')

if __name__ == '__main__':
    app.run()
```

访问 [http://127.0.0.1:8000/](http://127.0.0.1:8000/) 会看到 Sanic 返回的 `hello, world`，访问 [http://127.0.0.1:8000/calc/add?a=1&b=x](http://127.0.0.1:8000/calc/add?a=1&b=x) 则会看到 UtilMeta 对参数进行了解析与处理

```json
{"data": null, "msg": "BadRequest: parse item: ['b'] failed: invalid number: 'x'"}
```

!!! tip
	因为请求的参数 `b=x` 无法转化为 `int` 类型 

### Tornado

将 UtilMeta 接口整合如 Tornado 的方式如下

```python  hl_lines="21"
import asyncio
import tornado

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

from utilmeta.core import api, response

class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

def make_app():
    return tornado.web.Application([
        CalcAPI.__as__(tornado, route='/calc'),
        (r"/", MainHandler),
    ])

async def main():
    app = make_app()
    app.listen(8888)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

就是将 `API.__as__` 的结果作为 `tornado.web.Application` 的一条路由

### UtilMeta 接入规则

在将 UtilMeta 接入其他的现有项目时，你应该只接入 **一个** API 类，如果你开发了其他的 API 类，那么可以使用挂载作为接入的 API 类的子路由

因为在 UtilMeta 接口接入其他项目的时候，服务不是由 UtilMeta 控制的，所以 `API.__as__` 函数会创建一个 隐藏的 UtilMeta 服务进行调控，所以为了避免服务冲突，你只能调用一次 `API.__as__` 函数

## UtilMeta 项目接入其他框架接口

你的 UtilMeta 项目也可以接入其他框架开发好的接口，比如
### Django

你可以将你编写的 Django 视图 URL 直接接入 UtilMeta 项目中，有两种方式

**使用 `django` 作为服务 `backend`**

如果你的 UtilMeta 服务就是使用 `django` 作为 `backend` 的，有着类似如下的文件结构
```python
/blog
	/app
		models.py
	urls.py   
	service.py
```

其中 `urls.py` 定义了 Django 视图路由，那么你只需要把这个文件的引用传入 DjangoSettings 的 `root_urlconf` 即可

=== "service.py" 
	```python  hl_lines="14"
	from utilmeta import UtilMeta
	import django
	
	service = UtilMeta(
	    __name__,
	    name='blog',
	    backend=django
	)
	
	from utilmeta.core.server.backends.django import DjangoSettings
	from utilmeta.core.orm import DatabaseConnections, Database
	service.use(DjangoSettings(
	    apps=['app'],
	    root_urlconf='urls'
	))
	
	service.use(DatabaseConnections({
	    'default': Database(
	        name='db',
	        engine='sqlite3',
	    )
	}))
	
	from utilmeta.core import api
	
	class RootAPI(api.API):
	    @api.get
	    def hello(self):
	        return 'world'
	
	service.mount(RootAPI, route='/api')
	app = service.application()
	
	if __name__ == '__main__':
	    service.run()
	```

=== "urls.py"
	```python
	from app.models import Article
	from django.urls import path
	import json
	from django.http.response import HttpResponse
	
	def get_article(request):
	    return HttpResponse(
	        json.dumps(list(Article.objects.filter(id=request.GET.get('id')).values()))
	    )
	
	urlpatterns = [
	    path('article', get_article)
	]
	```

当你访问 `GET /article` 时，就会命中 Django 的路由视图函数 `get_article`


**使用 `starlette` (fastapi) 作为服务 `backend`**

你也可以使用 `starlette` 作为 `backend` 并接入 django 视图函数。在你的 Django 项目的 `settings.py` 配置中，应该会有一个 `application` 属性

```python
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

你只需要把这个 `application` 导入，并使用 UtilMeta 服务的 `mount()` 方法进行挂载即可，比如

```python  hl_lines="8"
import starlette
from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=starlette)

from settings import application as django_wsgi

service.mount(django_wsgi, '/v1')
```

当请求访问 `/v1/xxx` 时就会定向到 Django 的路由视图函数

### Flask

**使用 `flask` 作为服务 `backend`**

如果你使用 `flask` 作为 UtilMeta 服务 `backend`，那么只需要把 flask 应用作为 `backend` 传入 UtilMeta 服务即可

```python  hl_lines="18"
from flask import Flask
from utilmeta import UtilMeta
from utilmeta.core import api, response

flask_app = Flask(__name__)

class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'

service = UtilMeta(
    __name__,
    backend=flask_app,
    api=RootAPI,
    route='/api'
)

@flask_app.route("/v1/hello")
def hello_flask():
    return "<p>Hello, flask!</p>"

if __name__ == '__main__':
    service.run()
```

这样当你访问 [http://127.0.0.1:5000/v1/hello](http://127.0.0.1:5000/v1/hello) 就会访问到 `hello_flask` 路由函数，返回 `Hello, flask!`，而当你访问 [http://127.0.0.1:5000/api/hello](http://127.0.0.1:5000/api/hello) 则会被 UtilMeta API 处理，响应

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


**使用 `starlette` (fastapi) 作为服务 `backend`**

你也可以使用 `starlette` 作为 `backend` 并挂载 flask 应用，只需要把 `Flask(__name__)` 的应用使用 `mount` 方法挂载即可

```python  hl_lines="13"
import starlette
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route("/hello")
def hello_flask():
    return "<p>Hello, flask!</p>"

from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=starlette)
service.mount(flask_app, '/v1')
```

这样当你访问 `GET /v1/hello` 时，依然会被 `hello_flask` 路由函数处理

### Starlette (FastAPI)

类似 Flask，接入 Starlette (FastAPI) 只需要把核心应用使用 `mount` 方法挂载即可

```python  hl_lines="22"
from fastapi import FastAPI

fastapi_app = FastAPI()

@fastapi_app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}

from utilmeta import UtilMeta
from utilmeta.core import api, response

class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'

service = UtilMeta(
    __name__,
    backend=fastapi_app,
    api=RootAPI
)

if __name__ == '__main__':
    service.run()
```

当你访问 [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1) 会命中 FastAPI 的 `read_item` 函数返回 `{"item_id":"1"}`，而访问 [http://127.0.0.1:8000/hello](http://127.0.0.1:8000/hello) 则会被 UtilMeta API 处理，响应

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


!!! tip
	接入 Starlette (FastAPI) 接口后，你的 UtilMeta 项目的 `backend` 也需要是是 `starlette` 或 `fastapi`

### Sanic

接入 Sanic 接口只能使用 `sanic` 作为 UtilMeta 服务的 `backend`，用法与 Flask 类似

```python  hl_lines="22"
from sanic import Sanic, text

sanic_app = Sanic('demo')

@sanic_app.get("/v1/hello")
def hello(request):
    return text("Hello, sanic!")

from utilmeta import UtilMeta
from utilmeta.core import api, response

class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'

service = UtilMeta(
    __name__,
    name='test',
    backend=sanic_app,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    service.run()
```


当你运行服务访问 [http://127.0.0.1:8000/v1/hello](http://127.0.0.1:8000/v1/hello) 时会命中 sanic 的路由函数返回 `Hello, sanic!`，而当你访问 [http://127.0.0.1:8000/api/hello](http://127.0.0.1:8000/api/hello) 时就会被 UtilMeta 处理并响应

```json
{"data": "Hello, UtilMeta!", "error": ""}
```

## 支持更多框架

如果你正在使用的 Python 框架还没有被支持，请在 UtilMeta 框架的 [Issues](https://github.com/utilmeta/utilmeta-py/issues) 中提出
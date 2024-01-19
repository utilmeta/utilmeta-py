# Migrate from current project

UtilMeta is a ** Progressive ** meta-framework, which means that it can be accessed incrementally from existing Python projects, and can also integrate interfaces from other Python framework projects. This document will introduce the corresponding usage.

## Integrate UtilMeta to current project

All API interfaces in the UtilMeta project exist in the form of API class ( `utilmeta.core.api.API`). The API class has a method for converting the UtilMeta interface to the routing function of other frameworks. This method is as follows

`API.__as__(backend, route: str, asynchornous: bool = None)`

The parameters are

*  `backend`: You can pass in `django` a reference to a package such as, `tornado` or the core application of `flask`, `starlette`, `fastapi`, `sanic`.
*  `route`: The routing path corresponding to the incoming interface, such as
*  `asynchornous`: Whether to provide an asynchronous interface. If True, the UtilMeta API class will be converted to an asynchronous function. Otherwise, it will be converted to a synchronous function. The default is None, determined by `backend` the attribute of.

This is the only method required for the UtilMeta interface to progressively access existing projects, and the following is an example of access to different frameworks
### Django

To access a Django project, simply use `API.__as__` the return result of a method as `urlpatterns` an element in, as shown in
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

We mount the Calc API on `/calc` the route, and when we access `GET/calc/add?a=1&b=2` it, we get the following JSON response
```json
{"data": 3, "msg": ""}
```

### Flask

Flask is used `Flask(__name__)` to initialize an application, and you just need to pass the application to `API.__as__` the first parameter of the method.

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

When you start the project access [http://127.0.0.1:5000/](http://127.0.0.1:5000/), you can see that the screen appears `Hello, World!`, this is the interface from Flask, and the request [http://127.0.0.1:5000/calc/add?a=-1&b=2](http://127.0.0.1:5000/calc/add?a=-1&b=2), you can see the return of the UtilMeta interface.

```json
{"data": 1, "msg": ""}
```

### Starlette (FastAPI)

Similar to Flask, when accessing a Fast API (Starlette) application, you only need to pass the application into `API.__as__` the method, as shown in
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

When you access [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1), you will access the FastAPI interface and get

When you visit [http://127.0.0.1:8000/calc/add?a=1.5&b=2.1](http://127.0.0.1:8000/calc/add?a=1.5&b=2.1), you will visit the results of UtilMeta and get
```json
{"data": 3, "msg": ""}
```

!!! tip

### Sanic
Usage similar to Flask or FastAPI
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

Access [http://127.0.0.1:8000/](http://127.0.0.1:8000/) will see Sanic returned `hello, world`, and access [http://127.0.0.1:8000/calc/add?a=1&b=x](http://127.0.0.1:8000/calc/add?a=1&b=x) will see UtilMeta parsed and processed the parameters.

```json
{"data": null, "msg": "BadRequest: parse item: ['b'] failed: invalid number: 'x'"}
```

!!! tip

### Tornado

The way to integrate the UtilMeta interface like Tornado is as follows

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

Is to take `API.__as__` the result of as `tornado.web.Application` a route to

### Integration rules

When connecting UtilMeta to other existing projects, you should only connect ** One ** API classes. If you develop other API classes, you can use the mount as a subroute to the connected API classes.

Because the service is not controlled by UtilMeta when the UtilMeta interface accesses other projects, `API.__as__` the function will create a hidden UtilMeta service for control, so in order to avoid service conflicts, you can only call the `API.__as__` function once.

## Integrate other frameworks to UtilMeta

When your project uses starlette (or Fast API) as the underlying implementation, you can also tap into the interfaces of the following frameworks at the same time
### Django

You can write the Django view URL directly into the UtilMeta project in two ways.

** Use `django` as a service `backend` **

If your UtilMeta service is used `django` as `backend` a, it has a file structure similar to the following
```python
/blog
	/app
		models.py
	urls.py   
	service.py
```

Django view routing is `urls.py` defined, so you just need to pass a reference to this file into DjangoSettings `root_urlconf`.

=== “service.py”
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

=== “urls.py”
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

When you visit `GET/article`, it hits Django’s route view function.


** Use `starlette` (fastapi) as a service

You can also use `starlette` as `backend` and access Django view functions. In the configuration of your Django project `settings.py`, there should be a `application` property

```python
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

You just need to import this `application` and mount it using the `mount()` UtilMeta service method, such as

```python  hl_lines="8"
import starlette
from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=starlette)

from settings import application as django_wsgi

service.mount(django_wsgi, '/v1')
```

When access `/v1/xxx` is requested, it is directed to Django’s routing function.

### Flask

** Use `flask` as a service `backend` **

If you are using `flask` as the UtilMeta service `backend`, simply pass the flask application as `backend` the UtilMeta service.

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

In this way, when you access [http://127.0.0.1:5000/v1/hello](http://127.0.0.1:5000/v1/hello), you will access the `hello_flask` routing function and return `Hello, flask!`, and when you access [http://127.0.0.1:5000/api/hello](http://127.0.0.1:5000/api/hello), it will be processed and responded by UtilMeta API.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


** Use `starlette` (fastapi) as a service

You can also use `starlette` as `backend` and access the flask interface, just `Flask(__name__)` mount the application usage `mount`.

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

So when you access `GET/v1/hello` it, it will still be processed by `hello_flask` the routing function.

### Starlette (FastAPI)

Similar to Flask, accessing Starlette (Fast API) only needs to mount the core application usage `mount`.

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

When you access [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1) it, it will hit the `read_item` function return `{"item_id":"1"}` of FastAPI, and the access [http://127.0.0.1:8000/hello](http://127.0.0.1:8000/hello) will be processed and responded by UtilMeta API.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


!!! tip

### Sanic

Access to the Sanic interface can only be used `sanic` as a UtilMeta service `backend`, similar to Flask

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


When you run service access [http://127.0.0.1:8000/v1/hello](http://127.0.0.1:8000/v1/hello), it will hit sanic’s routing function return `Hello, sanic!`, and when you access [http://127.0.0.1:8000/api/hello](http://127.0.0.1:8000/api/hello) it, it will be processed and responded by UtilMeta.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```

## Support more frameworks

If the Python framework you are using is not yet supported, please mention it in the [Issues](https://github.com/utilmeta/utilmeta-py/issues) UtilMeta framework.
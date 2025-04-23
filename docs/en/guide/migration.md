# Migrate from current project

UtilMeta is a **Progressive** meta-framework, which means that it can be integrated incrementally from existing Python projects, and can also integrate other Python framework's API. This document will introduce the corresponding usage.

## Integrate UtilMeta to current project

All API in the UtilMeta project are declared in API class ( `utilmeta.core.api.API`). The API class has a method for converting the UtilMeta API to the routing function of other frameworks. This method is as follows

`API.__as__(backend, route: str, asynchornous: bool = None)`

The parameters are

* `backend`: You can pass in the `django`, `tornado` package or the core application of `flask`, `starlette`, `fastapi`, `sanic`
* `route`: The routing path corresponding to the API, such as `/v2`
* `asynchornous`: Whether to provide an asynchronous API. If True, the UtilMeta API class will be converted to an asynchronous function. Otherwise, it will be converted to a synchronous function. The default is None, determined by the `backend`

This is the only method required for the UtilMeta API to progressively integrate to existing projects, and the following is an example of integrate to different frameworks
### Django

To integrate a Django project, simply use the return result of `API.__as__` method as an element in `urlpatterns` , as shown in
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

We mount the `CalcAPI` on the route `/calc` , and when we request `GET /calc/add?a=1&b=2`, we'll get the following JSON response
```json
{"data": 3, "msg": ""}
```

### Flask

Flask use `Flask(__name__)` to initialize an application, and you just need to pass the application to `API.__as__` as the first parameter of the method.

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

When you startup the project and request [http://127.0.0.1:5000/](http://127.0.0.1:5000/), you can see that the `Hello, World!` in the browser, this is the API from Flask, and if request [http://127.0.0.1:5000/calc/add?a=-1&b=2](http://127.0.0.1:5000/calc/add?a=-1&b=2), you can see the return of the UtilMeta API.

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

When you request [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1), you will access the FastAPI's endpoint and get `{"item_id":"1"}`

When you request [http://127.0.0.1:8000/calc/add?a=1.5&b=2.1](http://127.0.0.1:8000/calc/add?a=1.5&b=2.1), you will get the results of UtilMeta API
```json
{"data": 3, "msg": ""}
```

!!! tip
	This result is because the `a` and `b` param is converted to `int` before the calculation

### Sanic
Usage is similar to Flask or FastAPI
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

Request [http://127.0.0.1:8000/](http://127.0.0.1:8000/) will see Sanic returned `hello, world`, and request [http://127.0.0.1:8000/calc/add?a=1&b=x](http://127.0.0.1:8000/calc/add?a=1&b=x) will see UtilMeta's parameters procession.

```json
{"data": null, "msg": "BadRequest: parse item: ['b'] failed: invalid number: 'x'"}
```

!!! tip
	Because the query param `b=x` cannot converted to `int` type

### Tornado
The way to integrate the UtilMeta API like Tornado is as follows

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

Just take the result of  `API.__as__` as a route of `tornado.web.Application`

### API Integration rules

When integrate UtilMeta to other existing projects, you should only integrate **One** API classes. If you develop other API classes, you can use API mounting as a subroute of the integrated API classes.

Because the service is not controlled by UtilMeta when the UtilMeta API integrate other projects,  so `API.__as__` will create a hidden UtilMeta service for control, in order to avoid service conflicts, you can only call the `API.__as__` function once.

### Configure UtilMeta service

You can declare a UtilMeta service instance to inject your configurations. Set the API class you defined as root API of service using `api` param, then replace the `__as__` method to `service.adapt` to adapt the entire service, like:

```python hl_lines="34"
import django
from django.urls import re_path
from django.http.response import HttpResponse
from utilmeta.core import api, response

class TimeAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def now(self):
        return self.request.time

def django_test(request, route: str):
    return HttpResponse(route)

from utilmeta import UtilMeta
from utilmeta.conf import Time

service = UtilMeta(
    __name__,
    name='time',
    backend=django，
    api=TimeAPI,
)
service.use(Time(
    datetime_format="%Y-%m-%d %H:%M:%S",
    use_tz=False
))

urlpatterns = [
    re_path('test/(.*)', django_test),
    service.adapt('/api/v1/time')
]
```
`service.adapt` takes a route param to specify the adapted route that will prepend to the UtilMeta service root url. Using the above method, when request `/api/v1/time/now`, you will see the datetime string using the configured format:
```json
{"data": "2025-04-15 16:38:30", "msg": ""}
```

!!! note
	The `backend` param of UtilMeta service instance should be consistent to the framework the project using.

## Integrate other frameworks

Your UtilMeta project can also integrate other framework's APIs
### Django

You can mount the Django view URL directly into the UtilMeta project in two ways.

**Use `django` as backend**

If your UtilMeta service is used `django` as `backend` a, it has a file structure similar to the following
```python
/blog
	/app
		models.py
	urls.py   
	service.py
```

Django view urls is defined in `urls.py`, so you just need to pass a reference to this file into the `root_urlconf` param of DjangoSettings 

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

When you request `GET /article`, it will hit Django’s route view function.

**Use `starlette` (fastapi) as backend**

You can also use `starlette` as `backend` mount Django view functions. In the configuration of your Django project `settings.py`, there should be a `application` property

```python
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

You just need to import this `application` and mount it using the `mount()` method of UtilMeta service, such as

```python hl_lines="8"
import starlette
from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=starlette, name='demo')

from settings import application as django_wsgi

service.mount(django_wsgi, '/v1')
```

When `/v1/xxx` is requested, it will be directed to Django’s view functions.

#### Django Ninja
to integrate **Django Ninja**, you must use `django` as service backend, the integration is as simple as follows

```python hl_lines="17"
import django
from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=django, name='demo')

from utilmeta.core.server.backends.django import DjangoSettings
service.use(DjangoSettings())
service.setup()

from ninja import NinjaAPI
ninja_api = NinjaAPI()

@ninja_api.get("/add")
def add(request, a: int, b: int):
    return {"result": a + b}

service.mount(ninja_api, '/v1')

app = service.application()
```

!!! warning
	`ninja` should import after the django settings setup, otherwise a `django.core.exceptions.ImproperlyConfigured` exception will be raised

#### DRF
to Integrate **Django REST framework**, you must use `django` as service backend, the integration is as simple as follows

```python hl_lines="42"
from utilmeta import UtilMeta
import django

service = UtilMeta(
    __name__,
    name='demo',
    backend=django
)

from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database
service.use(DjangoSettings(
    apps=['app', 'rest_framework', 'django.contrib.auth'],
    extra=dict(
        REST_FRAMEWORK={
            'DEFAULT_RENDERER_CLASSES': [
                'rest_framework.renderers.JSONRenderer',
            ]
        }
    )
))
service.setup()

from app.models import User
from rest_framework import routers, serializers, viewsets

# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'signup_time', 'admin']

# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

# Routers provide an easy way of automatically determining the URL conf.
drf_router = routers.DefaultRouter()
drf_router.register(r'users', UserViewSet)

service.mount(drf_router, route='/v1')

app = service.application()
```

!!! tip
	You can configure DRF in the `extra` param of DjangoSettings, and remember to include `'rest_framework'` in your `apps` param 

### Flask

**Use `flask` as backend**

If you are using `flask` as the UtilMeta service `backend`, simply pass the Flask application as `backend` of the UtilMeta service.

```python  hl_lines="19"
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
    name='demo',
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

In this way, when you request [http://127.0.0.1:5000/v1/hello](http://127.0.0.1:5000/v1/hello), the `hello_flask` routing function will be called and return `Hello, flask!`, and when you request [http://127.0.0.1:5000/api/hello](http://127.0.0.1:5000/api/hello), it will be processed and responded by UtilMeta API.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


**Use `starlette` (fastapi) as backend**

You can also use `starlette` as `backend` and mount the flask application, just mount the `Flask(__name__)` application using `mount`.

```python  hl_lines="13"
import starlette
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route("/hello")
def hello_flask():
    return "<p>Hello, flask!</p>"

from utilmeta import UtilMeta

service = UtilMeta(__name__, backend=starlette, name='demo')
service.mount(flask_app, '/v1')
```

So when you request `GET /v1/hello`, it will still be processed by `hello_flask` routing function of flask.

### Starlette (FastAPI)

Similar to Flask, integrate Starlette (FastAPI) only needs to mount the core application using `mount`.

```python  hl_lines="24"
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
    name='demo',
    backend=fastapi_app,
    api=RootAPI
)

if __name__ == '__main__':
    service.run()
```

When you request [http://127.0.0.1:8000/items/1](http://127.0.0.1:8000/items/1), it will call the `read_item` function of FastAPI application and return `{"item_id":"1"}`, and request [http://127.0.0.1:8000/hello](http://127.0.0.1:8000/hello) will be processed and responded by UtilMeta API.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```


!!! tip
	When integrating Starlette (FastAPI) application, your `backend` of UtilMeta service must be `starlette` or `fastapi`

### Sanic

Integrate Sanic is similar to Flask, but you can only use `sanic` as the `backend` of UtilMeta service

```python  hl_lines="24"
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
    name='demo',
    backend=sanic_app,
    api=RootAPI,
    route='/api'
)

app = service.application()

if __name__ == '__main__':
    service.run()
```


When you run service and request [http://127.0.0.1:8000/v1/hello](http://127.0.0.1:8000/v1/hello), it will call sanic’s routing function and return `Hello, sanic!`, and when you request [http://127.0.0.1:8000/api/hello](http://127.0.0.1:8000/api/hello), it will be processed and responded by UtilMeta API.

```json
{"data": "Hello, UtilMeta!", "error": ""}
```

## Support more frameworks

If the Python framework you are using is not yet supported, please mention it in the [Issues](https://github.com/utilmeta/utilmeta-py/issues) of UtilMeta framework.
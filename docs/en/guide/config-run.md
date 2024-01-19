# Run & Deploy

This document describes how to configure and run the UtilMeta project and how to deploy it in a production environment.

## Service initialization

```python
from utilmeta import UtilMeta

service = UtilMeta(__name__, ...)
```

The first parameter of the UtilMeta service receives the name of the current module ( `__name__`). Other supported parameters are

*  `backend`: Pass in the module or name of the runtime framework, such as
* The name of the `name` service should reflect the domain and business of the service, followed by the registration, discovery, and detection functions of the user service.
*  `description`: Description of the service
*  `production`: Whether it is in production status. It is False by default and should be set to True in the deployed production environment. Finding a parameter will affect the running configuration of the underlying framework, such as `django` `PRODUCTION` the setting of. `debug` Parameters with flask/starlette/fastapi/sanic

*  `host`: The host IP that the service listens to when running. The default is `127.0.0.1`. It can also be set to the IP of the running host or `0.0.0.0` (public access).
*  `port`: The port number of the service runtime listener. The default depends on the runtime framework. For example, flask uses `8000` `5000`. Other frameworks generally use.

*  `version` Specifies the current version number of the service. You can pass in a string, such as `'1.0.2'`, or a tuple. For example `(0, 1, 0)`, the specification for the version number is recommended to comply with
*  `asynchronous` Mandatory specifies whether the service provides an asynchronous interface. The default is determined by the nature of the runtime framework.
*  `api`: Pass in UtilMeta’s root API class or its reference string
*  `route`: The path string of the root API mount of UtilMeta. The default is `'/'`, that is, mount to the root path.

When you initialize UtilMeta, in addition to importing directly, you can also import the UtilMeta service instance of the current process in this way

```python
from utilmeta import service
```

!!! warning

### Choose `backend`

The runtime frameworks currently supported by UtilMeta are

* `django`
* `flask`
* `starlette`
* `fastapi`
* `sanic`
* `tornado`

!!! tip

The framework you specify with `backend` the parameter needs to be installed in your Python environment first, and then you can import the package and pass in `backend` the parameter in a way similar to the following

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
#### Inject custom application

Some runtime frameworks often provide developers with an application class of the same name, such as `Flask`, `FastAPI` `Sanic`, which can define some initialization parameters, if you need to configure the parameters. You can pass `backend` in parameters for the defined application instance, such as

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

### Asynchronous service

Different runtime frameworks support asynchrony to varying degrees. If no parameters are explicitly specified `asynchronous`, whether a service interface is asynchronous depends on its characteristics, such as
 
* **Django**: Both WSGI and ASGI are supported, but `asynchronous` the default is False.
!!! tip

* **Flask**: WSGI is supported. To process asynchronous functions, you need to convert them into synchronous functions. `asynchronous` The default is False.
* **Sanic**: ASGI is supported, `asynchronous` True by default
* **Tornado**: Self-implemented HTTP Server based on `asyncio`, `asynchronous` True by default
* **Starlette/FastAPI**: ASGI is supported, `asynchronous` True by default

If you want to write an async `async def` interface, choose a runtime framework that supports async by default to maximize the performance of your asynchronous interface. If you choose a runtime framework that does not enable async by default (such as `django`/ `flask`), You need to turn on the `asynchronous=True` option or you will not be able to execute the asynchronous functions in it

## Service Methods & Hooks

The instantiated UtilMeta service also has some methods or hooks that can be used.

### `use(config)` Inject configuration

The methods of the service instance `use` can be used to inject the configuration, for example
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

Common configurations built into UtilMeta are

*  `utilmeta.core.server.backends.django.DjangoSettings` Configure the Django project. Use this if your service uses Django as the runtime framework, or if you need to use the Django model.
*  `utilmeta.core.orm.DatabaseConnections`: Configure Database Connection
*  `utilmeta.core.cache.CacheConnections`: Configure the cache connection
*  `utilmeta.conf.time.Time`: Configures the time zone of the service and the time format in the interface.

!!! warning

### `setup()` install configuration

Some service configuration items need to be installed and prepared before the service starts. For example, for services using Django model, `setup()` functions will be called `django.setup` to complete the discovery of the model. You need to call this method before you can import the Django models you define and the interfaces and Schema classes that depend on them, such as

```python
from utilmeta import UtilMeta
from config.conf import configure 
import django

service = UtilMeta(..., backend=django)
configure(service)
service.setup()

from user.models import *
```

Otherwise, an error similar to the following occurs
```python
django.core.exceptions.ImproperlyConfigured: 
Requested setting INSTALLED_APPS, but settings are not configured, ...	
```

Of course, for projects using Django, it is a best practice to use a reference string to specify the root API, so that you don’t need to include an import of the Django model in the service configuration file, for example

=== “main.py”
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
=== “service/api.py”
	```python
	from utilmeta.core import api
	
	class RootAPI(api.API):
	    @api.get
	    def hello(self):
	        return 'world'
	```

### `application()` Get WSGI/ASGI Application

You can call the service `application()`’s method to return the WSGI/ASGI application it generated, as in the Hello World example.

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

The type of this generated `app` depends on what the `backend` service instance specifies, such as

*  `flask`: Returns a Flask instance
*  `starlette`: Returns a Starlette instance
*  `fastapi`: Returns a FastAPI instance
*  `sanic`: Returns a Sanic instance
*  `django`: a WSGIHandler is returned by default, or an ASGIHandler if specified `asynchronous=True`
*  `tornado`: Returns an `tornado.web.Application` instance

If you use WSGI servers such as uwsgi and gunicorn to deploy API services, you need to specify a WSGI application, and you only need to set the corresponding configuration item to `app` the reference of, such as

=== “gunicorn.py”
	```python
	wsgi_app = 'server:app'
	```
=== “uwsgi.ini”
	```ini
	[uwsgi]
	module = server.app
	```

!!! Warning “use `sanic`”

### `@on_startup` startup hook

You can use the decorator of the service instance `@on_startup` to decorate a startup hook function, which is called before the service process starts. It can be used to initialize some services, such as

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

For frameworks that support async `backend`, like Starlette/FastAPI/Sanic/Tornado, you can use async functions as startup hook functions, otherwise you need to use synchronous functions, like Django/Flask

###  `@on_shutdown` termination hook

You can use the decorator of the service instance `@on_shutdown` to decorate a termination hook function, which is called before the service process ends, and can be used to clean up the service process, such as

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

## Environment variables

In the actual back-end development, you often need to use a lot of keys, such as database passwords, third-party application keys, JWT keys, etc. If these information is hard-coded into the code, there is a risk of leakage, which is very unsafe, and these key information often has different configurations in the development, testing and production environments, so it is more suitable to use environment variables to manage.

UtilMeta provides a built-in environment variable component `utilmeta.conf.Env` for you to manage these variables and key information in the following way

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

By inheriting `utilmeta.conf.Env` classes, you can declare the environment variables required by the service. Environment variables are resolved regardless of case, but we recommend using uppercase to distinguish them from other attributes. You can declare a type and default value for each variable, and `Env` will convert the variable to your declared type. Use the default value you specified when the corresponding variable is not available

 `Env` Subclasses can specify the source of environment variables when they are instantiated, such as

### `sys_env` System environment variables

You can specify a prefix that will pick up ** Prefix + name ** the variables in the system environment variables. For example, if the prefix specified in the example is `'DEMO_'`, the variables in `DEMO_DB_PASSWORD` the system environment variables will be parsed as attributes in the `DB_PASSWORD` environment variable data.

If you do not need to specify any prefixes, you can use the
### `file` Configuration file

In addition to picking from system environment variables, you can also specify a JSON or INI format configuration file using `file` the parameter

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    pass

env = ServiceEnvironment(file='/path/to/config.json')
```

Declare the corresponding environment variables in the file, as shown in

=== “json”
	```json
	{
	    "DB_USER": "my_user",
	    "DB_PASSWORD": "my_password"
	}
	```
=== “ini”
	```ini
	DB_USER=my_user
	DB_PASSWORD=my_password
	```

!!! tip

## Run the service

The UtilMeta service instance provides a `run()` method to run the service, and we’ve already seen its use.
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

We usually call this `service.run()` in ` __name__ == '__main__'` the section, so you can run the service by executing this file in python, for example

```
python server.py
```

The `run()` method will execute the corresponding operation policy according to the `backend` service instance, such as

* ** Django **: Runs the service by invoking a `runserver` command. Not recommended for production environments.
* ** Flask **: Directly call the method of the Flask application `run()` to run the service
* ** Starlette/FastAPI **: The running service will be used `uvicorn`
* ** Sanic **: Directly call the method of Sanic application `run()` to run the service
* ** Tornado **: Use `asyncio.run` Run Service

### Customize the run

For Flask, Sanic and other frameworks, you can `service.application()` get the generated Flask application and Sanic application, so you can also directly call their `run()` methods to pass in the parameters supported by the corresponding framework.

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

## Deploy the service

Through `run()` this method, we can quickly run an accessible service instance during debugging, but in actual deployment, we often need additional configuration to make the service run stably at the address we expect and give full play to the performance of the running environment.

A common deployment architecture for API services developed in Python is

![ BMI API Doc ](https://utilmeta.com/assets/image/server-deploy.png)

Run your API service on a WSGI server such as uwsgi/gunicorn or an ASGI server such as Daphne for more efficient multi-worker management and request distribution

Then use a reverse proxy service (such as Nginx) to resolve the root route of the API to the port provided by the WSGI/ASGI server. At the same time, it can proxy static files such as images or HTML, and then provide HTTP service at port 80 or HTTPS service at port 443 as required.

However, because different runtime frameworks have different features, we recommend that you choose a deployment strategy based on what you use `backend`.

* **Django**: WSGI application is generated by default and can be deployed using uWSGI/Gunicorn. If it is an ASGI application generated by asynchronous service, it can also be deployed using Daphne ASGI server.
* **Flask**: Generate a WSGI application that can be deployed using uWSGI/Gunicorn
* **Sanic**: It is a multi-process service application and can directly use the Nginx proxy.
* **Starlette/FastAPI**: Gunicorn deployment with Uvicorn worker can be used
* **Tornado**: It is an asynchronous service application and can directly use the Nginx proxy.

!!! tip

### uWSGI

Before using uWSGI, you need to install
```
pip install uwsgi
```

You can then use the `ini` file to write a uwsgi configuration file, such as
```ini
[uwsgi]
module = server:app
chdir = /path/to/your/project
daemonize = /path/to/your/log
workers = 5
socket=127.0.0.1:8000
```

The important parameters include

*  `chdir`: Specify the running directory of the service, usually the root directory of the project.
*  `module`: Specifies the WSGI application of your service, relative to the running directory of the service. Assuming that your WSGI application is located in `server.py` the `app` property, you can use `server:app` the definition.
*  `daemonize`: Set the log file address
*  `workers`: Set the number of processes the service runs, which can generally be set to the number of CPUs of the server X 2 + 1
*  `socket`: The socket address monitored by the uwsgi service, which is used to communicate with the proxy server such as Nginx in front.

The command to run the uwsgi server is as follows

```
uwsgi --ini /path/to/your/uwsgi.ini
```

### Gunicorn

Gunicorn needs to be installed before use
```
pip install gunicorn
```

After that, you can write Gunicorn’s configuration files directly using Python files, such as

```python
wsgi_app = 'server:app'
bind = '127.0.0.1:8000'
workers = 5
accesslog = '/path/to/your/log/access.log'
errorlog = '/path/to/your/log/error.log'
```

The main parameters are

*  `wsgi_app`: a reference to the WSGI application that specifies your service. Assuming your WSGI application is located in `server.py` the `app` property in, you can use `server:app` the definition.
*  `bind`: The address of the service listener, which is used to communicate with the proxy server such as Nginx in the front.
*  `workers`: Set the number of processes the service runs, which can generally be set to the number of CPUs of the server X 2 + 1
*  `accesslog`: Set the access log address of the service
*  `errorlog`: Set the running error log address for the service

In addition, you can specify the implementation of the worker process by using `worder_class` the attribute, which can optimize the running efficiency according to the type of interface, such as

*  `'uvicorn.workers.UvicornWorker'`: Suitable for asynchronous interfaces, such as Starlette/FastAPI, need to be installed first
*  `'gevent'`: Suitable for synchronous interfaces, such as Django/Flask, which use `gevent` coroutines (green threads) in the library to improve the concurrency performance of the interface, need to be installed first

The command to run the gunicorn server is

```
gunicorn -c /path/to/gunicorn.py
```

### Nginx

For the API service using uWSGI, assuming it is running on port 8000, the configuration of Nginx is roughly

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

For Gunicorn or other services running directly, assuming that it is running on port 8000, the configuration of Nginx is roughly

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

You should place the configured nginx file in. `/etc/nginx/sites-enabled/` To enable the corresponding configuration, you can use the following command to detect whether there is a problem with the configuration.

```
nginx -t
```

If there are no problems, you can restart the nginx service with the following command to make the updated configuration take effect

```
nginx -s reload
```

## API Management

UtilMeta will soon support full-cycle API management capabilities, including

* API documentation and debugging
* Log query
* Interface monitoring, server monitoring
* Alarm notification, event management
* Timed task scheduling

At present, the Beta version of waitlist has been opened on the platform and can be [ UtilMeta Official Site ](https://utilmeta.com) added to it.

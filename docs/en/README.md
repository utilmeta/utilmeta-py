# UtilMeta - Quick Guide
<img src="https://utilmeta.com/img/py-intro.png" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="600"/>

UtilMeta is a progressive meta-framework for backend applications, which efficiently builds declarative APIs based on the Python type annotation standard, and supports the integration of mainstream Python frameworks as runtime backend

<a href="https://pypi.org/project/utilmeta/" target="_blank">
	<img src="https://img.shields.io/pypi/v/utilmeta" alt="">
</a>
<a href="https://pypi.org/project/utilmeta/" target="_blank">
	<img src="https://img.shields.io/pypi/pyversions/utilmeta" alt="">
</a>
<a href="https://github.com/utilmeta/utilmeta-py/blob/main/LICENSE" target="_blank">
	<img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="">
</a>
<a href="https://github.com/utilmeta/utilmeta-py/actions?query=branch%3Amain+" target="_blank">
	<img src="https://img.shields.io/github/actions/workflow/status/utilmeta/utilmeta-py/test.yaml?branch=main&label=CI" alt="">
</a>

* Homepage: [https://utilmeta.com/py](https://utilmeta.com/py)
* Source Code: <a href="https://github.com/utilmeta/utilmeta-py" target="_blank"> https://github.com/utilmeta/utilmeta-py</a>
* Author: <a href="https://github.com/voidZXL" target="_blank">@voidZXL</a>

## Core features

### Progressive Meta Framework
UtilMeta developed a standard that support all major Python web framework like **django**, **flask**, **fastapi** (starlette), **sanic**, **tornado** as runtime backend, and support current projects using these frameworks to develop new API using UtilMeta progressivelycompatibility with multiple technology stacks, and asynchronous interface support

### Declarative Development
Using the declarative power from UtilMeta, you can easily write APIs with auto request validation, efficient ORM queries, and auto OpenAPI document generation

### Highly Flexible & Extensible
UtilMeta is highly flexible with a series of plugins includes authentication (Session/JWT), cross origin, rate limit, retry, and can be extended to support more features.

### Full-lifecycle DevOps Solution
The [UtilMeta Platform](https://utilmeta.com/) provided the full-lifecycle DevOps solution for this framework, the API Docs, Debug, Logs, Monitoring, Alerts, Analytics will all been taken care of in the platform

## Installation
```shell
pip install -U utilmeta
```

!!! note
	UtilMeta requires Python>=3.8

## Hello World
 Create a Python file named `server.py` and write the following code 
```python
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
    backend=django,    # or flask / starlette / tornado / sanic
    api=RootAPI,
    route='/api'
)

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
```

!!! note
	You can use `flask`, `starlette`, `sanic`, `tornado` instead of `django` as runtime backend, just install them first and replace them in the demo code

### Run
You can execute this file by python to run the server
```shell
python server.py
```
The following info Implies that the service has live
```
Running on http://127.0.0.1:8000
Press CTRL+C to quit
```
Then we can use our browser to open [http://127.0.0.1:8000/api/hello](http://127.0.0.1:8000/api/hello) to call this API directly, we will see
```
world
```
It means this API works

## How to read this document

We have several introductory case tutorials from easy to complex, covering most usage of the framework. You can read and learn in the following order.

1. [BMI Calculation API](tutorials/bmi-calc)
2. [User Login & RESTful API](tutorials/user-auth)
3. [Realworld Blog Project](tutorials/realworld-blog)
4. Websocket Chatroom (coming soon)

If you prefer to learn from a specific feature, you can refer to

* [Handle Request](guide/handle-request): How to handle path, query parameters, request body, file upload, request headers and cookies.
* [API Class and Routing](guide/api-route) How to use API class mounts to define tree-like API routing, and use  hooks to easily reuse code between APIs, handle errors, and template responses.
* [Data query and ORM operation ](guide/schema-query) How to use Schema to declaratively write the CRUD query, and ORM operations required by a RESTful interface.
* [API Authentication](guide/auth): How to use Session, JWT, OAuth and other methods to authenticate the request of the interface, get the current request's user and simplify the login operation
* [Config, Run & Deploy](guide/config-run): How to configure the run settings, startup, and deployment of a service using features such as declarative environment variables
* [Migrate from current project](guide/migration) How to progressively integrate UtilMeta API to an existing backend project or migrate to UtilMeta
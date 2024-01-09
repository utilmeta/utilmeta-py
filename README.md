# UtilMeta API Framework - Python
<img src="https://utilmeta.com/img/py-intro.png" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="720"/>

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
* Documentation: [https://docs.utilmeta.com/py/en/](https://docs.utilmeta.com/py/en/)
* Author: <a href="https://github.com/voidZXL" target="_blank">@voidZXL</a>
* License: Apache 2.0

## Installation
```
pip install utilmeta
```

## Core Features

### Declarative Development
Using the declarative power from UtilMeta, you can easily write APIs with auto request validation, efficient ORM queries, and auto OpenAPI document generation
<img src="https://utilmeta.com/img/py.section1.png" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="720"/>
### Progressive Meta Framework
UtilMeta developed a standard that support all major Python web framework like **django**, **flask**, **fastapi** (starlette), **sanic**, **tornado** as runtime backend, and support current projects using these frameworks to develop new API using UtilMeta progressively
<img src="https://utilmeta.com/img/py.section2.png" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="720"/>
### Highly Flexible & Extensible
UtilMeta is highly flexible with a series of plugins includes authentication (Session/JWT), cross origin, rate limit, retry, and can be extended to support more features.

### Full-lifecycle DevOps Solution
The [UtilMeta Platform](https://utilmeta.com/) provided the full-lifecycle DevOps solution for this framework, the API Docs, Debug, Logs, Monitoring, Alerts, Analytics will all been taken care of in the platform
<img src="https://utilmeta.com/img/py.section3.png" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="720"/>
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

> You can use `flask`, `starlette`, `sanic`, `tornado` instead of `django` as runtime backend, just install them first and replace them in the demo code

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

## Quick Guide
We have several introductory case tutorials from easy to complex, covering most usage of the framework. You can read and learn in the following order.

1. [BMI Calculation API](https://docs.utilmeta.com/py/en/tutorials/bmi-calc)
2. [User Login & RESTful API](https://docs.utilmeta.com/py/en/tutorials/user-auth)
3. [Realworld Blog Project](https://docs.utilmeta.com/py/en/tutorials/realworld-blog)
4. Websocket Chatroom (coming soon)

If you prefer to learn from a specific feature, you can refer to

* [Handle Request](https://docs.utilmeta.com/py/en/guide/handle-request): How to handle path, query parameters, request body, file upload, request headers and cookies.
* [API Class and Routing](https://docs.utilmeta.com/py/en/guide/api-route) How to use API class mounts to define tree-like API routing, and use  hooks to easily reuse code between APIs, handle errors, and template responses.
* [Schema query and ORM](https://docs.utilmeta.com/py/en/guide/schema-query) How to use Schema to declaratively write the CRUD query, and ORM operations required by a RESTful interface.
* [API Authentication](https://docs.utilmeta.com/py/en/guide/auth): How to use Session, JWT, OAuth and other methods to authenticate the request of the interface, get the current request's user and simplify the login operation
* [Config, Run & Deploy](https://docs.utilmeta.com/py/en/guide/config-run): How to configure the run settings, startup, and deployment of a service using features such as declarative environment variables
* [Migrate from current project](https://docs.utilmeta.com/py/en/guide/migration) How to progressively integrate UtilMeta API to an existing backend project or migrate to UtilMeta

## Community
Join our community to build great things together

* [Discord](https://discord.gg/JdmEkFS6dS)
* [X(Twitter)](https://twitter.com/@utilmeta)
* [Reddit](https://www.reddit.com/r/utilmeta)
* [中文讨论区](https://lnzhou.com/channels/utilmeta/community)

## Enterprise Solutions & Support
The UtilMeta team is providing custom solutions and enterprise-level support at

* [https://utilmeta.com/solutions](https://utilmeta.com/solutions)

You can also contact us in [this page](https://utilmeta.com/about#contact)

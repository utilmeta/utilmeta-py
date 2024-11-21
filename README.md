# UtilMeta Python Framework

<img src="https://utilmeta.com/img/logo-main-gradient.png" style="width: 200px" alt="">

**UtilMeta** Python framework is a progressive meta-framework to develop and manage backend applications, building declarative API & ORM efficiently based on the Python type annotation standard with both sync & async syntax, and supports using mainstream Python frameworks as runtime backend

* Homepage: [https://utilmeta.com/py](https://utilmeta.com/py)
* Documentation: [https://docs.utilmeta.com/py/en/](https://docs.utilmeta.com/py/en/)
* Author: <a href="https://github.com/voidZXL" target="_blank">@voidZXL</a>
* Language: [![en](https://img.shields.io/badge/lang-English-blue.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.md) [![zh](https://img.shields.io/badge/lang-中文-green.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.zh.md)

<a href="https://pypi.org/project/utilmeta/" target="_blank">
	<img src="https://img.shields.io/pypi/v/utilmeta" alt="">
</a>
<a href="https://pypi.org/project/utilmeta/" target="_blank">
	<img src="https://img.shields.io/pypi/pyversions/utilmeta" alt="">
</a>
<a href="https://pepy.tech/project/utilmeta" target="_blank">
	<img src="https://pepy.tech/badge/utilmeta/month" alt="">
</a>
<a href="https://github.com/utilmeta/utilmeta-py/blob/main/LICENSE" target="_blank">
	<img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="">
</a>
<a href="https://github.com/utilmeta/utilmeta-py/actions?query=branch%3Amain+" target="_blank">
	<img src="https://img.shields.io/github/actions/workflow/status/utilmeta/utilmeta-py/test.yaml?branch=main&label=CI" alt="">
</a>


## Installation
```
pip install utilmeta
```

> UtilMeta requires Python >= 3.8

## Core Features

### Declarative API & ORM

with UtilMeta, you can easily write declarative APIs with auto request validation, efficient ORM queries, and auto OpenAPI document generation, here is an example from [mini_blog/blog/api.py](https://github.com/utilmeta/utilmeta-py/blob/main/examples/mini_blog/blog/api.py)

```python
from utilmeta.core import api, orm
from .models import User, Article
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str

class ArticleAPI(api.API):
    async def get(self, id: int) -> ArticleSchema:
        return await ArticleSchema.ainit(id)
```

if you request the ArticleAPI like `GET /article?id=1`, you will get the result like

```python
{
  "id": 1,
  "author": {
    "username": "alice",
    "articles_num": 3
  },
  "content": "hello world"
}
```
This is just what you declared, UtilMeta will generate optimized ORM queries automatically based on your declared schemas, prevent N+1 problem and also generate OpenAPI document for your APIs

### Progressive Meta Framework
UtilMeta built a standard that support most major Python web frameworks as runtime backend, and support current projects using these frameworks to develop new API using UtilMeta progressively

Currently supported backends:

* **Django** (also Django REST framework)
* **Flask** (also APIFlask)
* **FastAPI** (also Starlette)
* **Sanic**
* **Tornado**

You can change the entire runtime backend with a single line of code, Here is a hello world example of UtilMeta
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
    backend=django,    # or flask / fastapi / starlette / sanic / tornado
    api=RootAPI,
    route='/api'
)

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
```

You can create a Python file with the above code and run it to check it out.

## Quick Start

you can start by easily start by clone out repo and run an example 

```shell
pip install -U utilmeta
git clone https://github.com/utilmeta/utilmeta-py
cd utilmeta-py/examples/mini_blog
meta migrate        # migrate databases
meta run            # or python server.py
```

The following info Implies that the service has live
```
| UtilMeta (version) starting service [blog]
|     version: 0.1.0
|       stage: ● debug
|     backend: fastapi (version) | asynchronous
|    base url: http://127.0.0.1:8080
```

### Connect
When you started your service, you can see a line of output
```
UtilMeta OperationsAPI loaded at http://127.0.0.1:8080/ops, connect your APIs at https://ops.utilmeta.com
```

this indicates that UtilMeta Operations system is loaded successfully, you
You can connect your APIs by open this link: [https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8080/ops](https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8080/ops)

Click **API** and your will see the generated API document, you can debug your API here
<img src="https://utilmeta.com/assets/image/connect-local-api.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
With your local API connected, you can use these features

* **Data**: Manage database data (CRUD), in this example, you can add `user` and `article` instance
* **API**: view and debug on auto generated API document
* **Logs**: query realtime request logs, view request and response data, error tracebacks
* **Servers**: view realtime metrics of service resources like servers, databases, caches

> Using other management features requires you to connect a online service with public network address
## Document Guide
We have several introductory case tutorials from easy to complex, covering most usage of the framework. You can read and learn in the following order.

1. [BMI Calculation API](https://docs.utilmeta.com/py/en/tutorials/bmi-calc)
2. [User Login & RESTful API](https://docs.utilmeta.com/py/en/tutorials/user-auth)
3. [Realworld Blog Project](https://docs.utilmeta.com/py/en/tutorials/realworld-blog)
4. Websocket Chatroom (coming soon)

If you prefer to learn from a specific feature, you can refer to

* [Handle Request](https://docs.utilmeta.com/py/en/guide/handle-request): How to handle path, query parameters, request body, file upload, request headers and cookies.
* [API Class and Routing](https://docs.utilmeta.com/py/en/guide/api-route) How to use API class mounts to define tree-like API routing, and use  hooks to easily reuse code between APIs, handle errors, and template responses.
* [Schema Query and ORM](https://docs.utilmeta.com/py/en/guide/schema-query) How to use UtilMeta to write declarative ORM queries for RESTful API.
* [API Authentication](https://docs.utilmeta.com/py/en/guide/auth): How to use Session, JWT, OAuth and other methods to authenticate the request of the interface, get the current request's user and simplify the login operation
* [Declarative Web Client](https://docs.utilmeta.com/py/en/guide/client): Use the declarative syntax identical to API to write request client code, and genrate client code based on UtilMeta service or OpenAPI docs

If your APIs are developed, and want to know how to config, run and manage your APis, check

* [Config, Run & Deploy](https://docs.utilmeta.com/py/en/guide/config-run): How to configure the run settings, startup, and deployment of a service using features such as declarative environment variables
* [Connect & Operations](https://docs.utilmeta.com/py/en/guide/ops): How to connect and manage your API service 

## Community
Join our community to build great things together

* [Discord](https://discord.gg/JdmEkFS6dS)
* [X(Twitter)](https://twitter.com/@utilmeta)
* [Reddit](https://www.reddit.com/r/utilmeta)

## Enterprise Solutions & Support
The UtilMeta team is providing custom solutions and enterprise-level support at

* [https://utilmeta.com/solutions](https://utilmeta.com/solutions)

You can also contact us in [this page](https://utilmeta.com/about#contact)

### Wechat

Contact the creator's wechat (voidZXL) for support or join the developers wechat group

<img src="https://utilmeta.com/img/wx_voidzxl.jpg" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="200"/>

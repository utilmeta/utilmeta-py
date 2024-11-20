# UtilMeta Python 框架

<img src="https://utilmeta.com/img/logo-main-gradient.png" style="width: 200px" alt="">

**UtilMeta** 是一个面向服务端应用的渐进式 Python 后端元框架，基于 Python 类型注解标准高效构建声明式 API 与 ORM，支持使用主流 Python 框架作为运行时实现或渐进式整合

* 主页：[https://utilmeta.com/zh/py](https://utilmeta.com/zh/py)
* 代码：<a href="https://github.com/utilmeta/utilmeta-py" target="_blank">https://github.com/utilmeta/utilmeta-py</a>
* 作者：<a href="https://github.com/voidZXL" target="_blank">@voidZXL</a>
* 语言：[![en](https://img.shields.io/badge/lang-English-blue.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.md) [![zh](https://img.shields.io/badge/lang-中文-green.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.zh.md)

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

## 安装

```shell
pip install -U utilmeta
```

> UtilMeta 需要 Python >= 3.8

## 核心特性

### 声明式 API 与 ORM

你可以使用 UtilMeta 框架的声明式 API 与 ORM 语法轻松构建 RESTful API, 下面是一个来自 [mini_blog/blog/api.py](https://github.com/utilmeta/utilmeta-py/blob/main/examples/mini_blog/blog/api.py) 的示例

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

当年请求 `GET /article?id=1` 到 ArticleAPI，API 会返回类似如下的响应

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

可以看到它与你在代码中的声明完全一致，UtilMeta 会自动生成优化后的 ORM 查询，并将结果转化为你定义的类型与结构，自动避免 N+1 查询问题，并且会根据你的声明生成对应的 OpenAPI 文档

### 渐进式元框架

UtilMeta 内置了一套标准支持大部分主流 Python 框架作为 HTTP 运行时实现，灵活兼容多种技术栈，支持异步接口

当前支持的框架包括

* **Django** (与 Django REST framework)
* **Flask** (与 APIFlask)
* **FastAPI** (与 Starlette)
* **Sanic**
* **Tornado**

你可以仅用一个参数切换 API 服务的整个底层实现，比如下面的 hello world 示例代码
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

你可以创建一个 Python 文件写入并运行以上代码试试看

## 快速开始

你可以通过 clone 仓库并运行其中的示例项目来快速开始
```shell
pip install -U utilmeta
git clone https://github.com/utilmeta/utilmeta-py
cd utilmeta-py/examples/mini_blog
meta migrate        # 生成数据库
meta run            # 或 python server.py
```

当看到如下提示即说明启动成功
```
| UtilMeta (version) starting service [blog]
|     version: 0.1.0
|       stage: ● debug
|     backend: fastapi (version) | asynchronous
|    base url: http://127.0.0.1:8080
```

### 连接你的 API

当我们启动项目时，我们会看到以下的输出
```
UtilMeta OperationsAPI loaded at http://127.0.0.1:8080/ops, connect your APIs at https://ops.utilmeta.com
```

说明项目的运维管理 API 成功加载，我们可以直接点击这个连接：  [https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8080/ops](https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8080/ops)  连接到你的 API 服务

点击左侧 **API** 板块即可看到生成的 API 文档
<img src="https://utilmeta.com/assets/image/connect-local-api.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
本地 API 在连接平台后可以使用以下功能

* **Data**: 数据管理 CRUD，比如在上面的例子中，你可以进入添加 `user` 与 `article` 实例
* **API**：查看并调试自动生成的 API 文档
* **Logs**：查询实时请求日志，包括请求和响应的数据，错误调用栈等
* **Servers**：查询服务依赖的资源的实时监控数据，如服务器，数据库，缓存

> 使用其他的功能需要连接有公开访问地址的 API 服务

## 如何阅读本文档

我们设计了几个由易到难的入门案例由浅入深地涵盖了大部分框架的用法，你可以按照下面的顺序阅读与学习

1. [BMI 计算 API](https://docs.utilmeta.com/py/zh/tutorials/bmi-calc)
2. [用户注册登录查询 API](https://docs.utilmeta.com/py/zh/tutorials/user-auth)
3. [Realworld 博客项目](https://docs.utilmeta.com/py/zh/tutorials/realworld-blog)
4. Websocket 聊天室（即将提供）

如果你更希望从具体功能或用法入手学习，则可以参考

* [处理请求参数](https://docs.utilmeta.com/py/zh/guide/handle-request)：如何处理路径参数，查询参数，请求体和请求头，以及如何处理文件上传
* [API 类与接口路由](https://docs.utilmeta.com/py/zh/guide/api-route)：如何使用 API 类挂载简洁地定义树状接口路由，以及利用钩子等特性方便地在接口间复用代码，处理错误，模板化响应
* [数据查询与 ORM 操作](https://docs.utilmeta.com/py/zh/guide/schema-query)：如何使用 Schema 声明式地编写 RESTful 接口所需要的增删改查和 ORM 操作
* [接口与用户鉴权](https://docs.utilmeta.com/py/zh/guide/auth)：如何使用 Session, JWT, OAuth 等方式为接口的请求鉴权，获取当前请求用户与简化登录操作
* [声明式 Web 客户端](https://docs.utilmeta.com/py/zh/guide/client)：使用与 API 类一致的声明式语法快速编写客户端 SDK 代码，以及为现有的 UtilMeta 服务与 OpenAPI 文档自动生成客户端代码

如果你已经开发好了 UtilMeta 项目，希望了解如何配置，部署与运维管理你的 API 服务，可以参考

* [配置运行与部署](https://docs.utilmeta.com/py/zh/guide/config-run)：如何使用声明式环境变量等特性配置服务的运行设置，启动与部署
* [运维监控与服务管理](https://docs.utilmeta.com/py/zh/guide/ops)：如何配置 UtilMeta 的运维管理系统，全方位观测与管理本地与在线的 API 服务，以及连接你的现有 Django, Flask, FastAPI, Sanic 应用

## 社区

添加作者微信 (voidZXL) 加入开发者群，验证信息 UtilMeta

<img src="https://utilmeta.com/img/wx_voidzxl.jpg" href="https://utilmeta.com/py" target="_blank"  alt="drawing" width="200"/>

# UtilMeta - 入门指引

<img src="https://utilmeta.com/img/logo-main-gradient.png" style="width: 200px" alt="">

**UtilMeta** 是一个面向服务端应用的渐进式元框架，基于 Python 类型注解标准高效构建声明式接口与 ORM，支持使用主流 Python 框架作为运行时实现或渐进式整合

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

* 主页：[https://utilmeta.com/zh/py](https://utilmeta.com/zh/py)
* 代码：<a href="https://github.com/utilmeta/utilmeta-py" target="_blank">https://github.com/utilmeta/utilmeta-py</a>
* 作者：<a href="https://github.com/voidZXL" target="_blank">@voidZXL</a>
* 语言：[![en](https://img.shields.io/badge/lang-English-blue.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.md) [![zh](https://img.shields.io/badge/lang-中文-green.svg)](https://github.com/utilmeta/utilmeta-py/blob/main/README.zh.md)

## 核心特性

* **渐进式元框架**：使用一套标准支持 django, flask, fastapi (starlette), sanic, tornado 等主流 Python 框架作为 HTTP 运行时实现（切换实现只需一个参数），支持从以上框架的现有项目使用 UtilMeta 进行渐进式开发，灵活兼容多种技术栈，支持异步接口
* **声明式接口与 ORM**：快速产出简洁代码，自动根据声明完成请求校验，响应构建与生成 OpenAPI 标准文档，内置高效的声明式 ORM 标准，支持 django 等查询引擎
* **高度可扩展与丰富的插件**：内置一系列可灵活接入的鉴权（session/jwt），跨域处理，重试，请求控制，事务等插件

## 安装

```shell
pip install -U utilmeta
```

!!! note
	UtilMeta 需要 Python >= 3.8

## Hello World

我们新建一个名为 `server.py` 的 Python 文件，并在其中写入以下代码

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
	除了例子中的 `django` 外，你可以选择其他的框架作为 backend，但你需要先安装它们

## 运行项目

我们可以直接运行这个文件来启动 API 服务
```shell
python server.py
```

当看到如下提示即说明启动成功
```
Running on http://127.0.0.1:8000
Press CTRL+C to quit
```

接着我们可以直接使用浏览器访问 [http://127.0.0.1:8000/api/hello](http://127.0.0.1:8000/api/hello) 来调用 API，可以看到
```
world
```

说明项目启动成功

## 如何阅读本文档

我们设计了几个由易到难的入门案例由浅入深地涵盖了大部分框架的用法，你可以按照下面的顺序阅读与学习

1. [BMI 计算 API](tutorials/bmi-calc)
2. [用户注册登录查询 API](tutorials/user-auth)
3. [Realworld 博客项目](tutorials/realworld-blog)
4. Websocket 聊天室（即将提供）


如果你更希望从具体功能或用法入手学习，则可以参考

* [处理请求参数](guide/handle-request)：如何处理路径参数，查询参数，请求体和请求头，以及如何处理文件上传
* [API 类与接口路由](guide/api-route)：如何使用 API 类挂载简洁地定义树状接口路由，以及利用钩子等特性方便地在接口间复用代码，处理错误，模板化响应
* [数据查询与 ORM 操作](guide/schema-query)：如何使用 Schema 声明式地编写 RESTful 接口所需要的增删改查和 ORM 操作
* [接口与用户鉴权](guide/auth)：如何使用 Session, JWT, OAuth 等方式为接口的请求鉴权，获取当前请求用户与简化登录操作
* [配置运行与部署](guide/config-run)：如何使用声明式环境变量等特性配置服务的运行设置，启动与部署
* [从现有项目迁移](guide/migration)：如何从现有的后端项目中渐进式地接入 UtilMeta 接口或迁移到 UtilMeta
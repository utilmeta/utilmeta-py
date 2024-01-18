# 处理请求参数

API 请求可以使用多种方式携带参数信息，如

* 路径参数
* 查询参数
* 请求体（JSON/表单/文件等）
* 请求头（包括 Cookie）

我们将会一一介绍如何在 UtilMeta 中处理请求的各类参数

!!! tip
	UtilMeta 中请求参数的声明基于 Python 标准的类型注解（类型提示）语法与 [utype](https://utype.io/zh/) 库，如果你对 Python 类型注解语法还不熟悉，可以参考 [utype - Python 类型用法](https://utype.io/zh/guide/type/) 这篇文档

## 路径参数

在请求 URL 路径中传递数据是一种常见的方式，比如通过 `GET /article/3` 得到 ID 为 3 的文章数据，ID 的参数就是在 URL 路径中提供的，在 UtilMeta 中声明路径参数的方式如下
```python hl_lines="4"
from utilmeta.core import api

class RootAPI(api.API):
	@api.get('article/{id}')
	def get_article(self, id: int):
		return {"id": id}
```

我们在 `@api` 装饰器的第一个参数传入路径的模板字符串，如例子中的 `'article/{id}'`，使用花括号定义路径参数，并且在函数中声明一个同名的参数用来接收，并且可以声明期望的类型与规则

定义多个路径参数的用法类似
```python
from utilmeta.core import api
import utype
from typing import Literal

class RootAPI(api.API):
	@api.get('doc/{lang}/{page}')
	def get_doc(self, 
	           lang: Literal['en', 'zh'], 
	           page: int = utype.Param(1, ge=1)):
		return {"lang": lang, "page": page}
```
在这个例子中我们声明了两个路径参数：

* `lang` 只能在 `'en'` 和 `'zh'` 中取值
* `page` 是一个大于等于 1 且默认为 1 的参数
 
有默认值的参数如果没有在路径中提供则会直接传入默认值，于是当我们请求 `GET /doc/en` 时我们会得到输出
```json
{"lang": "en", "page": 1}
```

!!! tip
	如果路径中缺少没有提供默认值的参数，则会返回 `404 Notfound` 响应，比如当访问 `GET /doc` 时

如果请求参数不满足声明的规则或者无法转化到对应的类型，则会得到 `400 BadRequest` 的错误响应，比如 

* `GET /doc/fr/3` ：`lang` 参数没有在 `'en'` 和 `'zh'` 中取值
* `GET /doc/en/0` ：`page` 参数不符合大于等于一的规则

!!! warning
	多个路径参数之间必须有字符串进行分割，`'{category}{page}'` 就是一个无效的路径参数字符串，因为路径参数之间无法进行区分

### 路径正则表达式

我们有时需要路径参数满足一定的规则，这时我们可以通过声明正则表达式轻松做到这一点，使用方式如下
```python
from utilmeta.core import api, request

class RootAPI(API):
    @api.get('item/{code}')
    def get_item(self, code: str = request.PathParam(regex='[a-z]{1,9}')):
        return code
```

在 UtilMeta 的 `request` 模块中内置了一些常用的路径参数配置

* `request.PathParam`：默认的路径参数规则，即 `'[^/]+'`，匹配除了路径下划线外的所有字符
* `request.FilePathParam`：匹配所有的字符串，包括路径下划线，常用于当路径参数需要传递文件路径，URL 路径等情况时
* `request.SlugPathParam`：匹配类似 `how-to-guide` 这样由字母数据连接线组成的字符串，尝用于文章的 URL 编码中

以下是一个例子
```python
from utilmeta.core import api, request

class RootAPI(API):
    @api.get('file/{path}')
    def get_file(self, path: str = request.FilePathParam):
        return open(f'/tmp/{path}', 'r')
```

在这个例子中当我们请求 `GET /file/path/to/README.md` 时，`path` 参数可以得到 `'path/to/README.md'` 这一路径

### 声明请求路径

上面的这些例子展示在 UtilMeta 中声明使用模板字符串声明请求路径的方式，但这并不是唯一的方式

在 UtilMeta 中，API 接口请求路径的声明规则为

* 在 `@api`装饰器中传入路径字符串，作为这个接口请求路径的模板
* 没有路径字符串时，函数的名称将作为请求的路径
* 当函数的名称为 HTTP 动词时，其路径将自动设为 `'/'` 并无法被覆盖

!!! tip “API 接口函数”
	在 API 类中使用 `@api.<METHOD>` 装饰器装饰的函数，或名称为 HTTP 动词（get/post/put/patch/delete）的函数，将会被处理为 API 接口函数，对外提供 HTTP 请求访问

下面的例子覆盖了以上的几种情况，可以很清晰地说明路径的声明规则
```python
from utilmeta.core import api

@api.route('/article')
class ArticleAPI(api.API):
    @api.get
    def feed(self): pass
    # GET /article/feed
    
    @api.get('{slug}')
    def get_article(self, slug: str): pass
	# GET /article/{slug}
	
    def get(self, id: int): pass
    # GET /article?id=<ID>
```

!!! tip “路径匹配优先级”
	类似例子中同时声明了固定路径与可变的路径参数的接口时，需要把固定路径的接口声明放在上方，这样 UtilMeta 在匹配 `/article/feed` 请求时会先匹配到 `feed` 函数，而不是作为 `slug` 参数匹配到 `get_article` 函数

## 查询参数

使用查询参数传入键值对是很普遍的传参方式，比如通过 `GET /article?id=3` 得到 ID 为 3 的文章数据

查询参数声明的方式很简单，直接在函数中定义即可，如
```python
from utilmeta.utils import *

class RootAPI(API):
	@api.get
	def doc(self, 
	        lang: Literal['en', 'zh'], 
	        page: int = utype.Param(1, ge=1)):
		return {"lang": lang, "page": page}
```

当我们请求 `GET /doc?lang=en` 时我们会得到输出
```json
{"lang": "en", "page": 1}
```

!!! tip
	在 API 函数中，查询参数是 **默认** 的参数类型，也就是说如果一个参数没有被路径模板定义，也没有指定为其他的参数类型的话，就会被处理成一个查询参数

### 参数别名
如果参数名称无法表示为一个 Python 变量（如语法关键字或含有特殊符号），则可以使用 `utype.Param` 组件的 `alias` 参数指定字段的期望名称，如
```python
from utilmeta.core import api
import utype

class RootAPI(API):
    @api.get
    def doc(self,
            cls_name: str = utype.Param(alias='class'),
            page: int = utype.Param(1, alias='@page')
            ):
        return {cls_name: page}
```

当访问 `GET /api/doc?class=tech&@page=3` 时就会得到 `{"tech": 3}`

### 使用 Schema 类

除了在函数中声明查询参数外，你也可以将所有查询参数定义为一个 Schema 类，从而更好地组合与复用，用法如下
```python hl_lines="11"
from utilmeta.core import api, request
import utype
from typing import Literal

class QuerySchema(utype.Schema):
    lang: Literal['en', 'zh']
    page: int = utype.Field(ge=1, default=1)
    
class RootAPI(API):
    @api.get
    def doc(self, query: QuerySchema = request.Query):
        return {"lang": query.lang, "page": query.page}
```

在例子中，我们将查询参数 `lang` 与 `page` 定义在了 `QuerySchema` 中，然后使用 `query: QuerySchema = request.Query` 注入到 API 函数中

使用这种方式，你可以方便地使用类的继承和组合等方式在接口间复用查询参数

!!! warning
	使用 Schema 类定义的查询参数必须指定 `request.Query` 作为函数参数的默认值，否则这个参数将视为查询参数中的一个字段，你需要请求 `GET /api/doc?query={"lang":"en","page":3}` 才能映射到对应的参数

## 请求体数据

请求体数据常用于在 POST / PUT / PATCH 方法传递对象，表单或文件等数据

通常在 UtilMeta 中，你可以使用 Schema 类来声明 JSON 或表单格式的请求体数据，用法如下
```python  hl_lines="11"
from utilmeta.core import api, request
import utype

class LoginSchema(utype.Schema):
	username: str
	password: str
	remember: bool = False

class UserAPI(api.API):
    @api.post
    def login(self, data: LoginSchema = request.Body):
		pass
```
我们声明了一个名为 LoginSchema 的 Schema 类，作为请求体参数的类型提示，再使用 `Request.Body` 作为参数的默认值标记这个参数是请求体参数

当你使用一个 Schema 类声明请求体，这个接口便拥有了处理  JSOM / XML 和表单数据的能力，比如你可以传递这样的 JSON 请求体
```json
{
	"username": "alice",
	"password": "123abc",
	"remember": true
}
```

你也可以使用 `application/x-www-form-urlencode` 格式的请求体，语法类似于查询参数，如
```
username=alice&password=123abc&remember=true
```

* `request.Body`：基础请求体类型，只需请求体中的数据能够解析到声明的类型即可
* `request.Json`：请求体 Content-Type 需要为 `application/json`
* `request.Form`：请求体 Content-Type 需要为  `multipart/form-data` 或 `application/x-www-form-urlencoded`

### 列表数据
一些如批量创建与更新等场景需要上传列表类型的请求体数据，其声明方式就是在对应的 Schema 类外加上 `List[]` ，如
```python  hl_lines="10"
from utilmeta.core import api, orm, request
from .models import User

class UserAPI(api.API):
	class UserSchema(orm.Schema[User]):
		username: str = utype.Field(regex='[a-zA-Z0-9]{3,20}')
	    password: str = utype.Field(min_length=6, max_length=20)
    
    @api.post
    def batch_create(self, users: List[UserSchema] = request.Body):
		for user in users:
			user.save()
```

如果客户端需要传递列表数据，需要使用 JSON （`application/json`）类型的请求体，如果客户端只传递了一个 JSON 对象或表单，那么将会被自动转化为只有这一个元素的列表

在定义例子中的接口后，可以请求 `POST /api/user/batch`，传递请求体
```json
[{
	"username": "alice",
	"password": "123abc"
}, {
	"username": "bob",
	"password": "XYZ789"
}]
```

### 处理文件上传

如果你需要支持文件上传，只需要将文件字段的类型提示声明为文件即可，用法如下
```python  hl_lines="7"
from utilmeta.core import api, request, file
import utype

class FileAPI(api.API):
	class AvatarData(utype.Schema):
		user_id: int
		avatar: file.Image = utype.Field(max_length=10 * 1024 ** 2)
	
	@api.post
	def avatar(self, data: AvatarData = request.Body):
		pass
```

在 `utilmeta.core.file` 文件中提供了几种常用的文件类型，你可以用它们声明文件参数

* `File`：接收任意类型的文件
* `Image`：接收图片文件（`image/*`）
* `Audio`：接收音频文件（`audio/*`）
* `Video`：接收视频文件（`video/*`）

另外，你可以使用规则参数中的 `max_length` 对文件的大小进行限制，例子中我们限制 `avatar` 只接收 10M 以下的文件

!!! tip
	对于含有文件的表单，客户端需要传递 `multipart/form-data` 类型的数据

如果你需要支持上传多个文件，只需要为文件参数的类型声明外加上 `List[]`  即可，如
```python  hl_lines="8"
from utilmeta.core import api, request, file
import utype
from typing import List

class FileAPI(api.API):
	class FilesData(utype.Schema):
        name: str
        files: List[file.File] = utype.Field(max_length=10)

    @api.post
    def upload(self, data: FilesData = request.Body):
        for i, f in enumerate(data.files):
            f.save(f'/data/{data.name}-{i}')
```

#### 单独上传文件
如果你希望客户端直接将整个二进制文件作为请求体，而不是使用嵌套在表单中的形式的话，只需要将文件参数指定为 `request.Body` 即可，如

```python
from utilmeta.core import api, request, file
import utype

class FileAPI(api.API):
    @api.post
    def image(self, image: file.Image = request.Body) -> str:
	    name = str(int(self.request.time.timestamp() * 1000)) + '.png'
        image.save(path='/data/image', name=name)
```

### 请求体参数

除了支持声明完整的请求体 Schema 外，你还可以使用 `request.BodyParam` 单独声明请求体中的字段
```python
from utilmeta.core import api, request, file

class FileAPI(api.API):
	@api.post
	def upload(self, name: str = request.BodyParam,
	           file: file.File = request.BodyParam):
	    file.save(path='/data/files', name=name)
```

### 字符串与其他类型数据
如果你希望接口接受字符串等形式的请求体，也只需要将对应参数指定请求体即可，如
```python
from utilmeta.core import api, request

class ArticleAPI(api.API): 
	@api.post
	def content(self, html: str = request.Body(
		max_length=10000,
		content_type='text/html'
	)):
		pass
```
在这个函数中，我们使用 `html` 来指定和接收 `'text/html'` 类型的请求体，并且限定了请求体上传文本的最大长度为 10000

## 请求头参数

API 请求通常会携带请求头（HTTP Headers）来传递请求的元信息，如权限凭据，协商缓存，会话 Cookie 等，除了默认的请求头外，你也可以自定义请求头，声明请求头的属性有两种

* `request.HeaderParam`：声明单个请求头参数
* `request.Headers`：声明完整的请求头 Schema

```python
from utilmeta.core import api, request
import utype

class RootAPI(api.API):
	class HeaderSchema(utype.Schema):
		auth_token: str = utype.Field(length=12, alias='X-Auth-Token')
		meta: dict = utype.Field(alias='X-Meta-Data')
	
	@api.post
	def operation(self, headers: HeaderSchema = request.Headers):
		return [headers.auth_token, headers.meta]
```

一般来说自定义的请求头都以 `X-` 开头，并且使用连字符 `-` 连接单词，我们使用 `alias`  参数来指定请求体参数的名称，如示例中声明的请求头参数为

* `auth_token`：目标请求头名称为 `X-Auth-Token`，长度为 12 的字符串
* `meta`：目标请求头的名称为 `X-Meta-Data`，一个能被解析为字典的对象

!!! tip
	请求头是大小写不敏感的，所以你使用  `alias='X-Auth-Token'` 或 `alias='x-auth-token'` 声明的是一样的请求头

当请求
```http
POST /api/operation HTTP/1.1

X-Auth-Token: OZ3tPOl6
X-Meta-Data: {"version":1.2}
```
就会得到 `["OZ3tPOl6", {"version": 1.2}]` 的响应

!!! note
	一般浏览器在发送含有自定义的请求头的请求之前，还会发送一个 `OPTIONS` 请求来检查自定义的请求头是否位于响应中的 `Access-Control-Allow-Headers` 所允许的范围内，不过不用担心，UtilMeta 会自动将你声明的请求头放入 `OPTIONS` 响应中

### 通用参数

常见的情况是，某个请求头需要在多个接口间复用，比如鉴权凭据，此时除了在每个接口中声明同样的参数外，UtilMeta 的 API 类提供了一种更简洁的方式：在 API 类中声明通用参数，用法如下
```python
from utilmeta.core import api, request
import utype

class RootAPI(api.API):
    auth_token: str = request.HeaderParam(alias='X-Auth-Token')
	
    @api.post
	def operation(self):
		return self.auth_token
```

这样在 API 类中定义的所有接口都需要提供 `X-Auth-Token` 这一请求头参数，你还可以直接通过 `self.auth_token` 直接获取到对应的值

### 解析 Cookie

请求头的 cookie 字段可以携带一系列的键值参数用于和服务端保持会话或者携带凭据信息等，Cookie 参数有两种声明方式

* `request.CookieParam`：声明单个 Cookie 参数
* `request.Cookies`：声明完整的 Cookie 对象

```python
from utilmeta.core import api, request

class RootAPI(api.API):
    sessionid: str = request.CookieParam(required=True)
    csrftoken: str = request.CookieParam(default=None)

    @api.post
    def operation(self):
        return [self.sessionid, self.csrftoken]
```

在这个例子中，我们在 RootAPI 类中声明了两个通用的 Cookie 参数，请求可按照如下方式传递 cookie 参数
```http
POST /api/operation HTTP/1.1

Cookie: csrftoken=xxxx; sessionid=xxxx;
```

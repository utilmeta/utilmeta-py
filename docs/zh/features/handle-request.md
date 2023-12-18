# 解析请求参数

在一个 API 请求中可以使用多种方式携带参数信息，如
* 路径参数
* 查询参数
* 请求体（JSON/表单/文件等）
* 请求头（包括 Cookie）

我们将会一一介绍每种参数携带方式的使用方法

## 路径参数
在请求 URL 路径中传递数据是一种常见的方式，我们来看一个例子
```python
from utilmeta.utils import *

class RootAPI(API):
	@api.get('doc/{category}/{page}')
	def get_doc(self, category: str, page: int = 1):
		return {category: page}
```
使用 @api 装饰器的 `path` 参数可以定义路径参数字符串，其中使用了与 Python 格式化字符串相同的语法来声明参数 (`{<name>}`)，其中声明的 `category` 和 `page` 参数在 API 函数中定义了相同的名称用于接受对应的路径参数

于是当我们请求 `GET /api/doc/tech/3` 时我们会得到输出 `{"tech": 3}`
由于 `page` 参数指定了默认值 1，所以当我们请求 `GET /api/doc/tech` 时会得到 `{"tech": 1}`
而因为 `category` 参数没有指定默认值，所以请求 `GET /api/doc` 会得到 `404 Notfound` 的响应

请求参数都需要满足函数参数中声明的类型与规则，如果请求了 `GET /api/doc/tech/NAN` 则会得到 `400 BadRequest` 的错误响应，因为对应的 `page` 参数 `NAN` 无法转化为整数

需要注意的是，使用 `path` 参数定义的路径字符串在 URL 中位于 API 函数名称的后方，如例子中的函数的期望路径是 `/api/doc/{category}/{page}`，如果需要从 API 类的根路由位置声明路径参数，可以参考下一小节路由函数的用法

::: warning
路径参数之间必须有字符串进行分割，`'{category}{page}'` 就是一个不合法的路径参数字符串，因为路径参数之间无法进行区分
:::

#### 路径参数的规则
一般来说，路径参数以下划线分割，所以路径参数的值默认是不能包括下划线的，但是如果你需要将一个文件路径或者 URL 路径作为路径参数，那么这个参数就需要包含下划线了，这种参数声明的方式如下

```python
class RootAPI(API):
    @api.get('@file:{path}.png')
    def get_file(self, name: str, path: str = Request.PathParam):
        return path
```

在例子中  `path`  是需要包含下划线的路径参数，需要将它的默认值设为 `Request.Path`
如果请求 `GET /api/@file:media/image/avatar.png` ，path 参数就会是 `'media/image/avatar'`

#### 默认路径参数
如果请求的 URL 路径无法匹配 API 类中的所有函数，则会抛出 `exc.Notfound` 错误并默认处理为 404 响应，但是你也可以通过指定默认路径参数的方式将无法匹配的路径捕获并处理，默认路径参数的声明方式很简单，就是将参数的默认值设为 `Request.Path`，并且不要在路径参数字符串中声明对应的参数，如
```python
class UserAPI(API):
    def get(self, path: str = Request.PathParam):
        return path
        
class RootAPI(API):
    class Router:
        user = UserAPI
```

在这个例子中， UserAPI 的 get 函数具有了捕获所有路径的能力（但仅限 GET 方法）
如请求 `GET /api/user/any/route` ，path 参数会传入未匹配的路径 `'any/route'`

## 查询参数
使用 URL 中的查询字符串传入键值对是很普遍的传参方式，我们一般称之为查询参数，API 函数中的参数如果没有被路径参数占用，则会被处理为查询参数，如
```python
from utilmeta.utils import *

class RootAPI(API):
	@api.get
	def doc(self, category: str, page: int = 1):
	    return {category: page}
```

如访问 `GET /api/doc?category=tech` 会得到 `{"tech": 1}`
访问 `GET /api/doc?category=tech&page=3` 会得到 `{"tech": 3}`

::: tip
查询字符串是位于 URL 的 `?` 之后，以 `&` 符号分隔，并以 `=` 号连接的一系列键值对组成的字符串
:::


#### 为参数指定别名
如果参数名称无法表示为一个 Python 变量（如为关键字或含有特殊符号），则可以使用 Rule 组件的 `alias` 参数指定字段的期望名称，如
```python
from utilmeta.utils import *

class RootAPI(API):
    @api.get
    def doc(self, 
	    cls_name: str = Rule(alias='class'), 
	    page: int = Rule(alias='@page', default=1)
	):
        return {cls_name: page}
```
访问 `GET /api/doc?class=tech&@page=3` 会得到 `{"tech": 3}`


#### 使用 Schema 类定义查询参数
为了区分参数以及利用 Schema 类的优势，你也可以将查询参数定义为一个 Schema 类，并在 API 函数中使用 `Request.Query` 作为对应的参数值来指定为查询参数，如
```python
from utilmeta.utils import *

class QuerySchema(Schema):
    page: int = Rule(ge=1, default=1)
    item: str = Rule(max_length=10, default=None)
    
class RootAPI(API):
    @api.get
    def doc(self, query: QuerySchema = Request.Query):
        return query
```

`GET /api/doc` 会返回 `{"page": 1, "item": null}`
`GET /api/doc?page=3&item=devops` 会返回 `{"page": 3, "item": "devops"}`

如果请求的数据不符合对应的规则，如 `GET /api/doc?page=0` 则会返回 `400 BadRequest` 响应

::: warning
使用 Schema 类定义的查询参数必须指定 `Request.Query` 作为函数参数的默认值，否则这个参数将视为查询参数中的一个字段，你需要请求 `GET /api/doc?query={"page":3,"item":"devops"}` 才能映射到对应的参数

你只能为最多一个参数指定 `Request.Query`，且这个参数的类型提示必须是 Schema 类或者 `dict`
:::


## 请求体数据
请求体数据常用于传递对象，表单或文件等数据，当接口使用 POST / PUT / PATCH 方法时可以声明与传递请求体数据

#### JSON 与普通表单
最常用的请求体类型就是 JSON 文档和表单了，他们的共同之处就是都使用键值对的方式表示数据，而这正符合了 Schema 类的结构规范，所以声明 JSON 与表单数据的方式就是使用 Schema 类

我们在 快速开始-基本工作流 中的 UserAPI 中已经看到了请求体是如何声明的了，简化的逻辑如
```python
from utilmeta.utils import *

class UserAPI(API):
	class LoginSchema(Schema):
		username: str
	    password: str = Rule(min_length=6, max_length=20)
	    remember: bool = False
    
    @api.post
    def login(self, data: LoginSchema = Request.Body):
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


如果你希望为请求体限制类型（`Content-Type`），可以使用 `Request.Body` 的 `content_type` 参数，如
```python
from utilmeta.core import api, request

class UserAPI(api.API):
	class LoginSchema(Schema):
		username: str
	    password: str = Rule(min_length=6, max_length=20)
	    remember: bool = False
    
    @api.post
    def login(self, data: LoginSchema = request.Body(content_type='application/json')):
		pass
```
此时请求必需上传 JSON（`application/json`）格式的请求体数据


#### 列表型的请求体数据
一些如批量创建与更新等场景需要上传列表类型的请求体数据，其声明方式就是在对应的 Schema 类外加上 `List[]` ，如
```python
from utilmeta.utils improt *
from .models import User

class UserAPI(API):
	class UserSchema(Schema):
		username: str
	    password: str = Rule(min_length=6, max_length=20)
    
    @api.post
    def batch(self, users: List[UserSchema] = Request.Body):
		for user in users:
			User(**user).save()
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

::: tip
例子中的批量创建并不是最佳的方式，只是为了表明请求体数据是一个列表，批量创建可以使用 Bulk 组件或模型 ORM 的 `bulk_create` 方法，能够将批量数据的创建整合为一条 SQL，提高查询性能
:::


### 处理文件上传
如果你希望支持的请求体数据中包含文件，只需要将文件参数的类型提示声明为文件即可，UtilMeta 目前支持的文件类型有
* `File`：默认的文件，任意的文件类型
* `Media.Text`：文本类型文件（`text/*`）
* `Media.Image`：图片类型文件（`image/*`）
* `Media.Audio`：音频类型文件（`audio/*`）
* `Media.Video`：视频类型文件（`video/*`）

我们可以编写一个用于上传和保存图片的 API 来看一下包含文件表单的用法
```python
from utilmeta.utils improt *

class ImageAPI(API):
	media = Media()
	
	class FormData(Schema):
		name: str
		image: Media.Image = File(max_size=10 * Media.MB)
	
	@api.post
	def upload(self, data: FormData = Request.Body):
		return self.media.store(data.image, name=data.name)
```
在我们为请求体指定的数据结构 `FormData` 中，`image` 参数使用了 `Media.Image` 作为类型提示，表明了这个参数需要传入一个图片文件，对应的 File 组件可以看作是解析和校验文件型数据的 Rule 组件，其中可以定义文件后缀名，最高文件大小等规则，如例子中使用 `max_size=10 * Media.MB` 声明了 `image` 传入的图片文件大小不能超过 10 M （如果超过会直接返回 `400 BadRequest`）

::: tip Media 组件
在这个 API 中，我们为属性插槽 `media` 声明了一个 Media 组件实例，并在 API 函数中使用了 Media 的 `store` 方法来将文件存储到磁盘中，下文的 [媒体文件处理 Media 组件](##媒体文件处理-media-组件) 将会详细介绍 Media 组件的用法
:::

对于含有文件的表单，客户端需要传递 `multipart/form-data` 类型的数据，如
`Content-Type: multipart/form-data; boundary=----WebKitFormBoundary`
```multipart/form-data
------WebKitFormBoundary
Content-Disposition: form-data; name="name" 
avatar
------WebKitFormBoundary
Content-Disposition: form-data; name="image"; filename="image.jpg" 
Content-Type: image/jpeg 
------WebKitFormBoundary--
```
以上的数据实际传递的信息会被解析转化为 `FormData(name='avatar', image=<Image: image.jpg>)`

#### 单个参数上传多个文件
在文件表单的文件参数上不仅可以上传单个文件，还可以支持上传多个文件，只需要为文件参数的类型声明外加上 `List[]` ，如
```python
from utilmeta.utils improt *

class ImageAPI(API):
	media = Media()
	
	class FormData(Schema):
		name: str
		images: List[Media.Image] = File(max_size=10 * Media.MB)
	
	@api.post
	def upload(self, data: FormData = Request.Body) -> List[str]:
		urls = []
		for i, image in enumerate(data.images):
			urls.append(self.media.store(image, name=f'{data.name}-{i}'))
		return urls
```

#### 只包含文件的表单
由于文件类型的参数只能通过请求体传递，所以你即使没有指定 `Request.Body` ，但在函数中声明了文件类型的参数，那么这个参数也会作为文件表单请求体的字段，如

```python
class ImageAPI(API):
    media = Media(name_func=Media.name_timestamp)

    @api.post
    def avatar(self, file: Media.Image = File(max_size=500 * Media.KB)) -> str:
        path = self.media.store(file, path='image/avatar')
        user = self.request.user
        user.avatar = path
        user.save()
        return path
```
我们编写了一个名为  `avatar`  的处理用户头像上传和保存的 API 函数 （假设用户有一个名为 `avatar` 的字段保存着头像地址），在函数的参数中直接使用了文件类型的参数 `file`，这样请求这个接口需要上传一个 `multipart/form-data` 类型的表单，其中只包含一个名为 `file` 的字段，对应一个图片文件


#### 单独上传文件
如果你希望客户端直接将整个二进制文件作为请求体，而不是使用嵌套在表单中的形式的话，只需要将文件参数指定为 `Request.Body` 即可，如果你需要为文件给出限制，可以使用  `Request.Body`  中的 `rule` 参数，如

```python
class ImageAPI(API):
    media = Media(name_func=Media.name_timestamp)

    @api.post
    def avatar(self, file: Media.Image = Request.Body(
        rule=File(max_size=500 * Media.KB))) -> str:
        path = self.media.store(file, path='image/avatar')
        user = self.request.user
        user.avatar = path
        user.save()
        return path
```
在这个接口中，客户端需要将用户头像的二进制文件作为请求体上传，并且大小不超过 500k


#### 字符串与其他类型数据
如果你希望接口接受字符串等形式的请求体，也只需要将对应参数指定请求体即可，如
```python
class ArticleAPI(API): 
	@api.post
	def content(self, html: str = Request.Body(
		rule=Rule(max_length=10000),
		content_type='text/html'
	)):
		pass
```
在这个函数中，我们为 `html` 参数指定了 `Request.Body` ，并使用了其中 `rule` 参数定义了上传文本的最大长度为 10000，使用 `content_type` 参数定义了请求体的类型为 `'text/html'`，也就是 HTML 格式


## 请求头参数
任意的 HTTP 请求都可以携带请求头（HTTP Headers）来传递信息，除了默认的请求头外，你也可以自定义一些请求头用于携带请求的元信息，凭据或期望的 API 版本等

声明请求头参数的方式与请求体类似，就是声明一个 Schema 类作为一个函数参数的类型，并将该函数参数指定为 `Request.Headers`，如
```python
class RootAPI(API):
	class HeaderSchema(Schema):
		auth_token: str = Rule(length=12, alias='X-Auth-Token')
		meta: dict = Rule(alias='X-Meta-Data')
	
	@api.post
	def operation(self, headers: HeaderSchema = Request.Headers):
		return [headers.auth_token, headers.meta]
```

在 HeaderSchema 中，我们使用 Rule 组件中的 alias 参数为请求头参数指定实际的请求头名称，一般来说，自定义的请求头都以 `X-` 开头，并且使用连字符 `-` 连接单词，如示例中声明的请求头参数为
* `auth_token`：目标请求头名称为 `X-Auth-Token`
* `meta`：目标请求头的名称为 `X-Meta-Data`

::: tip
由于请求头是大小写不敏感的，所以你使用  `alias='X-Auth-Token'` 或 `alias='x-auth-token'` 声明的是一样的请求头，但如果你没有指定 alias，UtilMeta 就会按照你的参数名称来寻找对应的请求头（依然是大小写不敏感的），对于没有连字符的请求头可以不指定 alias，如 `Cookie` ，但如果参数包含了下划线却没有指定 alias，则是较为不合规范的，一些 HTTP 代理和服务器不允许使用带有下划线的请求头
:::

那么请求一般使用
```http
POST /api/operation HTTP/1.1

X-Auth-Token: OZ3tPOl6
X-Meta-Data: {"version":1.2}
```
就会得到 `["OZ3tPOl6", {"version": 1.2}}` 的响应

::: tip
一般浏览器在发送含有自定义的请求头的请求之前，还会发送一个 OPTIONS 请求来检查自定义的请求头是否位于响应中的 `Access-Control-Allow-Headers` 所允许的范围内，不过不用担心，UtilMeta 会自动将你声明的请求头放入 OPTIONS 响应中
:::

请求头参数的另一种声明方式是使用请求的**处理前钩子**（before hook），处理前钩子函数中声明的所有参数都会被处理为请求头参数，我们会在后面具体介绍


### 解析 Cookie
请求头的 cookie 字段可以携带一系列的 HTTP Cookies 用于和服务端保持会话或者携带凭据和信息等，声明 Cookie 参数的方式就是在请求头的 Schema 类中再定义一个名为 `cookie` 的 Schema 类，将 Cookie 中需要携带的字段声明出来，如
```python
class RootAPI(API):
	class HeaderSchema(Schema):
		auth_token: str = Rule(length=12, alias='X-Auth-Token')
		
		class cookie(Schema):
			sessionid: str
			csrftoken: str
			access_key: str = Rule(length=32, default=None)
	
	@api.post
	def operation(self, headers: HeaderSchema = Request.Headers):
		return [headers.auth_token, headers.cookie]
```
在这个例子中，我们在请求头对象 HeaderSchema 中声明了一个名为  `cookie` 的 Schema 类，其中指定了 `sessionid`, `csrftoken` 和 `access_key` 作为 cookie 字段，对应请求的格式就需要是

```http
POST /api/operation HTTP/1.1

X-Auth-Token: OZ3tPOl6
Cookie: csrftoken=xxxx; sessionid=xxxx; access_key=xxxxx;
```

::: tip
sessionid 是使用 Session 鉴权策略时承载会话标识的默认 cookie 字段名称，csrftoken 是启用了 CSRF 防护后携带 CSRF Token 的默认 cookie 字段名称
:::

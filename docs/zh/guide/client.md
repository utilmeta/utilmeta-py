# 声明式 Web 客户端

UtilMeta 框架不仅提供了 API 类用于服务端接口的开发，还提供了一个与 API 类语法相近的 `Client` 类，用于开发对接 API 接口的客户端请求代码

与声明式接口一样，`Client` 类是一个声明式的客户端，只需要将目标接口的请求参数和响应模板声明到函数中，`Client` 类就会自动完成 API 请求的构建和响应的解析

!!! tip
	在 UtilMeta 中 `API` 类和 `Client` 类类似的不仅仅是语法，它们使用的 `Request` 和 `Response` 对象也是同一个类。没错，这样会降低开发者的心智成本，也能方便复用插件代码


## 编写 `Client` 类

编写 `Client` 类的方式与  [编写 API 类](../api-route) 如出一辙，只不过我们的类需要继承自 `utilmeta.core.cli.Client` 类

### 请求函数

我们假设要为以下 API 接口编写  `Client` 类

```python
from utilmeta import UtilMeta
from utilmeta.core import api

class RootAPI(api.API):
	@api.get
	def plus(self, a: int, b: int) -> int:
		return a + b
```

我们只需要按照 API 函数的请求参数写法编写 `Client` 的请求函数，把函数体留空即可，如
```python
from utilmeta.core import cli, api, response

class APIClient(cli.Client):
	class PlusResponse(response.Response):
		result: int
		
	@api.get
	def plus(self, a: int, b: int) -> PlusResponse: pass
```

这样当我们在按照如下方式调用时
```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> resp = client.plus(a=1, b=2)
```

就会根据你的函数声明构建一个请求，相当于
```
curl https://127.0.0.1:8000/api/plus?a=1&b=2
```

并将响应按照你的请求函数声明的响应模板解析为一个 `PlusResponse` 实例，你可以通过 `resp.result` 访问到已经转化为整数类型的结果

!!! tip
	你可以在 [请求参数](../handle-request) 文档中查看所有的请求参数的声明方法，`Client` 类中的请求函数与 API 函数的声明规则是一样的，只不过 API 类是解析和处理来自客户端的请求，而 `Client` 类是根据函数参数来构建和发起请求

#### 直接指定 URL

请求函数除了可以使用函数名称作为路径，与 `Client` 类的 `base_url` 组合成请求 URL 外，你还可以在 `@api` 装饰器中直接指定目标 URL 路径，下面是一个 Github 接口客户端代码示例

```python
from utilmeta.core import cli, api, request, response
from utype import Schema
	
class GithubClient(cli.Client):
	class OAuthData(Schema):
		code: str
		redirect_uri: str
		client_id: str = '<GITHUB_CLIENT_ID>'
		client_secret: str = '<GITHUB_CLIENT_SECRET>'
		
	@api.post('https://github.com/login/oauth/access_token')
    async def oauth_token(
	    self, 
	    query: OAuthData = request.Query
	) -> response.Response: pass

    @api.get('https://api.github.com/user')
    async def get_user(
	    self, 
	    token: str = request.HeaderParam('Authorization')
	) -> response.Response: pass
```

我们直接在 `@api` 装饰器中指定了完整的 URL 路径，这样 `Client` 类在调用时会忽略传入的 `base_url`，而直接使用这个指定的 URL 进行访问

!!! tip "异步请求函数"
	上面例子中我们声明的是异步的请求函数，你只需要用异步关键字 `async` 声明函数即可。但需要注意的是，异步请求函数需要配合异步的请求库才能让调用链底层的网络请求真正的成为异步请求，目前 UtilMeta 支持的异步请求库有 `httpx` 和 `aiohttp`，你可以在调用 `Client` 时使用 `backend` 参数指定使用的请求库，如
	```python
	>>> import httpx
	>>> client = GithubClient(backend=httpx)
	```

#### 声明响应模板

你可以使用 UtilMeta 的响应模板优雅地解析 `Client` 类的请求函数得到的响应。响应模板应该声明在 `Client` 类的请求函数的 **返回值类型提示** 中，需要声明为一个继承自 `Response` 的响应类，或者使用 `Union` 组合的多个响应类，比如下面是一个登录接口的 `Client` 类示例

```python
from utilmeta.core import cli, api, request, response
import utype

class UserSchema(utype.Schema):
	id: int
	username: str

class UserResponse(response.Response):
	status = 200
	result: UserSchema

class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
	) -> UserResponse: pass
```

在 UserClient 的 `login` 请求函数中，我们使用 `UserResponse` 作为函数的返回类型提示，在 `UserResponse` 中声明了 200 的响应状态码，并将 `UserSchema` 作为结果数据的类型提示，表示这个响应只接受 200 状态码的响应，并且会把响应数据向  `UserSchema` 进行解析

```python
>>> client = UserClient(base_url='<BASE_URL>')
>>> resp = client.login(username='alice', password='<PASSWORD>')
>>> resp.result
UserSchema(id=1, username='alice')
```

声明响应模板类中常用的属性有

* `status`: 可以指定一个响应码，只有响应的响应码与这个响应码一直时才会向这个响应模板解析
* `result`：声明响应的结果数据，若这个属性有类型声明，响应将会把结果数据按照这个类型进行解析
* `headers`：声明响应的响应头，若这个属性使用 `Schema` 类进行声明，响应将会把响应头按照这个类型进行解析

如果响应体数据是一个 JSON 对象并且有着固定的模式，你也可以使用以下的选项声明对应的模式键值

* `result_key`：响应对象中对应着 **结果数据** 的键，如果指定了这个属性，那么 `response.result` 属性访问到的结果数据将会是解析后的 `response.data[response.result_key]`
* `message_key`：响应对象中对应着 **错误消息** 的键，如果指定了这个属性，那么 `response.message` 将会访问到响应体对象中的消息字符串
* `state_key`：响应对象中对应着 **业务状态码** 的键，如果指定了这个属性，那么 `response.state` 将会访问到响应体对象中的业务状态码
* `count_key`：响应对象中对应着 **查询数据总数** 的键（用于分页），如果指定了这个属性，那么 `response.count` 将会访问到响应体对象中的查询数据总数

!!! tip
	你可以通过 `response.data` 访问到未解析的完整响应体对象，通过 `response.result` 访问到的是解析后的结果数据（如果响应模板没有声明 `result_key`，那么结果数据就是解析后的`response.data`）

#### 使用 `Union` 处理多种响应

一个常见的情况是接口可能会返回多种响应，比如成功，失败，权限不够等，这样的情况放在一个响应模板里较难处理，我们可以使用  `Union` 来组合多个响应模板，如

```python
from utilmeta.core import cli, api, request, response
import utype
from typing import Union

class UserSchema(utype.Schema):
	id: int
	username: str

class UserResponse(response.Response):
	status = 200
	result: UserSchema

class UserResponseFailed(response.Response):
	status = 403
	message_key = 'error'
	state_key = 'state'

class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
	) -> Union[UserResponse, UserResponseFailed]: pass
```

我们对上面的用户登录客户端代码进行了改造，添加了对应登录失败状态的 `UserResponseFailed` 响应，并与 `UserResponse` 组合到 `Union` 中作为登录请求函数的返回类型声明

这样当响应的状态码是 200 时，会向 `UserResponse` 进行解析，状态码是 403 时，会向 `UserResponseFailed` 进行解析

除了根据状态码进行的解析外，若响应模板未提供状态码或有多个响应模板提供了相同的状态码，`Client` 类将会按照响应模板在 `Union[]` 中声明的顺序进行解析，若解析成功则返回，解析失败则继续解析下一个模板，若所有的模板都无法完成响应解析则会抛出对应的错误，如果你不希望在解析失败时抛出错误，你可以在 `Union[]` 的末尾增加一个 `Response` 元素，例如 

```python
class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
	) -> Union[UserResponse, UserResponseFailed, response.Response]: pass
```

这样当前面的模板都无法成功解析时，请求函数会返回一个 `response.Response` 实例

!!! tip "在 API 函数中直接返回响应"
	`Client` 类中请求得到的响应和 API 类中最终生成的响应的类型是一致的，都是 `utilmeta.core.response.Response` 类，这样带来了很多方便之处，除了响应模板可以复用外，你可以在 API 函数中把调用 `Client` 类得到的响应直接作为 API 函数的响应进行返回，UtilMeta 可以直接识别处理，这对于编写一些代理接口来说非常方便

#### 处理 Server-Sent Events 流式响应

使用 Client 客户端还可以处理 Server-Sent Events（SSE） 流式响应，需要使用 `response.SSEResponse` 作为 SSE 接口的响应提示，示例如下：

```python
from utilmeta.core import cli, request, api, response
import utype
from utype.types import *

class ErrorEvent(response.ServerSentEvent):
    event = 'error'
    data: str

class MessageEvent(response.ServerSentEvent):
    event = 'message'

    class _message_data(utype.Schema):
        v: str

    data: _message_data

class StreamClient(cli.Client):
    @api.get('/stream')
    def get_events(self) -> response.SSEResponse[Union[MessageEvent, ErrorEvent]]:
        pass
```

SSE 接口请求得到的 `response.SSEResponse` 对象可以被当作生成器或异步生成器进行迭代，其中的元素为 SSE 中的一个事件，其基本类型为 `response.ServerSentEvent`，包含的字段为：

* `event`: 事件类型，如 `message` 表示消息， `error` 表示错误，`close` 表示关闭连接
* `data`: 事件的数据，可以为一个 JSON 对象
* `id`: 事件的 ID（可选）
* `retry`: :断连时的重连毫秒时间（可选）

!!! tip
	`SSEResponse` 中设置了 `stream = True` ，会被 Client 类自动处理为流式响应

如果 SSE 接口中返回的事件有着更明确的事件类型和数据结构，你可以将其声明并按照如上例子的方式进行传递，`SSEResponse` 会根据 `event` 的值进行解析，并得到符合声明的事件数据类型实例，调用示例如下：

```python
import httpx

async with StreamClient(
    base_url=f'http://127.0.0.1:8000/api/',
    backend=httpx
) as client:
	async for event in client.get_events():
	    print(event)
	    # MessageEvent(event='message', data=MessageEvent._message_data(v='content'))
	    # ErrorEvent(event='error', data='Error Message')
```

若使用 `httpx` / `aiohttp` 这样的异步请求库，就使用 `async for` 迭代异步生成器，否则使用 `for` 进行迭代即可，其中的元素会被正确地进行类型提示 （ 如例子中的 `Union[MessageEvent, ErrorEvent]`）便于开发

!!! note
	UtilMeta >= 2.8 版本支持此特性

#### 自定义请求函数

在上面的例子中，我们都是使用声明式的请求参数声明和响应模板声明，让 `Client` 类自动根据声明构建请求与解析响应，这样的请求函数我们称之为 **默认请求函数**，它的函数体不需要任何内容，只需要 `pass` 即可

当然我们也可以在函数体中编写自定义的请求调用逻辑和响应处理逻辑，这样的请求函数就是自定义请求函数，下面是一个例子

```python
from utilmeta.core import cli, api, request, response
import utype
from typing import Union

class UserSchema(utype.Schema):
	id: int
	username: str

class UserResponse(response.Response):
	status = 200
	result: UserSchema

class UserResponseFailed(response.Response):
	status = 403
	message_key = 'error'
	state_key = 'state'

class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
		_admin: bool = False,
	) -> Union[UserResponse, UserResponseFailed]:
		if _admin:
			return self.post(
				'/login/admin',
				data=dict(
					username=username,
					password=password
				)
			)
```

我们在 login 请求函数中添加了一个 `_admin` 参数，在函数逻辑中，当这个参数为 True 时，将使用自定义的请求逻辑，否则，当 `Client` 类检测到请求函数返回的结果为空时，将会按照默认请求函数的方式构建请求，无论是自定义的请求还是默认构建的请求，他们返回的响应都会被请求函数的响应模板解析

!!! tip
	在请求函数中添加的自定义属性需要使用下划线 `'_'` 开头，这样它才不会识别为请求查询参数。当然，如果你不希望 `Client` 类对你的自定义请求函数进行处理，而是完全定义自己的请求逻辑，你的函数就不需要使用 `@api` 装饰器，这样就是一个普通的函数了

在 `Client` 类中提供了一个内置的请求函数 `request()` 和一系列以 HTTP 方法为命名的请求函数，你可以在自定义的请求逻辑中调用，他们的函数参数为

* `method`：只有 `request()` 函数需要提供，指定 HTTP 方法，其他以 HTTP 方法命名的函数将使用对应的 HTTP 方法
* `path`：指定请求路径字符串，如果请求路径是完整的 URL，将会直接使用，否则会与 `Client` 类的 `base_url` 进行拼接
* `query`：指定请求的查询参数字典，将会与路径一起解析拼接为请求 URL
* `data`：指定请求体数据，可以是字典，列表，字符串，文件，如果没有指定 `Content-Type` 请求头，将会根据请求体数据的类型自动生成
* `headers`：指定请求头数据，传入一个字典
* `cookies`：指定请求的 Cookie 数据，可以传入字典或 Cookie 字符串，指定的 Cookie 会与 `Client` 实例持有的 Cookie 进行整合作为请求的 `Cookie` 头
* `timeout`：指定请求的超时时间，默认将使用 `Client` 类的 `default_timeout` 参数

!!! tip "异步内置请求函数"
	对所有的内置请求函数，`Client` 类也提供了对应的异步版本，只需要在函数名称前加 `async_` 即可，如 `async_request`，`async_get`

!!! warning
	请不要把请求函数的命名为以上内置的请求函数的名字，如果你想定义一个位于当前 `Client` 类根路径的请求函数，请不要使用 HTTP 方法命名，而是使用 `@api.get("/")`
 
### 钩子函数

在客户端代码的编写中，我们经常需要对请求，响应进行处理与微调，这时我们可以使用钩子函数来方便地处理。在 `Client` 类中已经定义了三个通用的钩子函数

```python
class Client:
	def process_request(self, request: Request):
        return request

    def process_response(self, response: Response):
        return response

    def handle_error(self, error: Error):
        raise error.throw()
```

如果你需要对这个 `Client` 类的请求，响应或错误处理进行通用的配置，你可以直接在类中继承这些函数并且编写你的逻辑

* `process_request`：处理请求，你可以调整请求中的参数，如果这个函数返回一个 `Response` 实例，那么请求函数将不再发起请求而直接使用这个响应
* `process_response`：处理响应，你可以修改响应头或调整数据，如果这个函数返回一个 `Request` 实例，那么请求函数将重新发起这个请求（这个特性可以用于请求的重试或重定向）
* `handle_error`：处理错误，你可以根据错误的情况记录日志或者做出处理操作，如果这个函数返回一个 `Response` 实例，那么请求函数将使用这个响应作为返回，如果这个函数返回一个 `Request` 实例，那么请求函数将发起这个请求，不返回或返回其他类型将抛出这个错误

!!! note
	通用钩子函数只作用于默认请求函数（内部使用 `pass` 的函数），如果你自定义了请求函数的逻辑，则不会经过通用钩子函数处理，但你依然可以在函数中自行调用 `self.process_request` 和 `self.process_response` 等

#### 装饰器钩子函数

相较于通用钩子函数，使用 `@api` 装饰器定义的钩子函数在目标的选择上更为灵活一些，`Client` 类中的装饰器钩子与 [API 的装饰器钩子](../api-route/#_10) 用法基本一致：

* `@api.before`：预处理钩子，在请求函数调用前对请求进行处理
* `@api.after`：响应处理钩子，在请求函数调用后对响应进行处理
* `@api.handle`：错误处理钩子，在请求函数调用链抛出错误时进行处理

与 API 钩子的区别在于，对于 `@api.before` 预处理钩子，需要使用第一个参数接收 `Client` 类生成的请求对象，你可以在预处理钩子中对这个请求对象的属性进行更改

```python
from utilmeta.core import cli, api, request, response
from utype import Schema

class GithubClient(cli.Client):
    class OAuthData(Schema):
        code: str
        redirect_uri: str
        client_id: str = '<GITHUB_CLIENT_ID>'
        client_secret: str = '<GITHUB_CLIENT_SECRET>'

    @api.post('https://github.com/login/oauth/access_token')
    async def oauth_token(
        self,
        query: OAuthData = request.Query
    ) -> response.Response: pass
    
    @api.get('https://api.github.com/user')
    async def get_user(self) -> response.Response: pass
    
    @api.before(get_user)
    def add_authorization(self, req: request.Request):
        req.headers['Authorization'] = f'token {self.token}'

    def __init__(self, token: str, **kwargs):
        super().__init__(**kwargs)
        self.token = token
```

在这个例子中，我们为 `GithubClient` 的 `get_user` 请求函数添加了一个预处理钩子函数 `add_authorization`，将实例的 `token` 参数添加到 `Authorization` 请求头，预处理钩子的第一个参数 `req` 用于接收请求对象进行处理

需要注意的是装饰器钩子函数和通用钩子函数在 `Client` 类请求函数的作用范围并不同，对于默认请求函数而言，处理的顺序如下

1. `@api.before` 钩子函数
2. `process_request` 函数
3. 发起请求
4. `process_response` 函数
5. `@api.after` 钩子函数

其中 2，3，4 步骤抛出的错误可以被 `handle_error` 通用钩子函数处理，所有步骤（1~5）中抛出的错误都会被 `@api.handle` 钩子函数处理

!!! tip "异步钩子函数"
	如果你的钩子函数中包含异步操作，你可以使用 `async` 关键字把钩子函数定义为异步函数（包括通用异步函数与装饰器异步函数），异步钩子函数的用法和同步钩子函数一致，但你需要把请求函数也声明成异步的，否则在同步的请求函数中无法调用异步钩子函数

### `Client` 类的挂载

与 API 类类似，`Client` 类也支持通过挂载方式定义多级树状路由，方便大型的请求 SDK 组织代码，下面是一个例子

```python
from utilmeta.core import cli, api, request, response
import utype

class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
	) -> response.Response: pass

class ArticlesClient(cli.Client):
	@api.get("/feed")
    def get_feed(
        self,
        offset: int = request.QueryParam(required=False, ge=0),
        limit: int = request.QueryParam(required=False, ge=0, le=100),
    ) -> response.Response: pass

class APIClient(cli.Client):
	user: UserClient
	articles: ArticlesClient
```

在这个例子中，我们把 `ArticlesClient` 类挂载到 `APIClient` 的 `articles` 路径上，把 `UserClient` 类挂载到了 `user` 路径上，这样当我们在进行以下调用时

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.articles.get_feed(limit=10)
```
我们实际上会访问到 `http://127.0.0.1:8000/api/articles/feed?limit=10`，也就是说挂载的 `Client` 类的 `base_url` 会在末尾添加挂载的路由

### 挂载路由中的路径参数

当你需要定义一些无法直接通过类属性来声明的的路由路径时，我们还可以用 `@api.route` 装饰器来声明路由名称，其中也可以包含路径参数，如

```python
from utilmeta.core import cli, api, request, response
import utype

class CommentClient(cli.Client):
    @api.get("/{id}")
    def get_comment(
	    self, 
	    id: int, 
	    slug: str = request.PathParam
	) -> response.Response: pass

class APIClient(cli.Client):
	comments: CommentClient = api.route(
        'articles/{slug}/comments'
    )
```

这个例子中 `CommentClient` 挂载的路由是 `'articles/{slug}/comments'`，其中包含一个路径参数 `slug`，在 `CommentClient` 的请求函数中，需要将 `slug` 参数声明为 `request.PathParam` (路径参数)，这样当我们调用 

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.comments.get_comment(id=1, slug='hello-world')
```
就会访问到 `http://127.0.0.1:8000/api/articles/hello-world/comments/1`

如果一个 `Client` 类的路由是确定的话，你也可以直接使用类装饰器的方式声明，比如
```python
from utilmeta.core import cli, api, request, response
import utype

@api.route('articles/{slug}/comments')
class CommentClient(cli.Client):
    @api.get("/{id}")
    def get_comment(
	    self, 
	    id: int, 
	    slug: str = request.PathParam
	) -> response.Response: pass

class APIClient(cli.Client):
	comments: CommentClient
```

### 客户端的表单与文件

使用客户端类为请求添加文件的方式有两种

* **直接上传文件**：直接使用单个文件作为请求体，你可以直接把 `utilmeta.core.file.File` 指定为请求体类型
* **使用表单上传文件**：使用 `multipart/form-data` 表单传输文件，除了文件外你还可以传入其他的表单字段

```python
from utilmeta.core import cli, request, api, file
import utype

class APIClient(cli.Client):
	class FormData(utype.Schema):
        name: str
        files: List[file.File]
        
    @api.post
    def multipart(self, data: FormData = request.Body): pass
```

在传入文件时，你可以直接使用 File 传递一个本地文件，比如

```python
client.multipart(data={
	'name': 'multipart',
	'files': [File(open('test.txt', 'r')), File(open('test.png', 'r'))] 
})
```

!!! tip
	你可以使用 File 的 `filename` 参数传入文件名，会作为  `multipart/form-data`  表单的文件名传递，如果没有指定的话会识别本地文件的文件名


## 调用 `Client` 

在上文的例子我们已经了解了如何实例化 `Client` 类进行调用，下面是完整的 `Client` 类实例化参数

* `base_url`：指定一个基准 URL，`Client` 实例中的请求函数与挂载的其他 `Client` 实例的 URL 都会从这个基准 URL 进行延申（除非对应的请求函数已经定义了绝对 URL），这个 URL 需要是一个绝对 URL （包含请求协议和请求源的 URL）
* `backend`：可以传入一个请求库的名称字符串或引用，这个请求库将会作为 `Client` 类函数发起请求调用的请求库，目前支持的请求库包括 `requests`, `aiohttp`, `httpx` 与 `urllib`，如果不设置将使用 `urllib`

!!! warning "异步请求库"
	如果你在 `Client` 类中编写的是异步的请求函数，请使用异步的请求库作为 `backend`，比如 `aiohttp`, `httpx`，否则底层发起的还是同步的请求

* `service`：可以指定一个 UtilMeta 服务作为 `Client` 实例的目标服务，如果指定 `internal` 参数为 True，那么 `Client` 构建的请求将不再发起网络请求，而是调用 UtilMeta 服务的内部路由并生成响应，否则 `Client` 实例的 `base_url` 将自动赋值为 UtilMeta 服务的 `base_url` 
* `internal`：用于控制 `Client` 实例是请求模式，默认为 False，如果为 True，则通过内部调用 `service` 指定的服务生成响应

!!! note
	若 `internal=True` 而 `service` 未指定，则 `Client` 实例会尝试导入当前进程中注册的 UtilMeta 服务

* `mock`：指定是否为 mock 客户端，如果为 True，`Client` 对请求函数不会进行实际的网络请求或内部调用，而是会直接根据声明的响应模板生成一个 mock 响应并返回，可以用于在接口尚未开发好时进行客户端开发
* `append_slash`：是否默认在请求 URL 的末端添加 `'/'`（当 URL末端不是 `'/'` 时）
* `default_timeout`：指定请求函数默认的超时时间，可以是一个表示秒数的 `int`, `float` 或 `timedelta` 对象
* `base_headers`：使用一个字典指定请求函数的默认请求头，每个请求的请求头都会默认包含这个字典中的请求头
* `base_cookies`：指定请求函数的默认 Cookie，可以是一个字典，Cookie 字符串或 `SimpleCookie` 对象
* `base_query`：指定请求函数的默认查询参数
* `proxies`：指定 `Client` 实例的 HTTP 请求代理，格式为 
```python
{'http': '<HTTP_PROXY_URL>', 'https': '<HTTPS_PROXY_URL>'}
```

* `allow_redirects`：是否允许底层请求库进行请求重定向（3XX），默认为 None，跟随请求库的默认配置
* `fail_silently`：若设为 True，当请求函数的响应数据无法解析为声明的响应模板类时，不抛出错误，而是返回一个通用的 `Response` 实例，默认为 False

!!! tip
	若要调控 `Client` 类中的某个或某些请求函数拥有 `fail_silently` 的特性，你可以在对应请求函数的响应声明中加上默认的 `Response` 类，如
	```python
	class APIClient(Client):
		@api.get
		def my_request(self) -> Union[MyResponse, Response]: pass
	```
### 简单调用

当然 UtilMeta 的 `Client` 类也可以直接作为请求类来使用，用法很简单

```python
>>> from utilmeta.core.cli import Client
>>> import httpx
>>> client = Client('https://httpbin.org/', backend=httpx)
>>> resp = client.get('/get' , query={'a': 1, 'b': 2})
>>> resp
Response [200 OK] "GET /get?a=1&b=2"
>>> resp.data.get('args')
{'a': '1', 'b': '2'}
```

### Cookies 会话保持

客户端一个常见的需求是提供一个 Session 会话机制，像浏览器一样，能够保存和记忆响应设置的 Cookies 并且在请求中发送，Client 类就内置了这样的机制

当你的请求的响应包含 `Set-Cookie` 响应头时，Client 类就会解析其中的 Cookie 并且存储，在接下来的请求中 Client 类就会携带这些 Cookie 进行请求

#### 通过 `with` 语句隔离会话

如果你希望 Client 类中的会话状态只保持在一部分代码块中，你可以使用 `with` 语句来组织与隔离这些会话，在 `with` 语句退出时，client 中的 Cookie 等会话状态将会被清理

```python
client = UserClient(
	base_url='http://127.0.0.1:8555/api/user',
)
with client:
	resp = client.session_login(
		username='alice',
		password="******",
	)
with client:
	resp = client.jwt_login(
		username='alice',
		password="******",
	)
```

!!! tip
	对于 `httpx` 与 `aiohttp` 等异步请求库，需要使用 `async with` 进行会话管理

在 `with` / `async with` 语句块中，不仅可以保持 Cookies 状态，Client 还会将请求会话（`httpx.Client` / `aiohttp.Session` / `requests.Session`）进行复用，不会在单个请求结束后关闭，客户端可以复用 TCP 连接与 TLS 握手，对于同域名的多次请求会有性能的提升，在语句块结束后关闭对应的请求会话（使用 `async with` 可以调用对应的异步 `close` 方法）

!!! note
	UtilMeta >= 2.8 版本支持 `async with` 语法与自动处理请求会话的复用和关闭

## 生成 `Client` 类代码

### 为 UtilMeta 服务生成请求代码

为 UtilMeta 服务自动生成 Client 类的请求 SDK 代码只需要一个命令，在你的项目目录（包含 `meta.ini` 的目录）下执行以下命令

```
meta gen_client
```

你可以额外增加 `--to` 参数指定生成的文件名，默认将会生成 `client.py` 到你的当前文件夹，其中包含着自动生成的客户端代码

### 为 OpenAPI 文档生成请求代码

你可以在使用 `meta gen_client` 命令时传入 `--openapi` 参数，指定 OpenAPI 的 URL 或文件地址，UtilMeta 就会根据这个地址对应的 OpenAPI 文档生成客户端请求 SDK 代码，如

```
meta gen_client --openapi=https://petstore3.swagger.io/api/v3/openapi.json
```

## `Client` 类代码示例

### Realworld 文章接口

我们以 [Realworld 博客项目的获取文章接口](https://realworld-docs.netlify.app/specifications/backend/endpoints/#get-article) 为例，使用 UtilMeta 的  `Client` 类编写客户端请求

```python
from utilmeta.core import cli, api, request, response
import utype
from utype.types import *


class ProfileSchema(utype.Schema):
	username: str
	bio: str
	image: str
	following: bool

class ArticleSchema(utype.Schema):
	body: str
	created_at: datetime = utype.Field(
		alias="createdAt"
	)
	updated_at: datetime = utype.Field(
		alias="updatedAt"
	)
	author: ProfileSchema
	slug: str
	title: str
	description: str
	tag_list: List[str] = utype.Field(alias="tagList")
	favorites_count: int = utype.Field(
		alias="favoritesCount"
	)
	favorited: bool

class ArticleResponse(response.Response):
	name = "single"
	result_key = "article"
	content_type = "application/json"
	result: ArticleSchema
	status = 200

class ErrorResponse(response.Response):
	result_key = "errors"
	message_key = "msg"
	content_type = "application/json"

class APIClient(cli.Client):
    @api.get("/articles/{slug}", tags=["articles"])
    def get_article(
        self, slug: str = request.PathParam(regex="[a-z0-9]+(?:-[a-z0-9]+)*")
    ) -> Union[
        ArticleResponse,
        ErrorResponse
    ]:
        pass
```

调用方式：

```python
>>> client = APIClient(base_url='https://realworld.utilmeta.com/api')
>>> resp = client.get_article(slug='utilmeta-a-meta-backend-framework-for-python')
>>> resp
ArticleResponse [200 OK] "GET /api/articles/utilmeta-a-meta-backend-framework-for-python"
```


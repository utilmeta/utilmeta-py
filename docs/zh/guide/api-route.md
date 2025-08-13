# API 类与路由

## 定义 API 接口

我们在 Hello World 中看到了 UtilMeta 最简单的 API 接口
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

这个简单的例子展示了 UtilMeta 声明和组织接口的两种方式

* **API 类**：继承 `utilmeta.core.api.API`，其中可以声明一系列 API 函数作为接口，或者挂载其他的 API 类来定义树状的路由
* **API 函数**：在 API 类中定义的使用 `@api` 装饰器装饰的函数会被处理为 API 的端点接口

### `@api` 装饰器

`api` 模块中内置了几个装饰器函数，用于定义 API 函数

* `@api.get`：声明 GET 方法的 API 接口
* `@api.put`：声明 PUT 方法的 API 接口
* `@api.post`：声明 POST 方法的 API 接口
* `@api.patch`：声明 PATCH 方法的 API 接口
* `@api.delete`：声明 DELETE 方法的 API 接口

所有 `@api` 装饰器都支持传入参数来指定具体的接口配置，包括

* `<route>`：第一个参数，可以传入一个路径字符串来指定 API 的路径或路径模板，具体用法可以参考 [处理路径参数](../handle-request#路径参数)
* `summary`：API 的介绍，会被整合到 OpenAPI 文档接口中的 `summary` 属性
* `deprecated`：API 是否已弃用
* `idempotent`：API 是否 **幂等**（相同参数多次调用与单次调用效果一致，对于编写客户端重试机制很重要）
* `private`：API 是否是私有接口，私有接口不提供公开调用，也不会出现在生成的 API 文档中
* `tags`:  指定生成的 OpenAPI 文档中的标签 (默认为按照接口的定义路由生成)
* `description`:  指定生成的 OpenAPI 文档中的说明 (默认为接口函数的 doc_string)
* `extension`: 额外定义或覆盖  OpenAPI 文档的 JSON 对象，如果是额外定义的字段需要以 `x-` 开头
* `timeout`: 指定接口的超时时间，如果接口函数在此时间内都没有返回响应则会抛出 TimeoutError 

!!! tip
	你在 API 类或 API 函数中编写的文档（`"""doc_string"""`）会被解析整合到 OpenAPI 文档接口中的 `description`，如
	
	```python
	class UserAPI(api.API):
		"""This is the user API"""
		@api.post
		def login(self):
			"""This is the login API"""
	```

如果  `@api` 装饰器没有使用第一个参数指定路径字符串，则会使用被装饰函数的名称作为 API 接口的路径，如在 Hello World 中 `hello` 函数的名称就作为了该接口的路径

!!! warning
	如果你需要定义的路径名称恰好是 HTTP 动词的名称，你应该把该路径作为路径字符串进行定义，如
	```python
	class RootAPI(api.API):
		@api.get('patch')
		def get_patch(self): pass
	```

### 核心方法

除了使用 `@api` 装饰器声明的 API 函数外，API 类中的名称为 HTTP 方法（get/put/post/patch/delete）的函数会被自动处理为 API 函数，路径与 API 类的路径一致，它们称为 API 类的核心方法，如

```python
from utilmeta.core import api

class ArticleAPI(api.API):
    def get(self, id: int) -> ArticleSchema:
	    return ArticleSchema.init(id)

    def post(self, data: ArticleSchema = request.Body):
        data.save()
```

例子中的 ArticleAPI 声明了 `get` 和 `post` 两个核心方法函数，如果 ArticleAPI 被挂载到了 `/article` 路径，那么调用 `GET /article` 就会执行 `get` 函数的逻辑，同理调用 `POST /article` 会执行 `post` 函数

!!! tip "HEAD 与 OPTIONS 方法" 
	当你声明了一个 GET 接口后，这个接口的路径就自动拥有了响应 HEAD 方法请求的能力，使用 HEAD 方法请求 GET 接口的路径会得到一个与请求 GET 接口的响应头和响应码一致的响应，但是响应体为空
	
	对于任意方法的接口路径都会拥有响应 OPTIONS 方法请求的能力，会按照 OPTIONS 方法的标准返回当前接口支持的方法，请求头，是否允许跨域等信息
	
	所以你无需声明 HEAD 方法和 OPTIONS 方法的接口

## API 挂载与路由

我们除了可以在 API 类内定义接口外，也可以通过 API 挂载的方式将一个 API 类挂载到另一个 API 类上，从而定义树状的路由，API 挂载的用法如下
```python
from utilmeta.core import api

class ArticleAPI(api.API):
	@api.get
	def feed(self): pass

class UserAPI(api.API):
	@api.post
	def login(self): pass

class RootAPI(api.API):
	article: ArticleAPI
	user: UserAPI
```

API 通过声明类型的方式挂载，在这个例子中我们把 ArticleAPI 挂载到了 RootAPI 的 `article` 路径上，把 UserAPI 挂载到了 `user` 路径上，于是就形成了以下的 URL 路径

```
/ ------------------ RootAPI
/article ----------- ArticleAPI
/article/feed ------ ArticleAPI.feed
/user -------------- UserAPI
/user/login -------- UserAPI.login
```

### 使用 `@api.route` 配置路由

我们知道 `@api` 下的方法装饰器可以通过装饰函数声明 API 接口，除此之外还有一个 `@api.route` 装饰器用于为整个 API 类配置路由，用法如下

```python
from utilmeta.core import api, request

@api.route('{slug}/comments')
class CommentAPI(api.API):
    def get(self, slug: str = request.PathParam): pass

class ArticleAPI(api.API):
    comments: CommentAPI

class RootAPI(api.API):
	article: ArticleAPI
```

使用 `@api.route` 定义的路由路径会覆盖挂载的属性路径，于是例子中声明的路由如下
```
/ ------------------------- RootAPI
/article ------------------ ArticleAPI
/article/{slug}/comments -- CommentAPI
```

其中 CommentAPI 的所有接口都会有一个名为 `slug` 的路径参数

`@api.route` 与其他的 API 装饰器一样，除了路径字符串外还可以定义以下参数

* `summary`：API 的介绍，会被整合到 OpenAPI 文档接口中的 `summary` 属性
* `deprecated`：API 是否已弃用
* `private`：API 是否是私有接口，私有接口不提供公开调用，也不会出现在生成的 API 文档中

### 根 API 的挂载

在 UtilMeta 中，所有的 API 类都需要最终挂载到一个 API 类上从而提供访问，这个 API 类就是 **根 API**，通常命名为 RootAPI，根 API 也需要挂载到服务上从而提供访问

在 Hello World 中我们已经看到了根 API 的一种挂载方式
```python hl_lines="14"
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
```

在 UtllMeta 服务的初始化参数中有两个参数用于挂载根 API  

* `api`：传入根 API 类或者它的引用字符串
* `route`：根 API 挂载的路径，默认为空

比如当你的服务运行在 `127.0.0.1:8000` 地址时，根 API 的地址就在 `127.0.0.1:8000/api`，其上定义的路径为 `hello` 的接口的地址在 `127.0.0.1:8000/api/hello`

另外可以使用 **引用字符串** 挂载根 API，使用方式如下

=== "main.py"  
	```python hl_lines="8"
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
=== "service/api.py"  
	```python
	from utilmeta.core import api
	
	class RootAPI(api.API):
	    @api.get
	    def hello(self):
	        return 'world'
	```

这种方式也称为 **懒加载**，通常用来解决循环依赖等问题，根 API 会在服务启动前完成加载

!!! tip "引用字符串"
	引用字符串指的是在当前项目中导入这个类的路径，包括其所在包名，文件名，以及类的名称，比如你可以通过如下方式导入 RootAPI 类时
	```python
	from service.api import RootAPI
	```
	RootAPI 完整的引用字符串就是 `'service.api.RootAPI'`


另外 UtilMeta 服务实例中有一个名为 `mount` 的方法也可以用于挂载根 API
```python hl_lines="5"
from utilmeta import UtilMeta

service = UtilMeta(...)

@service.mount(route='/api')
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

需要注意的是，无论使用什么方式，一个服务只能挂载一个根 API

!!! warning "Django 的挂载策略"
	如果你使用的是 Django 作为 backend 或者需要使用 Django 的 ORM，那么你需要使用 **引用字符串** 的方式挂载根 API，因为在加载 Django 模型前需要先对 Django 进行初始化，这个过程会由 UtilMeta 内置的 DjangoSettings 在服务启动前自动完成，但如果你在此之前导入了 API 类与 Django 模型，就会出现以下错误
	```python
	django.core.exceptions.ImproperlyConfigured: 
	Requested setting INSTALLED_APPS, but settings are not configured, ...	
	```

## API 类的使用

### 访问当前请求

在 API 函数中，你可以通过 `self.request` 访问到当前的请求数据，其中常用的属性有

* `method`：当前请求的 HTTP 方法
* `url`：请求的完整 URL 路径（包含协议，域名，路径，查询字符串）
* `query`：解析请求的查询字符串得到的字典
* `headers`：请求头字典
* `body`：请求体数据
* `time`：请求的时间，返回一个 `datetime` 对象
* `ip_address`：请求的 IP 地址，返回一个 `ipaddress.IPv4Address` 或 `ipaddress.IPv6Address`

下面是一个简单的使用示例，返回当前请求的 IP 地址
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def ip(self) -> str:
        return str(self.request.ip_address)
```


!!! note
	请求对象的 `adaptor` 属性是请求的适配器对象，用于适配不同的 HTTP backend 的请求数据，也保存着原始的请求对象，比如当你使用 `starlette` 作为 HTTP backend 时，访问 `self.request.adaptor.request` 会得到原始的 `starlette.requests.Request` 实例

### 公共参数

如果一个 API 类中的所有接口都需要携带某一参数，那么可以将这个参数作为该 API 类的公共参数进行声明，声明的方式很简单，就是将它定义为 API 类中的一个变量，我们将上面例子中 CommentAPI 进行改造

```python hl_lines="5"
from utilmeta.core import api, request

@api.route('{slug}/comments')
class CommentAPI(api.API):
    slug: str = request.SlugPathParam

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article = Article.objects.filter(slug=self.slug).first()
        if not article:
            raise exceptions.NotFound('article not found')

    def get(self):
        return CommentSchema.serialize(
			Comment.objects.filter(article=self.article)
		)
		
    def post(self, comment: CommentSchema[orm.A] = request.Body):
        comment.article_id = self.article.pk
        await comment.save()
```

CommentAPI 使用 `@api.route` 为整个 API 类指定了路径模板字符串，所以你可以直接将 `slug` 路径参数声明为 API 的类属性，这样每个接口都可以直接访问而无需重复声明

我们在 CommentAPI 的初始化函数中直接访问 `slug` 参数并查询对应的文章实例，这样在接口中我们就可以直接使用文章实例了，在这里也你可以看出使用 API 类的方便之处


所有的公共参数需要指定一个 `utilmeta.core.request` 中的参数类型作为属性的值，你在 [解析请求参数](../handle-request) 了解到所有的请求属性，常用的有

* `request.PathParam`：定义路径参数
* `request.QueryParam`：定义查询参数
* `request.HeaderParam`：定义请求头参数
* `request.CookieParam`：定义 Cookie 参数

### 运行时调用 API 

为了更好的复用 API 逻辑，你可能需要在一个 API 函数中调用其他的 API 接口，在 UtilMeta 中实现这样的调用非常简单

在 UtilMeta 中所有的接口都是 API 类的一个实例函数，所以在调用接口前你需要先把对应的 API 类进行初始化，方法有两种
#### 挂载初始化
如果你调用的是当前 API 类挂载的 API，那么你直接使用实例属性访问到的 API 就是一个被自动初始化好的 API 类实例，你可以直接调用其中的方法，只需要传入对应的函数参数即可，如
```python hl_lines="15"
from utilmeta.core import api, request

@api.route('{slug}/comments')
class CommentAPI(api.API):
    def get(self, slug: str = request.PathParam) -> List[CommentSchema]:
        return CommentSchema.serialize(
			Comment.objects.filter(article__slug=slug)
		)

class ArticleAPI(api.API):
    comments: CommentAPI
    
    def get(self, id: int) -> ArticleSchema:
        data = ArticleSchema.init(id)
        data.comments = self.comments.get(slug=data.slug)
        return data
```

在这里例子中，我们在 ArticleAPI 的 get 接口中 使用 `self.comments` 调用了挂载其上的CommentAPI，访问到的就是已经初始化好的 CommentAPI 实例，所以你可以直接调用其中的 get 访问来获取当前文章的所有的评论

!!! note
	使用类型声明的方式挂载 API，你会发现在类实例方法中调用时，可以完全享受 IDE 的类型提示和方法补全，因为你在运行时访问得到的实例类型和声明的完全一致

#### 自行初始化
除了通过挂载的方式自动初始化 API 类外，你还可以自行完成 API 类的初始化与调用，API 类的初始化参数就是一个**请求对象**，而当前的请求对象可以通过 `self.request` 访问到，所以你可以直接通过 `CommentAPI(self.request)` 得到 API 实例
```python hl_lines="12"
from utilmeta.core import api, request

class CommentAPI(api.API):
    def get(self, slug: str = request.PathParam) -> List[CommentSchema]:
        return CommentSchema.serialize(
			Comment.objects.filter(article__slug=slug)
		)
		
class ArticleAPI(api.API):
    def get(self, id: int) -> ArticleSchema:
        data = ArticleSchema.init(id)
        data.comments = CommentAPI(self.request).get(slug=data.slug)
        return data
```

### 继承与组合
除了使用 API 类型声明的方式挂载外，你还可以通过继承或多重继承的方式把多个 API 类挂载到一个路径中，示例如下

```python hl_lines="12"
from utilmeta import UtilMeta
from utilmeta.core import api

class UserAPI(api.API):
    @api.post
    def login(self): pass

class ArticleAPI(api.API):
    @api.get
    def feed(self): pass

class RootAPI(UserAPI, ArticleAPI): pass
   @api.get
    def hello(self):
        return 'world'
```

其中定义的路径就是把继承的 API 类的接口组合起来
```
/ --------- RootAPI
/feed ----- ArticleAPI.feed
/login ---- UserAPI.feed
/hello ---- RootAPI.hello
```

!!! warning
	组合 API 类中的路径不能有冲突

## 生成响应

对于简单的接口，你可以直接将结果数据返回，UtilMeta 会自动处理为一个 200 HTTP 响应，但 UtilMeta 依然有着完善的响应模板与生成系统，可以自行定义响应码，响应头与响应结构等

我们来看一个简单的响应模板示例
```python
from utilmeta.core import api, response

class WrapResponse(response.Response):
    result_key = 'data'
    message_key = 'msg'

class RootAPI(api.API):
    response = WrapResponse

	@api.get
	def hello(self):
		return 'world'
```

UtilMeta 的所有接口响应都继承自 `utilmeta.core.response.Response`，这个例子为响应指定了一定的模板结构，把 API 函数的返回数据包裹为一个 JSON 对象，其中 `result_key` 指定的键对应的返回结果数据，`message_key` 指定的键对应的报错等消息，然后通过 API 类的 `response` 属性插槽注入到这个 API 类上

所以当我们访问 `hello` 接口时我们会得到
```json
{"data": "world", "msg": ""}
```

当你访问不存在的路径时也可以看到报错信息进行了包裹处理
```json
{"data": null, "msg": "NotFound: not found"}
```

如果你只希望响应模板应用与某个 API 接口，可以直接将其声明为 该 API 函数的返回类型，比如
```python hl_lines="9"
from utilmeta.core import api, response

class WrapResponse(response.Response):
    result_key = 'data'
    message_key = 'msg'

class RootAPI(api.API):
	@api.get
	def hello(self) -> WrapResponse:
		return 'world'
```

!!! tip
	通常当你像例子中声明了返回类型提示后，你应该使用 `return WrapResponse('world')` 来返回，但即使你没有这样处理，UtilMeta 也会根据你的返回类型声明生成对应的响应

### 模板字段
继承 Response 的类可以指定以下属性来定制响应模板

* `name`：响应模板的名称，将会整合到 API 文档中
* `description`：响应模板的描述，将会整合到 API 文档中
* `status`：响应模板的默认响应码

你还可以指定以下的模板参数，将 API 函数的返回结果包裹为一个 JSON 对象作为响应体

* `result_key`：对应的返回结果数据的键名称
* `message_key`：对应的报错等消息的键名称
* `count_key`：对应的结果总数的键名称，常用于分页查询
* `state_key`：业务自定义状态码的键名称

还有两个特殊的字段，你可以为它们指定类型提示，从而生成对应的 API 响应文档

* `result`：指定响应结果的类型与结构
* `headers`：指定响应头的结构，需要是一个 Schema 类

!!! tip
	如果响应模板定义了 `result_key`，这里的 `result` 结果指的就是 `result_key` 键对应的数据，否则指的是整个响应体数据

下面是一个响应模板示例

```python
class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    description = 'list of objects when path param [slug] is not provided'
    name = 'multi'
    result: List[ArticleSchema]
```

!!! tip
	默认情况下，你指定的响应结果和响应头模板只会作为提示与文档生成，而不会进行严格的转化与校验，但你也可以通过在响应类中声明 `strict = True` 属性来进行严格的结果转化与校验

### 构造参数

所有响应模板都可以通过实例化得到响应实例，其中的参数有

* `result`：第一个参数，传入返回的结果数据
* `status`：传入响应码
* `headers`：传入响应头，应该是一个字典
* `cookies`：传入响应 Set-Cookie 的字典
* `error`：传入 Python Exception 对象，会被处理为对应的响应（对应的错误码与报错信息）
* `state`：传入业务状态码，只有当模板指定了 `state_key` 时有效
* `message`：传入消息，只有当模板指定了 `message_key` 时有效
* `count`：传入结果数量，只有当模板指定了 `count_key` 时有效
* `file`:传入一个文件对象或文件路径，对应的文件将作为响应体
* `content_type`: 指定响应的 `Content-Type`
* `event_stream`: SSE 响应的事件生成器（或异步生成器）

!!! tip
	如果响应模板定义了 `result_key`，这里的 `result` 结果数据指的就是 `result_key` 键对应的数据，否则指的是整个响应体数据

下面是一个构造响应的示例
```python
from utilmeta.core import api, request, orm, response

class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    description = 'list of objects when path param [slug] is not provided'
    name = 'multi'
    result: List[ArticleSchema]

class ArticleAPI(api.API):
    @api.get
    def list(self, author_id: int, limit: int = 10) -> MultiArticlesResponse:
        base_qs = Article.objects.filter(author_id=author_id)
        return MultiArticlesResponse(
            result=ArticleSchema.serialize(base_qs[:limit]),
            count=base_qs.count()
        )
```

我们在 list 接口返回时使用 MultiArticlesResponse 构造了对应的响应，其返回的响应体结构应该为

```json
{
    "articles": [],
    "articlesCount": 0
}
```


!!! tip
	即使你没有在 API 类中定义 `response` 属性，你在 API 函数中访问 `self.response` 也会得到一个 Response 类，所以你在任何 API 函数中都可以使用 `return self.response(...)` 来构造响应对象

### Server-Sent Events

API 服务端可以使用 Server-Sent Events (SSE) 技术向客户端发送流式事件响应，如处理大语言模型的流式输出，UtilMeta 框架也支持定义 SSE 接口，
```python
from utilmeta.core import api, request, response

class ChatAPI(api.API):
    @api.post
    async def chat(
        self,
        message: str = request.BodyParam()
    ) -> response.SSEResponse:
        async for chunk in await self.get_client().chat.completions.create(
            messages=[{'role': 'user', 'content': message}],
            stream=True
        ):
            yield response.ServerSentEvent(
	            event='message', 
	            data={'v': chunk.choices[0].delta.content}
	        )
            
    def get_client(self):
        # init LLM Client
        ...
```

如果你生成 SSE 的生成器 / 异步生成器函数已经定义好了，你也可以直接在响应构建的 `event_stream` 参数传入一个生成器 / 异步生成器，这样 UtilMeta 也会自动进行 SSE 响应的处理，例如：
```python
from utilmeta.core import api, request, response

class ChatAPI(api.API):
    async def event_stream(self, message: str):
        async for chunk in await self.get_client().chat.completions.create(
            messages=[{'role': 'user', 'content': message}],
            stream=True
        ):
            yield response.ServerSentEvent(
	            event='message', 
	            data={'v': chunk.choices[0].delta.content}
	        )

    @api.post
    async def chat(
        self,
        message: str = request.BodyParam()
    ):
        return self.response(event_stream=self.event_stream(message))

    def get_client(self):
        # init LLM Client
        ...
```

!!! tip
	当 SSE 的生成器在迭代过程中抛出异常时，会被自动处理为一个 `event: error` 事件（包括当 API 接口定义了 `timeout` 时，在时限内没有完成输出抛出的 TimeoutError）

!!! note
	UtilMeta >= 2.8 版本支持此特性


## 钩子机制

在 API 类中还可以定义一种特殊的函数，称为 **钩子函数**，钩子函数可以作用于 API 类的一个或多个接口与子路由，进行自定义校验，数据预处理，响应处理和错误处理等操作，API 类中的钩子函数类型有

* **预处理钩子**：使用 `@api.before` 定义，在接口函数执行前前调用
* **响应处理钩子**：在使用 `@api.after` 定义，在接口函数执行后调用
* **错误处理钩子**：使用 `@api.handle` 定义，在接口函数或钩子抛出错误时调用

### `@api.before` 预处理钩子
预处理钩子在目标函数执行前执行，多用于进行自定义校验和数据预处理等操作，预处理钩子使用 `@api.before` 装饰器定义，如

```python hl_lines="20"
from utilmeta.core import api, request, orm, response

@api.route('{slug}/comments')
class CommentAPI(api.API):
    slug: str = request.SlugPathParam

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article: Optional[Article] = None

    async def get(self) -> ListResponse:
        return await CommentSchema.aserialize(
            Comment.objects.filter(article=self.article)
        )

    async def post(self, comment: CommentSchema[orm.A] = request.Body):
        comment.article_id = self.article.pk
        await comment.asave()
        
    @api.before(get, post)
    async def handle_article_slug(self):
        article = await Article.objects.filter(slug=self.slug).afirst()
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article
```

`@api.before` 装饰器可以传入多个 API 函数或 API 类，钩子函数将会在对应的 API 函数或 API 类调用前执行，这样你可以在处理请求前编写可复用的逻辑

在这个例子中，我们定义的 `handle_article_slug` 钩子函数会在 get, post 方法执行前调用，从而处理 `slug` 路径参数得到对应的文章对象

另外，如果你需要钩子函数作用于该 API 类内的所有接口，可以使用 `@api.before('*')`

!!! tip "异步钩子"
	当你编写普通的同步接口时，对于需要在 API 类的所有接口前调用的逻辑，你可以直接在 API 函数的 `__init__` 方法定义，但如果这些逻辑涉及到异步（`async` / `await`）调用，你就需要声明一个异步的预处理钩子来编写了，因为类的初始化方法无法改造成异步的

### `@api.after` 响应处理钩子
响应处理钩子在目标函数执行后执行，使用 `@api.after` 装饰器定义，钩子函数可以接收目标接口函数生成的响应，对其进行处理并返回，如
```python hl_lines="7"
from utilmeta.core import api

class RootAPI(api.API):
	user: UserAPI
	article: ArticleAPI

    @api.after('*')
    def add_timestamp(self, resp):
	    resp.headers['Server-Timestamp'] = int(self.request.time.timestamp() * 1000)
        return resp
```

响应处理钩子函数的第一个参数会传入接口返回的响应对象，是一个 Response 实例，在这个例子中，`add_timestamp` 钩子会处理 RootAPI 中所有接口的响应，为它们的响应头添加 `'Server-Timestamp'` 字段

!!! tip
	在所有的钩子装饰器中，`'*'` 都表示作用于当前 API 类中的所有接口

此外，利用响应处理钩子，你还可以批量为接口生成响应，响应处理钩子的返回结果会代替 API 函数的返回结果作为响应进行返回，比如
```python hl_lines="28-29"
from utilmeta.core import api, orm, request

class SingleArticleResponse(response.Response):
    result_key = 'article'
    name = 'single'
    result: ArticleSchema
    
class ArticleAPI(api.API):
	def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.article = None

	@api.get('/{slug}')
    async def get_article(self): pass

	@api.put('/{slug}')
    async def update_article(self, article: ArticleSchema[orm.WP] = request.Body):
        article.id = self.article.pk
        await article.asave()
        
	@api.before(get_article, update_article)
    async def handle_slug(self, slug: str = request.SlugPathParam):
        article = await Article.objects.filter(slug=slug).afirst()
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article
        
    @api.after(get_article, update_article)
    async def handle_result(self) -> SingleArticleResponse:
        return SingleArticleResponse(
            await ArticleSchema.ainit(self.article)
        )
```

在这个例子中，`get_article` 和 `update_article` 接口所需要的请求处理和结果生成逻辑相同，所以我们定义了一个预处理钩子和一个响应处理钩子来复用逻辑

预处理钩子将 `slug` 路径参数解析查询得到文章实例 `self.article`，而响应处理钩子则把这个文章实例进行序列化并返回

!!! tip
	上面这个例子很好的展示了，你可以通过在 API 类的 `__init__` 函数声明自定义属性的方式在钩子与 API 函数之间传递信息，这也是使用类进行 API 开发的方便之处

#### 响应的生成规则
在 UtilMeta 中，Response 响应模板有三种声明的方式

* 在 API 接口函数的返回提示中声明
```python
class RootAPI(api.API):
    def get(self) -> WrapResponse: pass
```
* 在 响应处理钩子中的返回提示中声明
```python
class RootAPI(api.API):
    @api.after('*')
    def handle_response(self) -> WrapResponse: pass
```
* 在 API 类的 `response` 属性中声明
```python
class RootAPI(api.API):
    response = WrapResponse
```

如果一个函数声明了 Response 响应模板，那么它的返回值就会被处理为这个模板的响应，如果一个 API 类声明了 `response` 属性，在这个 API 类在调用后也会得到对应的模板响应

而如果 API 接口函数或 API 类没有对应的响应模板声明，函数返回的结果数据就会被一路返回，直到遇到声明 `response` 属性的 API 类或者声明返回类型的响应处理钩子

而当一个 Response 响应实例形成后，之后的响应模板就不会对它进行任何处理。也就是说响应的生成遵循的是 **就近优先** 原则

### `@api.handle` 错误处理钩子 
在 API 函数中可能发生各种各样的错误，你有时你也需要在检测到失败条件时主动抛出错误，默认情况下 UtilMeta 会捕捉 API 接口抛出的所有错误并根据错误的类型和消息返回对应的响应

但除此之外你也可以使用错误处理钩子 `@api.handle` 自定义错误的处理逻辑，钩子装饰器的参数是目标接口函数或接口类，以及需要处理的错误类型，使用方式如下
```python hl_lines="18 22"
from utilmeta.core import api, response
from utilmeta.utils import exceptions as exc
from utilmeta.utils import Error

class State:
	INVALID_PARAMS = 400000
	AUTH_FAILED = 400001
	PASSWORD_WRONG = 400002
	NOT_FOUND = 400004

class RootAPI(api.API):
	user: UserAPI
	
    class response(response.Response):
	    message_key = 'msg'
	    result_key = 'data'
	        
    @api.handle(UserAPI, exc.Unauthorized, exc.PermissionDenied)
    def handle_user_auth(self, e: Error):
        return self.response(state=State.AUTH_FAILED, error=e)
    
    @api.handle('*', exc.Notfound)
    def handle_not_found(self, e: Error):
        return self.response(state=State.NOT_FOUND, error=e)
```

在这个例子中，我们声明了两个错误处理钩子，为不同类型的错误指定不同的业务状态码

* `handle_user_auth`：处理 UserAPI 发生的 `exc.Unauthorized` 错误和 `exc.PermissionDenied` 错误，指定了 `State.AUTH_FAILED` 作为业务状态码（传入 `state` 参数）
* `handle_not_found`：对所有的 `exc.Notfound` 错误进行处理，指定了 `State.NOT_FOUND` 作为业务状态码

!!! tip
	通过构建响应的 `error` 参数传入异常实例，响应可以直接使用其中的错误消息和默认状态码

在错误处理钩子中的第一个参数会传入一个 Error 错误示例，它是对 Python Exception 的一个包装，方便获取其中的错误信息，其中的属性有

* `exception`：其中包裹的 Python 异常（Exception）实例
* `type`：错误实例的类型，如 ValueError, TypeError 等，是一个 Exception 的子类
* `traceback`：错误的调用栈字符串
* `message`：包含着异常类型，异常信息和异常调用栈的字符串，与 Python 自动输出的错误信息格式类似
* `status`：错误所默认对应的响应码，如 `exc.BadRequest` 错误默认对应 400，`exc.Notfound` 错误默认对应 404 等

#### 默认的错误处理
UtilMeta 的默认错误处理逻辑是

* 错误信息会被处理为响应构造参数中的 `message`，如果模板声明了 `message_key`，则会对应错误信息
* 根据错误的类型得到对应的响应码 `status`，如果没有识别到对应的类型，则会返回 500 响应

在开发中我们常用的错误类型包括

**HTTP 标准错误**

在 `utilmeta.utils.exceptions` 中定义了许多 HTTP 标准错误，它们会被自动识别对应的响应码，常用的 HTTP 标准错误如下

* `BadRequest`：当请求参数校验失败时抛出，默认返回 **400** 响应
* `Unauthorized`：当鉴权组件检测到请求未携带鉴权凭据时抛出，默认返回 **401** 响应
* `PermissionDenied`：一般当请求用户不满足 API 接口所需的权限时抛出，默认返回 **403** 响应
* `Notfound`：请求的路径不存在时抛出，默认返回 **404** 响应
* `MethodNotAllowed`：当请求的方法不在请求路径所支持的方法时抛出，默认返回 **405** 响应

**Python 标准错误**

某些 Python 标准错误也会识别出响应码

* `PermissionError`：当系统命令等操作权限不足时抛出，默认返回 **403** 响应
* `FileNotFoundError`：文件路径不存在时抛出，默认返回 **404** 响应
* `NotImplementedError`：接口尚未实现，默认返回 **501** 响应
* `TimeoutError`：当接口的超时条件不满足时抛出，默认返回  **503** 响应

在 编写 API 函数时，你可以遵循短路优先原则，尽可能早的在函数逻辑中处理失败的情况并抛出错误，你所抛出的错误都能够得到妥善的处理并生成相应的响应而不会导致服务出现问题，你也可以通过在上层定义错误处理钩子的方式自行对错误进行处理，或者交由最上层的默认错误处理逻辑根据错误的类型生成响应

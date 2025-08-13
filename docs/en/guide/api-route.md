# API Class and Routing

## Define the API

We learned UtilMeta’s simplest API in Hello World.
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

This simple example shows two ways to declare and organize APIs in UtilMeta.

* **API Class**: Inherit `utilmeta.core.api.API`, in which you can declare a series of functions as APIs, or mount other API classes to define tree-like routes.
* **API function**: functions in API class decoratefd with `@api` decorators are discovered as API endpoint.

### `@api` Decorator

Decorator functions are built into the `api` module to define API endpoint functions

*  `@api.get`: Declare the API interface for the GET method
*  `@api.put`: Declare the API interface for PUT methods
*  `@api.post`: Declare the API interface for the POST method
*  `@api.patch`: Declares the API interface for the PATCH method
*  `@api.delete`: API interface to declare DELETE method

All `@api` decorators support passing in parameters to specify configurations, including

* `<route>`: The first parameter. You can pass in a path template string to specify the path of the API. more specific usage can refer to [Path Parameters](../handle-request/#path-parameters).
* `summary`: API description, will be integrated into the OpenAPI documentation
* `deprecated`: Whether the API is deprecated (not recommended to use)
* `idempotent`: Whether the API is **idempotent** (multiple requests of the same params have the same effect as a single request, which is important for writing a client-side retry mechanism)
* `private`: Whether the API is private. Private API do not provide public access and do not appear in the generated API documentation.
* `tags`:  Specify the `tags` of OpenAPI operation (by default generated from API routes)
* `description`:  Specify the `description` of OpenAPI operation (using the doc string of function by default)
* `extension`: Specify the extra OpenAPI operation fields by a dict, custom fields should be startswith `x-`
* `timeout`: Set the timeout of the API function, raise `TimeoutError` if the function cannot return the response in such timeout. 

!!! tip
	The `"""doc_string"""` of your API class of function will be integrated to the `description` field of the generated OpenAPI docs, such as
	```python
	class UserAPI(api.API):
		"""This is the user API"""
		@api.post
		def login(self):
			"""This is the login API"""
	```

If `@api` the decorator does not specify a path template string with the first argument, it uses the name of the decorated function as the path to the API

!!! warning
	If you need to define the path with the name of a HTTP method, you need to put that path in the path template string, like
	```python
	class RootAPI(api.API):
		@api.get('patch')
		def get_patch(self): pass
	```

### Core methods

Functions named HTTP methods (get/put/post/patch/delete) in the API class are automatically discovered as API endpoint functions (even without `@api` decorator), and the path is consistent with the path of the API class. They are called **core methods** of the API class, such as

```python
from utilmeta.core import api

class ArticleAPI(api.API):
    def get(self, id: int) -> ArticleSchema:
	    return ArticleSchema.init(id)

    def post(self, data: ArticleSchema = request.Body):
        data.save()
```

The `ArticleAPI` in the example declares two core method functions, `get` and `post`, if the ArticleAPI is mounted to the `/article` path, calling `GET/article` will execute the `get` function, and similarly calling `POST/article` will execute the `post` function

!!! tip "HEAD and OPTIONS method"
	When you declare a `GET` endpoint, the path of the API automatically has the ability to respond to the `HEAD` method request. (by return a response that is consistent with the headers and status code of the GET API, but with empty body)
	For any method's API path, it will have the ability to respond to `OPTIONS` method requests, and will return headers such as allowed origin, methods, headers.
	So you don't need to declare the  `HEAD` or `OPTIONS` API

## API Mount and Routing

In addition to defining the endpoints in the API class, we can also mount an API class to another API class by means of API mounting, so as to define the tree-like routing. The usage of API mounting is as follows
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

The API is mounted by declaring the type annotation. In this example, we mount the `ArticleAPI` on the RootAPI's `article` path and the `UserAPI` on the `user` path, thus forming the following routes

```
/ ------------------ RootAPI
/article ----------- ArticleAPI
/article/feed ------ ArticleAPI.feed
/user -------------- UserAPI
/user/login -------- UserAPI.login
```

### Configure routing using `@api.route`

There is a `@api.route` decorator used to configure the route for the entire API class. The usage is as follows

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

The route defined in `@api.route` will overrides the mounted attribute, so the route declared in the example is as follows
```
/ ------------------------- RootAPI
/article ------------------ ArticleAPI
/article/{slug}/comments -- CommentAPI
```

Where all endpoints of the CommentAPI will have a path parameter named `slug`

 `@api.route` is similar to other API decorators, you can define the following parameters in addition to the path string

* `summary`: API description, will be integrated into the OpenAPI documentation
* `deprecated`: Whether the API is deprecated (not recommended to use)
* `private`: Whether the API is private. Private API do not provide public access and do not appear in the generated API documentation.

### Mounting the root API

In UtilMeta, all API classes need to be eventually mounted on an API class to provide access, which is **root API** (usually named RootAPI), and the root API also needs to be mounted on the service.

In Hello World, we have seen a way to mount the root API.
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

There are two parameters in the initialization of UtllMeta service to mount the root API

* `api`: Pass in the root API class or its reference string.
* `route`: The path of the root API, which is empty by default

For example, when your service runs at the `127.0.0.1:8000` address, the url of the root API is at `127.0.0.1:8000/api`, and the url of the `hello` endpoint is `127.0.0.1:8000/api/hello`

Alternatively, you can use **Reference string** to mount root API in the following way

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

This approach is also known as **Lazy loading**, is often used to handle circular dependencies, where the root API is loaded before the service is started.

!!! Tip “Reference string”
	Reference string stand for the import path in the current project, including the package, module and class name, for instance, if you can import the class in the following way
	```python
	from service.api import RootAPI
	```
	The reference string of the RootAPI is `'service.api.RootAPI'`

In addition, the `mount` method of UtilMeta service can also be used to mount the root API.
```python hl_lines="5"
from utilmeta import UtilMeta

service = UtilMeta(...)

@service.mount(route='/api')
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

It is important to note that a service can only mount one root API, regardless of the method used

!!! warning "Django mount strategy"
	If you are using Django as a backend or ORM, you need to mount the root API using the **reference string** method, because Django needs to be setup before loading the models. This process will be automatically completed by the built-in `DjangoSettings` in UtilMeta before the service starts. However, if you import the API class and Django models before that, the following error will occur
	```python
	django.core.exceptions.ImproperlyConfigured: 
	Requested setting INSTALLED_APPS, but settings are not configured, ...	
	```

## Use API class

### Get the current request

In the API function, you can get the current request object through `self.request`. The commonly used attributes are

* `method`: HTTP method of the current request
* `url`: Full URL path of the request (including protocol, domain name, path and query string)
* `query`: A query string `dict` of the request
* `headers`: A headers `dict` of the request
* `body`: body data of the request
* `time`: The requested time, returning an `datetime`
* `ip_address`: IP address of the request, return one of  `ipaddress.IPv4Address` or `ipaddress.IPv6Address`

Here is a simple usage example, returning the IP address of the current request
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def ip(self) -> str:
        return str(self.request.ip_address)
```


!!! note
	You can use `self.request.adaptor` to get the Adaptor object of the request which contains the original request of the runtime backend you used, For instance, if you are using `starlette` as runtime backend, `self.request.adaptor.request` will give you the  `starlette.requests.Request` object

### General parameters

If all endpoints in an API class need to carry a certain parameter, the parameter can be declared as a general parameter of the API class. By define it as a property in the API class. We modify the CommentAPI in the above example.

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

CommentAPI uses `@api.route` to specify a path template string for the entire API class, so you can declare the `slug` parameter directly as a class property of the API, so that all the endpoints can access it directly without repeating the declaration

We directly access `slug` and query the corresponding article instance in the initialization function of the CommentAPI, so that we can directly use the article instance in the API functions. Here you can also see the convenience of using the API class.

All general parameters need to specify a `utilmeta.core.request` class as the value of the property. You can learn all request attributes in [Handle request](../handle-request) . The commonly used ones are

*  `request.PathParam`: Define path parameter
*  `request.QueryParam`: Define query parameter
*  `request.HeaderParam`: Define request header parameter
*  `request.CookieParam`: Define Cookie parameter

### Call API at runtime

To better reuse API logic, you may need to call other API endpoints in an API function, which is very simple to implement in UtilMeta.

All API endpoints in UtilMeta are an instance function of the API class, so you need to initialize the corresponding API class before calling the endpoint function. There are two methods.
#### Initialization by mount
If you call the mounted API of the current API class, you can get a automatically-initialized API instance by access using `self`. You can directly call the method in it by passing the parameters, as shown in
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

In this example, we called the initialized instance of CommentAPI by `self.comments`, you can directly call the `get` function of CommentAPI to get all the comments on the current post.

!!! note
	Using the type-annotation syntax to mount API, you will find that when you calling them in the API methods, you can fully gain the IDE's type hinting and attributes autocompletion ability
#### Custom-initializing
You can also initialize and call the API class by yourself. The initialization parameter of the API class is a **Request object**, and the current request object can be accessed through `self.request`. So you can get the API instance directly through `CommentAPI(self.request)`
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

### Inheritance and composition
You can also mount multiple API classes to a path by inheritance. Examples are as follows
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

The defined path is to combine the interfaces of the inherited API classes.
```
/ --------- RootAPI
/feed ----- ArticleAPI.feed
/login ---- UserAPI.feed
/hello ---- RootAPI.hello
```

!!! warning
	You can't have conflicted path in composition APIs
## Generate response

For a simple API, you can return the result data directly, and UtilMeta will automatically process it as a 200 HTTP response, but UtilMeta still has a sound response template and generation system, where you can define the status code, headers and data structure by yourself.

Let’s look at a simple example of a response template.
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

All API responses of UtilMeta are inherited from `utilmeta.core.response.Response`. The example specified a template for the response, so the return data of the API function is wrapped as a JSON object, in which `result_key` specified key corresponds to the result data. The `message_key` specified key corresponds to the error message, injected into the API class through the `response` attribute slot.

So when we access `hello` the interface, we get
```json
{"data": "world", "msg": ""}
```

When you access a path that doesn’t exist, you can also see that the error message has been processed.
```json
{"data": null, "msg": "NotFound: not found"}
```

If you only want the response template applied in a single endpoint, you can directly declare it as the return type of the API function, such as
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
	Usually along with the return type annotation, you should use `return WrapResponse('world')` to return, but even if you forget to do so, UtilMeta will generate the right response based on your declaration

### Template fields
A class that inherits `Response` can specify the following properties to define the response template

* `name`: The name of the response template, which will be integrated into the API documentation.
* `description`: The description of the response template, will be integrated into the API documentation.
* `status`: The default status code of the response template

You can also specify the following template parameters to wrap the result of the API function as a JSON object as the response body

* `result_key`: Key name of the corresponding returned result data
* `message_key`: Key name of the corresponding error message
* `count_key`: Key name of the corresponding total number of results, often used for paged queries.
* `state_key`: Key name of user-defined action state code.

There are also two special fields for which you can specify a type annotation to generate the corresponding API response document

* `result`: Specify the type and structure of the response data.
* `headers`: Specifies the structure of the response headers

!!! tip
	If the response template defined `result_key`, the `result` here refers to the data corresponding to the `result_key` key. Otherwise, it refers to the entire response body data

The following is an example of a response template

```python
class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    description = 'list of objects when path param [slug] is not provided'
    name = 'multi'
    result: List[ArticleSchema]
```

!!! tip
	By default, the result and headers schema defined in the response template is only used in template generation with no validation, but you can define the `strict = True` in the Response class to perform the strict validation.
### Response parameters

All response templates can be instantiated into response instances with the following params

* `result`:  The first parameter is the returned result data
* `status`:   Status code of the response.
* `headers`:  A `dict` for the response headers.
* `cookies`:  A `dict` for response `Set-Cookie` pairs.
* `error`:  Pass a Python Exception object, will be processed as the corresponding response.
* `state`: Incoming business status code, valid only when the template is specified `state_key`
* `message`: Incoming message, valid only when the template is `message_key` specified
* `count`: The number of results passed in, valid only when the template is `count_key` specified
* `file`: Specify a file object or file path for the response body.
* `content_type`: Specify the `Content-Type` of the response,
* `event_stream`: An event generator / async generator for Server-Sent Events (SSE) response.

!!! tip
	If the response template defined `result_key`, the `result` is the data corresponding to the `result_key` key. Otherwise, it will be to the entire response body data.

Here is an example of constructing a response
```python hl_lines="14-17"
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

We use `MultiArticlesResponse` to construct the corresponding response in the get `list` endpoint, and the returned response body structure should be

```json
{
    "articles": [],
    "articlesCount": 0
}
```


!!! tip
	Even if you didn't defined a `response` property in the API class, you can still access `self.request` in API function and get a Response class, so in any endpoints, you can use  `return self.response(...)` to construct response

### Server-Sent Events

API server can use `Server-Sent Events` (SSE) to send streaming events to client (eg. handle LLM stream output), UtilMeta also support SSE API:

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

You can also use the `event_stream` of response to pass in a event generator / async generator: 
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
	the exception raised by SSE generator will be processed to an `event: error` event (includes the TimeoutError if the API has set `timeout`)
	
!!! note
	requires UtilMeta >= 2.8 
## Hook mechanism

In the API class, you can also define a special function called **Hook**, which can applied on one or more endpoints and sub-routes of the API class to perform operations such as custom verification, data preprocessing, response processing, and error handling. The types of hook functions in the API class are

* **Before hook**: is called before the API function is executed, using `@api.before` to define
* **After hook**: is called after the API function is executed, using `@api.after` to define
* **Error hook**: is called when an API function or hooks throws an error, using `@api.handle` to define

### `@api.before` hook
The `@api.before` hook is called before the target function is executed. It is mostly used for operations such as custom verification and data preprocessing, such as

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

 `@api.before` decorator can pass in multiple API functions or API classes, and the hook function will be executed before the corresponding endpoints or routes is called, so you can write reusable logic before processing the request.

In this example, the `handle_article_slug` hook function we defined will be called before the `get` and `post` methods are executed, thus processing the path parameter `slug` to get the corresponding article object.

In addition, if you need hook functions to work on all interfaces within the API class, you can use the

!!! tip "Async hooks"
	If you are wring sync API functions, the logic before executing **All** APIs can be placed in the `__init__` function, but if those logic contains asynchronous (`async` / `await`), you should declare an asynchronous before hook

### `@api.after` hook
The `@api.after` hook is called after the target function is executed, the hook function can receive the response generated by the target API function, process and return, such as
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

The first parameter of the after hook function will pass in the response object returned by the API, which is a `Response` instance. In this example, `add_timestamp` hook will process the responses of all endpoints in the RootAPI and add `'Server-Timestamp'` fields to their headers.

!!! tip
	In all the hook decorators, `'*'` means to hook all the endpoints and sub-routes of the current API class

In addition, you can also generate responses for the endpoints in batches using after hook, and the return value of the after hook will replace the return value of the API function as the response, such as
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

In this example, `get_article` and `update_article` requires the same request processing and result generation logic, so we define a before hook and a after hook to reuse the logic.

The before hook parses the `slug` path parameter to get the article instance and assigned to `self.article`, and the after hook serializes the article instance then returns it.

!!! tip
	 The example above shows that you can pass infomation among endpoints and hooks through the instance attribute defined in `__init__` method, that is also a convenience of using API class

#### Response generation rules
In UtilMeta, there are three ways to declare a Response template

* Declared in the return annotation of the API function
```python
class RootAPI(api.API):
    def get(self) -> WrapResponse: pass
```
* Declared in the return annotation of the after hook.
```python
class RootAPI(api.API):
    @api.after('*')
    def handle_response(self) -> WrapResponse: pass
```
* Declared in `response` attribute of the API class
```python
class RootAPI(api.API):
    response = WrapResponse
```

If a function declares a `Response` template, the return value will be processed through the template. If an API class declares an `response` attribute, it will also get the response of the corresponding template after calling.

If the API function or API class does not have a response template, the result data will be returned all the way until any API class of after hooks with the response template

When a `Response` instance is formed, the subsequent response template will not applied to it. Thus the generation of response follows the **The nearest priority** principle.

### `@api.handle` hook
A variety of errors can occur in API functions, and sometimes you need to actively throw errors when a failure condition is detected. By default, UtilMeta catches all errors thrown by the API functions and returns a response withe status code and message based on the exception

But in addition, you can also use the `@api.handle` hook to customize the error handling logic. The parameters of the hook decorator are the target API functions or API class, and the type of exception to be handled. The way to use it is as follows
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

In this example, we have declared two error handling hooks that specify different action state codes for different types of errors

* `handle_user_auth`: Handle the `exc.PermissionDenied` and `exc.Unauthorized` errors in the UserAPI, and specify them as the `State.AUTH_FAILED` state code (in `state` parameters). 
* `handle_not_found`: Handle all `exc.Notfound` errors, specify them as the `State.NOT_FOUND` state code

!!! tip
	By passing exception to `error` param, response can use it's error message and default status code

The first parameter in the error handling hook passes an `Error` instance, which is a wrapper around a Python Exception to get the error information in it. The properties are

* `exception`: the wrapped Python Exception instance.
* `type`: the type of the error instance, such as ValueError, TypeError, etc., is a subclass of Exception
* `traceback`: the stack trace of the exception
* `message`: a string containing the exception type, exception information, and exception call stack, similar to the format of Python’s automatic error message output.
* `status`: Response status code corresponding to the error by default. For example 400 for `exc.BadRequest` by default, and 404 for `exc.Notfound` by default.

#### Default error handling
The default error handling logic in UtilMeta is

* The error message will be processed as `message` in response construction parameter, and will be the `message_key` corresponding value if declared.
* Generate `status` code according to the type of error. If the corresponding type is not identified, a 500 response will be returned

Common error types in development include 

**HTTP Standard Error** 

`utilmeta.utils.exceptions` defined many HTTP standard errors, which will be automatically identified with corresponding response codes. Common HTTP standard errors are as follows

* `BadRequest`: Thrown when the request parameter verification fails. The default is to return a **400** response.
* `Unauthorized`: Thrown when the authentication component detects that the request does not carry authentication credentials, and the default is to return a **401** response
* `PermissionDenied`: Thrown when the requesting user does not meet the permissions required by the API. The default is to return a **403** response.
* `Notfound`: Thrown when the requested path does not exist, and the default is to return a **404** response.
* `MethodNotAllowed`: Thrown when the requested method is not in the method supported by the request path. The default is to return a **405** response.

**Python standard error**

Some Python standard errors also recognize response codes.

* `PermissionError`: Thrown when the system command and other operation permissions are insufficient, and the default is to return a **403** response.
* `FileNotFoundError`: Thrown when the file path does not exist, and the default is to return a **404** response.
* `NotImplementedError`: The interface has not been implemented, and the default is to return a **501** response.
* `TimeoutError`: Thrown when the timeout condition of the interface is not met, the default is to return a **503** response.

When writing API functions, you can follow short-circuit priority strategy, handle the failure in the function logic as early as possible and throw errors. The errors you throw can be properly handled and the corresponding response can be generated without causing service problems. You can also handle errors by defining error handling hooks in the upper layer.

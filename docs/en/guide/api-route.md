# API Class and Routing

## Define the API

We saw UtilMeta’s simplest API interface in Hello World.
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

This simple example shows two ways to declare and organize interfaces for UtilMeta.

* ** API class ** Inheritance `utilmeta.core.api.API`, in which you can declare a series of API functions as interfaces, or mount other API classes to define tree-like routes.
* Defined ** API function ** in API functions, functions decorated with `@api` decorators are treated as API endpoint interfaces.

###  `@api` Decorator

Several decorator functions are built into the `api` module to define API functions

*  `@api.get`: Declare the API interface for the GET method
*  `@api.put`: Declare the API interface for PUT methods
*  `@api.post`: Declare the API interface for the POST method
*  `@api.patch`: Declares the API interface for the PATCH method
*  `@api.delete`: API interface to declare DELETE method

All `@api` decorators support passing in parameters to specify specific interface configurations, including

*  `<route>`: The first parameter. You can pass in a path string to specify the path or path template of the API. Please refer to the specific usage.
* Introduction to the `summary` API, `summary` properties that will be integrated into the OpenAPI documentation interface
*  `deprecated`: Is the API deprecated
*  `idempotent`: Whether the API is idempotent (multiple invocations of the same parameter have the same effect as a single invocation, which is important for writing a client-side retry mechanism)
*  `private`: Whether the API is private. Private interfaces do not provide public calls and do not appear in the generated API documentation.

!!! tip
	
	```python
	class UserAPI(api.API):
		"""This is the user API"""
		@api.post
		def login(self):
			"""This is the login API"""
	```

If `@api` the decorator does not specify a path string with the first argument, it uses the name of the decorated function as the path to the API interface, as in Hello World `hello`

!!! tip
	```python
	class RootAPI(api.API):
		@api.get('patch')
		def get_patch(self): pass
	```

### Core methods

In addition to API functions declared with `@api` decorators, functions named HTTP methods (get/put/post/patch/delete) in the API class are automatically treated as API functions, and the path is consistent with the path of the API class. They are called core methods of the API class, such as

```python
from utilmeta.core import api

class ArticleAPI(api.API):
    def get(self, id: int) -> ArticleSchema:
	    return ArticleSchema.init(id)

    def post(self, data: ArticleSchema = request.Body):
        data.save()
```

The Article API in the example declares `get` two core method functions, and `post`, if the Article API is mounted to the `/article` path, Then the call `GET/article` will execute `get` the logic of the function, and similarly the call `POST/article` will execute the `post` function

!!! Tip “HEAD and OPTIONS Method
	
	

## API Mount and Routing

In addition to defining the interface in the API class, we can also mount an API class to another API class by means of API mounting, so as to define the tree-like routing. The usage of API mounting is as follows
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

The API is mounted by declaring the type. In this example, we mount the Article API on the RootAPI `article` path and the User API on `user` the path, thus forming the following URL path

```
/ ------------------ RootAPI
/article ----------- ArticleAPI
/article/feed ------ ArticleAPI.feed
/user -------------- UserAPI
/user/login -------- UserAPI.login
```

### Configure routing using `@api.route`

We know that `@api` the following method decorator can declare the API interface through the decorator function. In addition, there is a `@api.route` decorator used to configure the route for the API class. The usage is as follows

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

Using `@api.route` the defined route path overrides the mounted attribute path, so the route declared in the example is as follows
```
/ ------------------------- RootAPI
/article ------------------ ArticleAPI
/article/{slug}/comments -- CommentAPI
```

Where all interfaces of the CommentAPI will have a path parameter named `slug`

 `@api.route` As with other API decorators, you can define the following parameters in addition to the path string

* Introduction to the `summary` API, `summary` properties that will be integrated into the OpenAPI documentation interface
*  `deprecated`: Is the API deprecated
*  `private`: Whether the API is private. Private interfaces do not provide public calls and do not appear in the generated API documentation.

### Mounting of the root API

In UtilMeta, all API classes need to be eventually mounted on an API class to provide access, which is **root API** (usually named RootAPI), and the root API also needs to be mounted on the service to provide access.

In Hello World, we have seen a way to mount the root API.
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
    backend=django,
    api=RootAPI,
    route='/api'
)
```

There are two parameters in the initialization parameters of the UtllMeta service to mount the root API

*  `api`: Pass in the root API class or its reference string.
*  `route`: The path of the root API mount, which is empty by default, namely

For example, when your service runs at the `127.0.0.1:8000` address, the address of the root API is at `127.0.0.1:8000/api`, and the address of the interface whose path is `hello` defined on it is at.

Alternatively, you can use ** Reference string ** the mount root API in the following way

=== “main.py”
	```python
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
=== "service/api.py”
	```python
	from utilmeta.core import api
	
	class RootAPI(api.API):
	    @api.get
	    def hello(self):
	        return 'world'
	```

This approach, also known as **Lazy loading**, is often used to solve problems such as circular dependencies, where the root API is loaded before the service is started.

!!! Tip “Reference string”
	```python
	from service.api import RootAPI
	```

In addition, a `mount` method named in the UtilMeta service instance can also be used to mount the root API.
```python
from utilmeta import UtilMeta

service = UtilMeta(...)

@service.mount(route='/api')
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

It is important to note that a service can only mount one root API, regardless of the method used

!!! The mount policy for the warning “Django.
	```python
	django.core.exceptions.ImproperlyConfigured: 
	Requested setting INSTALLED_APPS, but settings are not configured, ...	
	```

## Use API class

### Access the current request

In the API function, you can access the current request data through `self.request`. The commonly used attributes are

*  `method`: HTTP method of the current request
*  `url`: Full URL path of the request (including protocol, domain name, path, query string)
*  `query`: The dictionary obtained by parsing the query string of the request
*  `headers`: Request Header Dictionary
*  `body`: Request body data
*  `time`: The requested time, returning an `datetime` object
*  `ip_address`: IP address of the request, return one or

Here is a simple usage example, returning the IP address of the current request
```python
from utilmeta.core import api

class RootAPI(api.API):
    @api.get
    def ip(self) -> str:
        return str(self.request.ip_address)
```


!!! note

### Public parameters

If all interfaces in an API need to carry a certain parameter, the parameter can be declared as a public parameter of the API. The declaration method is very simple, that is, it is defined as a variable in the API class. We modify the CommentAPI in the above example.

```python
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

The CommentAPI uses `@api.route` to specify a path template string for the entire API class, so you can declare this parameter directly as a class property of the API, so that each interface can access it directly without repeating the declaration

We directly access `slug` the parameters and query the corresponding article instance in the initialization function of the CommentAPI, so that we can directly use the article instance in the interface. Here you can also see the convenience of using the API class.


All public parameters need to specify a `utilmeta.core.request` parameter type as the value of the attribute. You [解析请求参数](../handle-request) are learning about all request attributes. The commonly used ones are

*  `request.PathParam`: Define path parameters
*  `request.QueryParam`: Define query parameters
*  `request.HeaderParam`: Define request header parameters
*  `request.CookieParam`: Define Cookie parameters

### Call API at runtime

To better reuse API logic, you may need to call other API interfaces in an API function, which is very simple to implement in UtilMeta.

All interfaces in UtilMeta are an instance function of the API class, so you need to initialize the corresponding API class before calling the interface. There are two methods.
#### Initialization by mount
If you call the API mounted by the current API class, the API you access directly by using the instance attribute is an automatically initialized API class instance. You can directly call the method in it by passing in the corresponding function parameter, as shown in
```python
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

In this example, we `self.comments` call the mounted CommentAPI in the get interface of ArticleAPI, and access the initialized instance of CommentAPI. So you can directly call the get access to get all the comments on the current post.

!!! note

#### Custom-initializing
In addition to automatically initializing the API class by mounting, you can also initialize and call the API class by yourself. The initialization parameter of the API class is one ** Request object **, and the current request object can be accessed through `self.request`. So you can get the API instance directly through `CommentAPI(self.request)`
```python
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
In addition to API mounting, you can also define multiple API classes to a path by inheritance or multiple inheritance. Examples are as follows
```python
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

## Generate response

For a simple interface, you can directly return the result data, and UtilMeta will automatically process it as a 200 HTTP response, but UtilMeta still has a perfect response template and generation system, and you can define the response code, response header and response structure by yourself.

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

All interface responses of UtilMeta are inherited from `utilmeta.core.response.Response`. In this example, a certain template structure is specified for the response, and the return data of the API function is wrapped as a JSON object, in which `result_key` the specified key corresponds to the return result data. The error message corresponding to the `message_key` specified key is injected into the API class through the `response` attribute slot of the API class

So when we access `hello` the interface, we get
```json
{"data": "world", "msg": ""}
```

When you access a path that doesn’t exist, you can also see that the error message has been processed.
```json
{"data": null, "msg": "NotFound: not found"}
```

If you only want the response template application to interface with an API, you can directly declare it as the return type of the API function, such as
```python
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

### Template fields
A class that inherits Response can specify the following properties to adjust the response template

*  `name`: The name of the response template, which will be incorporated into the API documentation.
*  `description`: The description of the response template will be integrated into the API documentation.
*  `status`: The default response code of the response template

You can also specify the following template parameters to wrap the result of the API function as a JSON object as the response body

*  `result_key`: Key name of the corresponding returned result data
*  `message_key`: The key name of the corresponding error message
*  `count_key`: The key name of the corresponding total number of results, often used for paged queries.
* Key name of `state_key` business user-defined status code

There are also two special fields for which you can specify a type hint to generate the corresponding API response document

*  `result`: Specify the type and structure of the response result. If the response template is `result_key` defined, the result here refers to the data corresponding to the `result_key` key. Otherwise, it refers to the entire response body data.
*  `headers`: Specifies the structure of the response header, which needs to be a Schema class

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

### Response parameters

All response templates can be instantiated into response instances

*  `result`: The first parameter is the returned result data. If the response template is `result_key` defined, the result here refers to the data corresponding to the `result_key` key. Otherwise, it refers to the entire response body data.
*  `status`: Incoming response code
*  `headers`: The incoming response header should be a dictionary.
*  `cookies`: The dictionary of the incoming response Set-Cookie
*  `error`: a Python Exception object is passed in and processed as the corresponding response.
*  `state`: Incoming business status code, valid only when the template is specified `state_key`
*  `message`: Incoming message, valid only when the template is `message_key` specified
*  `count`: The number of results passed in, valid only when the template is `count_key` specified

Here is an example of constructing a response
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

We use MultiArticles Response to construct the corresponding response when the list interface returns, and the returned response body structure should be

```json
{
    "articles": [],
    "articlesCount": 0
}
```


!!! tip

## Hook mechanism

In the API class, you can also define a special function called ** Hook function ** hook function, which can act on one or more interfaces and sub-routes of the API class to perform operations such as custom verification, data preprocessing, response processing, and error processing. The types of hook functions in the API class are

* ** Pretreatment hook **: is called before the interface function is executed, using `@api.before` the definition
* ** Respond to processing hooks **: is called after the interface function is executed when the definition is used `@api.after`
* ** Error handling hook **: Used by `@api.handle` definition, called when an interface function or hook throws an error

###  `@api.before` pre-process hook
The preprocessing hook is executed before the target function is executed. It is mostly used for operations such as custom verification and data preprocessing. The preprocessing hook is defined by a `@api.before` decorator, such as

```python
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

 `@api.before` The decorator can pass in multiple API functions or API classes, and the hook function will be executed before the corresponding API function or API class is called, so you can write reusable logic before processing the request.

In this example, the `handle_article_slug` hook function we defined will be called before the get and post methods are executed, thus processing `slug` the path parameter to get the corresponding article object.

In addition, if you need hook functions to work on all interfaces within the API class, you can use the

!!! Tip “Async Functions”

###  `@api.after` post-process hooks
The response processing hook is executed after the target function is executed. Using `@api.after` the decorator definition, the hook function can receive the response body generated by the target interface function, process it and return it, such as
```python
from utilmeta.core import api

class RootAPI(api.API):
	user: UserAPI
	article: ArticleAPI

    @api.after('*')
    def add_timestamp(self, resp):
	    resp.headers['Server-Timestamp'] = int(self.request.time.timestamp() * 1000)
        return resp
```

The first parameter of the response processing hook function will pass in the response object returned by the interface, which is a Response instance. In this example, `add_timestamp` the hook will process the responses of all interfaces in the RootAPI and add `'Server-Timestamp'` fields to their response headers.

In addition, using the response processing hook, you can also generate responses for the interface in batches, and the return result of the response processing hook will replace the return result of the API function as the response, such as
```python
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

In this example, `get_article` `update_article` the interface requires the same request processing and result generation logic, so we define a preprocessing hook and a response processing hook to reuse the logic.

The preprocessing hook parses the `slug` path parameter query to get the article instance `self.article`, and the response processing hook serializes the article instance and returns it.

!!! tip

#### Rules for generating responses
In UtilMeta, there are three ways to declare a Response template

* Declared in the return prompt of the API interface function
```python
class RootAPI(api.API):
    def get(self) -> WrapResponse: pass
```
* Declared in the return prompt in the response processing hook
```python
class RootAPI(api.API):
    @api.after('*')
    def handle_response(self) -> WrapResponse: pass
```
* Declared in an attribute of the `response` API class
```python
class RootAPI(api.API):
    response = WrapResponse
```

If a function declares a Response response template, it will get the response of the corresponding template after calling. If an API class declares an `response` attribute, it will also get the response of the corresponding template after calling.

If the API interface function or API class does not have a corresponding response template declaration, the result data returned by the function will be returned all the way until the API class declaring `response` the attribute or the response processing hook declaring the return type is encountered.

When a Response instance is formed, the subsequent response template will not process it. That is to say, the generation of response follows the ** The nearest priority ** principle.

###  `@api.handle` Error handling hook
A variety of errors can occur in API functions, and sometimes you need to actively throw errors when a failure condition is detected. By default, UtilMeta catches all errors thrown by the API interface and returns a response based on the type of error and the message.

But in addition, you can also use the error handling hook `@api.handle` to customize the error handling logic. The parameters of the hook decorator are the target interface function or interface class, and the type of error to be handled. The way to use it is as follows
```python
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

In this example, we have declared two error handling hooks that specify different business status codes for different types of errors

*  `handle_user_auth`: Handle the errors and `exc.PermissionDenied` errors occurring `exc.Unauthorized` in the UserAPI, and specify them as the `State.AUTH_FAILED` business status code (input `state` parameters). The error message and the corresponding response code (incoming `error` parameters) are used.
*  `handle_not_found`: Process all `exc.Notfound` errors, specify them as the `State.NOT_FOUND` business status code, and continue to use the error information and the corresponding response code

The first parameter in the error handling hook passes an Error instance, which is a wrapper around a Python Exception to get the error information in it. The properties are

* Python Exception instance wrapped in `exception`:
* The type of an `type` error instance, such as ValueError, TypeError, etc., is a subclass of Exception
*  `traceback`: bad call stack string
*  `message`: a string containing the exception type, exception information, and exception call stack, similar to the format of Python’s automatic error message output.
*  `status`: Response code corresponding to the error by default. For example `exc.BadRequest`, the error corresponds to 400 by default, and `exc.Notfound` 404 by default.

#### Default error handling
The default error handling logic for UtilMeta is

* The error message will be processed in `message` the response construction parameter, and if the template is `message_key` declared, the corresponding error message will be processed.
* Obtain the corresponding response code `status` according to the type of error. If the corresponding type is not identified, a 500 response will be returned

Common error types in development include ** HTTP Standard Error ** `utilmeta.utils.exceptions` many HTTP standard errors defined in, which will be automatically identified with corresponding response codes. Common HTTP standard errors are as follows

*  `BadRequest`: Thrown when the request parameter verification fails. The default is to return a response of 400.
*  `Unauthorized`: Thrown when the authentication component detects that the request does not carry authentication credentials, and the default is to return a 401 response
*  `PermissionDenied`: Thrown when the requesting user does not meet the permissions required by the API interface. The default is to return a 403 response.
*  `Notfound`: Thrown when the requested path does not exist, and the 404 response is returned by default
* Thrown `MethodNotAllowed` when the requested method is not in the method supported by the request path. The default is to return a 405 response.

** Python standard error ** Some Python standard errors also recognize response codes.

*  `PermissionError`: Thrown when the system command and other operation permissions are insufficient, and the 403 response is returned by default.
*  `FileNotFoundError`: Thrown when the file path does not exist, and the 404 response is returned by default
*  `NotImplementedError`: The interface has not been implemented. The default is to return a 501 response.
*  `TimeoutError`: Thrown when the timeout condition of the interface is not met, the default is to return 503 response.

When writing API functions, you can follow the principle of short-circuit priority, handle the failure in the function logic as early as possible and throw errors. The errors you throw can be properly handled and the corresponding response can be generated without causing service problems. You can handle errors by defining error handling hooks in the upper layer. Or the top-level default error handling logic generates a response based on the type of error.


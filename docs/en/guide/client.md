# Declarative Web client

UtilMeta framework not only provides an API class for the development of server-side APIs, but also provides a similar class `Client` for the development of client-side request code for integrating with the API.

Like a declarative API, a `Client` class is a declarative client. It only needs to declare the request parameters and response template of the target API in the function, and the `Client` class will complete the construction of the API request and the parsing of the response automatically .

!!! tip
	In UtilMeta, `Client` is not only having an alike syntax as `API` class, but also using the same `Request` and `Response` class. Yep, this can reduce the mindset for developers a lot.
## Write a `Client` class

Writing `Client` is as the same way as [Writing API Class](../api-route), except that our class needs to inherit from the `utilmeta.core.cli.Client` class.

### Request function

We assume that we want to write `Client` classes for the following API:

```python
from utilmeta import UtilMeta
from utilmeta.core import api

class RootAPI(api.API):
	@api.get
	def plus(self, a: int, b: int) -> int:
		return a + b
```

We only need to write the request function for `Client` using the request parameter syntax, and leave the function body empty, as shown in
```python
from utilmeta.core import cli, api, response

class APIClient(cli.Client):
	class PlusResponse(response.Response):
		result: int
		
	@api.get
	def plus(self, a: int, b: int) -> PlusResponse: pass
```

So when we call it like this,
```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> resp = client.plus(a=1, b=2)
```

A request is built based on your function declaration
```
curl https://127.0.0.1:8000/api/plus?a=1&b=2
```

And `Client` will parse the response as an `PlusResponse` instance of the response template declared by your request function, and you can use `resp.result` to access the result that has been converted to an integer type.

!!! tip
	You can view all request parameter declaring methods in [Handle Request Document](../handle-request), the rule is same for `Client` class 

#### Specify the URL directly

The request function can use the function name as the path and combine it with the `base_url` of  `Client` class to form the request URL. You can also specify the target URL path directly in the `@api` decorator. The following is an example of Github API client code.

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

We specify the full URL path directly in the `@api` decorator, so that the `Client` class will ignore the `base_url` passed in when it is called and use the specified URL directly.

!!! tip "asynchronous request function"
	In the above example, we used async request functions, all you need is to add `async` to your function. but you should be noticed that async request function need an **async request library** to send a fully async request, currently UtilMeta support `httpx` and `aiohttp` as async request library, you can specify in the `backend` parameter of initializing `Client`
	```python
	>>> import httpx
	>>> client = GithubClient(backend=httpx)
	```

#### Declare response template

You can use UtilMeta’s response template to elegantly parse the response from the request function of a `Client` class. The response template should be declared at the **return type** of the function, and it needs to be declared as a response class that inherits from `Response`, or use `Union` to combine multiple response classes. For example, the following is an example of a login client class.

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

In the request function of `login` UserClient, we use `UserResponse` the return type hint as the function, declare the response status code of 200 in `UserResponse`, and `UserSchema` use it as the type hint of the result data. Indicates that this response only accepts responses with 200 status codes and parses the response data to the `UserSchema`

```python
>>> client = UserClient(base_url='<BASE_URL>')
>>> resp = client.login(username='alice', password='<PASSWORD>')
>>> resp.result
UserSchema(id=1, username='alice')
```

Properties commonly used in declarative response template classes are

* `status`: Specify a response status code, `Client` will only parse response into this template if the status code is identical to `status`.
* `result`: Declare the result data type of the response. If this property has a type declaration, the response will parse the result data according to this type.
* `headers`: Declare the response header type of the response. If this property is declared using a `Schema` class, the response will parse the response header according to this type.

If the response body is a JSON object and has a fixed schema, you can also use the following options to declare the corresponding schema keys

* `result_key`: The corresponding **Result Data** key in the response data object. If this attribute is specified, `response.result` will be the parsed data of `response.data[response.result_key]`
* `message_key`: The corresponding **Error message** key in the response object.
* `state_key`: The corresponding **Business Code** key in the response object
* `count_key`: The corresponding **Total Number of Query Result** key in the response object (for pagination)

!!! tip
	You can accessed the unparsed response body object be `response.data`, where `response.result` will be the parsed result data (If the response template does not declare `result_key`, the result data will be the parsed `response.data`)

#### Handle multiple responses with `Union` 

A common situation is that the API may return multiple kinds of responses, such as success, failure, insufficient permissions, etc. So we can use `Union` to combine multiple response templates, such as

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

We have modified the above user login client code, added the `UserResponseFailed` corresponding to the login failure status , and combined `UserResponse` in a `Union` as return type declaration of the login request function.

In this way, when the status code of the response is 200, it will be resolved to `UserResponse`, and when the status code is 403, it will be resolved to `UserResponseFailed`.

If the response template does not provide a status code, or multiple response templates provide the same status code, the `Client` class will parse according to the order which the response are declared in in the `Union[]`. If the parsing is successful, it will return. otherwise it will continue to parse the next template. If all the templates fail to parse the response, the corresponding error will be thrown. If you don’t want to throw an error when the parsing fails, you can add an `Response` element at the end of `Union[]`, such as

```python
class UserClient(cli.Client):
	@api.post
	def login(
		self, 
		username: str = request.BodyParam,
		password: str = request.BodyParam,
	) -> Union[UserResponse, UserResponseFailed, response.Response]: pass
```

The request function returns an `response.Response` instance when none of the previous templates can be parsed successfully

!!! tip "Return the response directly in the API function"
	The response class you get from the request function is identical to the response class in API class (both are `utilmeta.core.response.Response`), So you can directly return the response from `Client` class as the return value of API function

#### Handle Server-Sent Events (SSE)

Client can also handle streaming response like `Server-Sent Events`（SSE）, for example:

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

The `response.SSEResponse` used for the request function can be iterated as a generator or async generator, the iterated item is a `response.ServerSentEvent` object, contains the following fields:

* `event`: Event type, like `message` / `error`  / `close`
* `data`: Event Data
* `id`: Event ID（Optional）
* `retry`: Reconnect miliseconds when disconnected（Optional）

!!! tip
	`SSEResponse` has set `stream = True`, will be processed as streaming response by Client

If the event in SSE has a more specific data structure, you can define it and pass it in the same way as the example above. `SSEResponse` will parse event stream based on the `event` value, example of calling:

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

If you are using async request library like `httpx` / `aiohttp`, you should use `async for` to iterate the events

!!! note
	 requires UtilMeta >= 2.8

#### Custom Request Function

In the above examples, we use the declarative request parameter and response template, let the `Client` class automatically build the request and parse the response according to the declaration. Such a request function is called **Default request function**, the function body does not need anything, just a `pass`.

Of course, we can also write custom request sending and response processing logic in the function body. Such a request function is a **Custom request function**. The following is an example.

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

We add a `_admin` parameter in the login request function, when this parameter is True, the user-defined request logic will be used. Otherwise, when `Client` detects that the result returned by the request function is `None`, the request will be constructed according to declaration by default. Both kind of response they return is parsed by the response template of the request function.

!!! tip
	A custom parameter in the request function should start with a underscore `'_'`, then it will not be recognized as a request parameter. But of course, if you do not need `Client` to generate request by default and custom your request logic completely, you do not need a `@api` decorator, just define a regular function is enough

The `Client` class provides a built-in request function `request()` and a series of request functions named after HTTP methods. You can call them in custom request logic. Their function parameters are

* `method`: Only the `request()` function needs to be provided. Specify the HTTP method. Other functions named by HTTP method will use the corresponding HTTP method.
* `path`: Specifies the request path string. If the path is a complete URL, it will be used directly, otherwise it will be concatenated with the `base_url` of `Client` class.
* `query`: Specify the query parameters dict of the request, which will be parsed and spliced into the request URL together with the path.
* `data`: Specify the request body data, which can be dict, list, string or file. If the `Content-Type` request header isn't specified, it will be automatically generated according to the type of the request body data.
* `headers`: Specify the request headers, pass in a dict
* `cookies`: Specifies the Cookies of the request. It can be passed in a dict or a Cookie string. The specified Cookie will be integrated with the session Cookie held by the `Client` instance as the header `Cookie` of the request.
* `timeout`: Specifies the timeout for the request. By default, the `default_timeout` parameter of `Client` class will be used.

!!! tip "Asynchronous built-in request functions"
	For all built-in request function, `Client` class has provided the corresponding async version, just add a `async_` prefix before function name, like `async_request`, `async_get`

!!! warning
	 Do not name a request function as one of the above built-in functions. If you need to define a request function with the root path of the current `Client` class, just use  `@api.get("/")`
### Hook function

When writing of client code, we often need to process and fine-tune the request and response, so we can use the **hook function** to handle it conveniently. Three common hook functions have been defined in `Client` the class

```python
class Client:
	def process_request(self, request: Request):
        return request

    def process_response(self, response: Response):
        return response

    def handle_error(self, error: Error):
        raise error.throw()
```

If you need generic process for the request, response, or error handling of this `Client` class, you can extend these functions directly from the class and write your logic.

* `process_request`: process the request, you can adjust the parameters in the request. If the function returns an `Response` instance, the requesting function will not initiate the request and will use the response directly.
* `process_response`: Process the response. You can modify the response header or adjust the data. If this function returns an `Request` instance, the request function will re-initiate the request. (This feature can be used to retry or redirect the request.)
* `handle_error` To handle an error, you can log or take action based on the error. If this function returns an `Response` `Request` instance, the request function will use the response as the return. If this function returns an instance, Then the requesting function will make the request and will throw the error if it does not return or if it returns something else.

!!! note
	Generic hook function will on be effected on the default requet functions (using `pass` as function body), If you defined a custom request logic, it will not be processed by these functions, but you can still call `self.process_request` and `self.process_response` inside the function
	
#### Decorator hook function

Compared with the generic hook function, the hook function defined by using `@api` the decorator is more flexible in the selection of the target, and the decorator hook in the `Client` class is basically the same as the usage of [API Decorator Hooks](../api-route/#hook-mechanism) :

* `@api.before` Preprocessing hooks, which process requests before they are called
* `@api.after`: Response processing hook, which processes the response after the request function call
* `@api.handle`: Error handling hook to handle when an error is thrown by the request function call chain

The difference between the `@api.before` is that for the preprocessing hook, you need to use the first parameter to receive the request object generated by the `Client` class, and you can change the properties of this request object in the preprocessing hook.

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

In this example, we added a `add_authorization` preprocessing hook for the `get_user` request function of the `GithubClient` class. that adds the parameter of the `token` instance to the `Authorization` request header, The first parameter `req` of the preprocessing hook is used to receive the request object for processing.

It should be noted that the scope of the decorator hook function is different from that of the generic hook function. For the default request function, the processing order is as follows

1.  `@api.before` Hook function
2.  `process_request` Function
3. Initiate the request
4.  `process_response` Function
5.  `@api.after` Hook function

The errors thrown in steps 2, 3 and 4 can be handled by the `handle_error` generic hook function, and the errors thrown in all steps (1 ~ 5) will be handled by the `@api.handle` hook function

!!! tip "Async hook function"
	You can use the `asynchronous` keyword to define an asynchronous hook function (including generic hooks and decorator hooks). The usage of asynchronous hook functions is the same as synchronous hook functions, but you need to declare the request function as asynchronous as well, otherwise asynchronous hook functions cannot be called in synchronous request functions

### Mounting `Client`

Similar to the API class, the `Client` class also supports the definition of multi-level tree routing through mounting, which is convenient for large request SDK to organize code. The following is an example

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

In this example, we mount the `ArticlesClient` class on the `articles` path of `APIClient`, and `UserClient` on the `user` path, so that when we make the following call

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.articles.get_feed(limit=10)
```
We will actually access to `http://127.0.0.1:8000/api/articles/feed?limit=10`,  the mounted route will append to the `base_url` of  the `Client` class.

### Path parameters

When you need to define some routes name that can’t declared directly through the class attribute. We can also use the `@api.route` decorator to declare the route name, which can also contain path parameters, such as

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

The route mounted in `CommentClient` is `'articles/{slug}/comments'`, which contains a path parameter `slug`. In the request function of `CommentClient`, you need to declare the `slug` parameter as `request.PathParam` (path parameter). So when we call

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.comments.get_comment(id=1, slug='hello-world')
```

Will be accessed to  `http://127.0.0.1:8000/api/articles/hello-world/comments/1`

If the route of a `Client` class is certain, you can also declare it directly using the class decorator, such as
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

### Files and form

There are two ways to add a file for a request using a client class

* **Upload the file directly**: Use file directly as the request body, you can specify `utilmeta.core.file.File` as the request body type.
* **Upload files using form**: Use `multipart/form-data` forms to transfer files. You can pass in other form fields in addition to the file.

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

When passing in a file, you can pass a local file directly using `File`, such as

```python
client.multipart(data={
	'name': 'multipart',
	'files': [File(open('test.txt', 'r')), File(open('test.png', 'r'))] 
})
```

!!! tip
	You can also specify `filename` in the File class, it will used as the filename of the `multipart/form-data` form, if not specified, the original local file name will be used.

## Invoke `Client`

In the example above we have seen how to initialize a `Client` class for sending requests. Here are the complete parameters of the `Client` class.

* `base_url`: Specify a base URL, all the request function or mounted classes in the `Client` instance will be extended this URL (unless the corresponding request function has defined an absolute URL). This URL needs to be an absolute URL (the URL containing the request protocol and the hostname)
* `backend`: You can pass in the name string or reference of a request library, which will be the request library that initiates the request call for all the `Client` functions. The currently supported request libraries are `requests`, `aiohttp`, `httpx`, and `urllib`. by default will be `urllib`.

!!! warning "Asynchronous Request Library"
	If you are wring async request functions in `Client` class, please use async request library as `backend`, like `aiohttp` and `httpx`, or it will still be a sync request underlying.

* `service`: You can specify a **UtilMeta service** as the target service of the `Client` instance. If the specified `internal` parameter is True, the  constructed request by `Client`  will not initiate a network request. Instead, it invokes the UtilMeta service’s internal route and generates a response, otherwise the `Client` nstance’s `base_url` will be automatically assigned to the UtilMeta service’s `base_url`.
* `internal`: Used to control the request mode of the `Client` instance. The default is False. If True, the response is generated by internal invocation the specified `service`.

!!! note
	If `internal=True` and the `service` is not specified. `Client` will try to import the registered UtilMeta service in current process

* `mock`: Specify whether it is a **mock** client. If it is True, the request function of `Client` will not make an actual network request or internal call, but will directly generate a mock response according to the declared response template and return it. It can be used for client development before the API is developed.
* `append_slash`: Whether to add a slash `'/'` at the end of the request URL by default.
* `default_timeout`: Specifies the default timeout for the request function, which can be a `int` or `float` number of seconds, or a `timedelta` object
* `base_headers`: Use a dict to specify the default request header for the request function. The request header for each request will contain theres headers by default.
* `base_cookies`: Specifies the default Cookie for the requesting function, which can be a dict, a Cookie string, or a `SimpleCookie` object.
* `base_query`: Specify the default query parameters for the request function
* `proxies`: Specify the HTTP request proxy for the  `Client`  instance in the syntax of
```python
{'http': '<HTTP_PROXY_URL>', 'https': '<HTTPS_PROXY_URL>'}
```

* `allow_redirects`: Whether to allow the underlying request library to perform request redirection (3XX). The default is None, which follows the default configuration of the request library.
* `fail_silently`: If set to True, when the response of the request function cannot be parsed into the declared response template, an error is not thrown, but a generic `Response` instance is returned. The default is False.

!!! tip
	In order to make some of the request function **fail silently** in the `Client` class, you can add a default `Response` class in the return type declaration.
	```python
	class APIClient(Client):
		@api.get
		def my_request(self) -> Union[MyResponse, Response]: pass
	```
### Simple call

Of course, the `Client` UtilMeta class can also be used directly as a request class, and the usage is very simple.

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

### Cookies and Session

A common requirement for a client is to provide a Session mechanism like a browser, can save and remember **Cookies** set in response and send them in the following requests. The Client class has such a mechanism built in.

When the response to your request contains a `Set-Cookie` response header, the Client parses the cookies and stores them, then carries them in subsequent requests.

#### Isolate session using `with`

If you want the session state in the Client class to be kept in only a part of the code block, you can use `with` statements to organize and isolate these sessions. When the `with` statement exits, the session state in the client such as cookies, will be cleaned up.

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
	For async request library like `httpx` and `aiohttp`, use `async with`

In `with` / `async with`, Client will reuse the request session（`httpx.Client` / `aiohttp.Session` / `requests.Session`）. Performance for multiple requests for the same domain will be improved

!!! note
	UtilMeta >= 2.8  supports `async with`

## Generate `Client` code

### Generate UtilMeta service

You need only one command to generate the request Client code automatically for the UtilMeta service:
Execute the following command in your project directory (directory containing `meta.ini`).

```
meta gen_client
```

You can add a `--to` argument to specify the generated filename, by default it will generate a file named `client.py` in your current directory, containing the client code.

### Generate for OpenAPI documentation

You can specify the OpenAPI URL or file path as `--openapi` parameter using the `meta gen_client` command, and UtilMeta will generate the client request SDK code according to the corresponding OpenAPI document, like:

```
meta gen_client --openapi=https://petstore3.swagger.io/api/v3/openapi.json
```

## `Client` code example

### Realworld article API

We use [The Realworld Article API](https://realworld-docs.netlify.app/specifications/backend/endpoints/#get-article) as an example to write UtilMeta `Client` class code.

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

Calling the API:

```python
>>> client = APIClient(base_url='https://realworld.utilmeta.com/api')
>>> resp = client.get_article(slug='utilmeta-a-meta-backend-framework-for-python')
>>> resp
ArticleResponse [200 OK] "GET /api/articles/utilmeta-a-meta-backend-framework-for-python"
```


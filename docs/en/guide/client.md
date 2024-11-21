# Declarative Web client

The UtilMeta framework not only provides an API class for the development of server-side interfaces, but also provides a class similar `Client` to the API class syntax for the development of client-side request code for interfacing with the API interface

Like a declarative interface, `Client` a class is a declarative client. It only needs to declare the request parameters and response template of the target interface into the function, and `Client` the class will automatically complete the construction of the API request and the parsing of the response.

!!! tip

## Write a `Client` class

Classes are written `Client` in the same way as [编写 API 类](../api-route), except that our class needs to inherit from the `utilmeta.core.cli.Client` class.

### Request function

We assume that we want to write `Client` classes for the following API interfaces

```python
from utilmeta import UtilMeta
from utilmeta.core import api

class RootAPI(api.API):
	@api.get
	def plus(self, a: int, b: int) -> int:
		return a + b
```

We only need to write `Client` the request function according to the request parameter writing method of the API function, and leave the function body empty, as shown in
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

A request is built based on your function declaration, which is equivalent to
```
curl https://127.0.0.1:8000/api/plus?a=1&b=2
```

Parse the response as an `PlusResponse` instance of the response template declared by your request function, and you can `resp.result` access the result that has been converted to an integer type.

!!! tip

#### Specify the URL directly

The request function can use the function name as the path and combine it with `Client` the `base_url` class to form the request URL. You can also specify the target URL path directly in the `@api` decorator. The following is an example of Github interface client code.

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

We specify the full URL path directly in the `@api` decorator, so that `Client` the class will ignore the `base_url` passed in when it is called and use the specified URL directly for access.

!!! Tip “asynchronous request function”
	```python
	>>> import httpx
	>>> client = GithubClient(backend=httpx)
	```

#### Declare a response template

You can use UtilMeta’s response template to elegantly parse `Client` the response from the request function of a class. The response template should be declared in `Client` the request function ** Returns a value type hint ** of the class, and it needs to be declared as a response class that inherits from `Response`, or use `Union` multiple response classes combined. For example, the following is an example of `Client` a login interface class

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

*  `status`: You can specify a response code, which will be parsed to the response template only when the response code is the same as the response code.
*  `result`: Access the result data of the response. If this property has a type declaration, the response will parse the result data according to this type.
*  `headers`: Access the response header of the response. If this property is declared using a `Schema` class, the response will parse the response header according to this type.

If the response body is a JSON object and has a fixed schema, you can also use the following options to declare the corresponding schema key

*  `result_key`: The corresponding ** Result data ** key in the response object. If this attribute is specified, `response.result` the result data accessed by the attribute will be parsed.
*  `message_key`: The corresponding ** Error message ** key in the response object. If this property is specified, `response.message` the message string in the response body object will be accessed.
*  `state_key`: The corresponding ** Service Status Code ** key in the response object. If this attribute is specified, `response.state` the business status code in the response object will be accessed.
*  `count_key`: The corresponding ** Total number of query data ** key in the response object. If this attribute is specified, `response.count` the total number of query data in the response body object will be accessed.

!!! tip

#### Use to `Union` process multiple responses

A common situation is that the interface may return multiple responses, such as success, failure, insufficient permissions, etc. This situation is difficult to deal with in a response template. We can use `Union` to combine multiple response templates, such as

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

We have modified the above user login client code, added the response corresponding to the login failure status `UserResponseFailed`, and `UserResponse` combined `Union` it with the return type declaration of the login request function.

In this way, when the status code of the response is 200, it will be resolved to `UserResponse` `UserResponseFailed`, and when the status code is 403, it will be resolved to.

In addition to the parsing based on the status code, if the response template does not provide a status code or multiple response templates provide the same status code, `Client` the class will parse according to the order in `Union[]` which the response templates are declared in. If the parsing is successful, it will return. If the parsing fails, it will continue to parse the next template. If all the templates fail to parse the response, the corresponding error will be thrown. If you don’t want to throw an error when the parsing fails, you can add an `Response` element at the `Union[]` end of, such as

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

!!! Tip “Returns the response directly in the API function”

#### Custom Request Function

In the above examples, we all use the declarative request parameter declaration and response template declaration, and let the `Client` class automatically build the request and parse the response according to the declaration. Such a request function is called ** Default request function **, and its function body does not need anything, just need `pass` it.

Of course, we can also write custom request call logic and response processing logic in the function body. Such a request function is a custom request function. The following is an example.

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

We add a `_admin` parameter in the login request function. In the function logic, when this parameter is True, the user-defined request logic will be used. Otherwise, when `Client` the class detects that the result returned by the request function is null, the request will be constructed in the way of the default request function. Whether the request is custom or built by default, the response they return is parsed by the response template of the request function.

!!! tip

The `Client` class provides a built-in request function `request` and a series of request functions named after HTTP methods. You can call them in custom request logic. Their function parameters are

*  `method`: Only the `request` function needs to be provided. Specify the HTTP method. Other functions named by HTTP method will use the corresponding HTTP method.
*  `path`: Specifies the request path string. If the request path is a complete URL, it will be used directly, otherwise it will be concatenated with `Client` the `base_url` class.
*  `query`: Specify the query parameter dictionary of the request, which will be parsed and spliced into the request URL together with the path.
*  `data`: Specify the request body data, which can be dictionary, list, string or file. If the request header is specified `Content-Type`, it will be automatically generated according to the type of the request body data.
*  `headers`: Specify the request header data and pass in a dictionary
*  `cookies`: Specifies the Cookie data of the request. It can be passed in a dictionary or a Cookie string. The specified Cookie will be integrated with `Client` the Cookie held by the instance as the header of the request `Cookie`.
*  `timeout`: Specifies the timeout for the request. By default, the class `default_timeout` parameter will be used `Client`.

!!! Tip “Asynchronous built-in request functions”

!!! warning
 
### Hook function

In the writing of client code, we often need to process and fine-tune the request and response, and we can use the hook function to handle it conveniently. Three common hook functions have been defined in `Client` the class

```python
class Client:
	def process_request(self, request: Request):
        return request

    def process_response(self, response: Response):
        return response

    def handle_error(self, error: Error):
        raise error.throw()
```

If you need generic configuration for the request, response, or error handling of this `Client` class, you can extend these functions directly from the class and write your logic.

* To `process_request` process the request, you can adjust the parameters in the request. If the function returns an `Response` instance, the requesting function will not initiate the request and will use the response directly.
*  `process_response`: Process the response. You can modify the response header or adjust the data. If this function returns an `Request` instance, the request function will re-initiate the request. (This feature can be used to retry or redirect the request.)
*  `handle_error` To handle an error, you can log or take action based on the error. If this function returns an `Response` `Request` instance, the request function will use the response as the return. If this function returns an instance, Then the requesting function will make the request and will throw the error if it does not return or if it returns something else.

!!! note

#### Decorator hook function

Compared with the general hook function, the hook function defined by using `@api` the decorator is more flexible in the selection of the target, and `Client` the decorator hook in the class is basically the same as [API 的装饰器钩子](./api-route/#_10) the usage:

*  `@api.before` Preprocessing hooks, which process requests before they are called
*  `@api.after`: Response processing hook, which processes the response after the request function call
*  `@api.handle`: Error handling hook to handle when an error is thrown by the request function call chain

The difference is that for `@api.before` the preprocessing hook, you need to use the first parameter to receive `Client` the request object generated by the class, and you can change the properties of this request object in the preprocessing hook.

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

In this example, we added a preprocessing hook for `GithubClient` `get_user` the request function `add_authorization` that adds the parameter of the `token` instance to the `Authorizatio` request header, The first parameter `req` of the preprocessing hook is used to receive the request object for processing.

It should be noted that the scope of the decorator hook function is different from that of the general hook function in `Client` the class request function. For the default request function, the processing order is as follows

1.  `@api.before` Hook function
2.  `process_request` Function
3. Initiate the request
4.  `process_response` Function
5.  `@api.after` Hook function

The errors thrown in steps 2, 3 and 4 can be handled by the `handle_error` general hook function, and the errors thrown in all steps (1 ~ 5) will be handled by the `@api.handle` hook function

!!! Tip “Async hook function”

### The mounting of the `Client` class

Similar to the API class, `Client` the class also supports the definition of multi-level tree routing through mounting, which is convenient for large request SDK to organize code. The following is an example

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

In this example, we `ArticlesClient` mount the class on the `articles` `APIClient` path to, and `UserClient` we mount the class on the `user` path so that when we make the following call

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.articles.get_feed(limit=10)
```
We will actually access `http://127.0.0.1:8000/api/articles/feed?limit=10`, that is, the mounted `Client` class `base_url` will add the mounted route at the end.

### Mount the path parameters in the route

When you need to define some complex routes, you can’t declare them directly through the class attribute. We can also use `@api.route` the decorator to declare the route name, which can also contain path parameters, such as

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

The route mounted in `CommentClient` this example is `'articles/{slug}/comments'`, which contains a path parameter `slug`. In `CommentClient` the request function of, you need to declare the `slug` parameter as `request.PathParam` (path parameter). So when we call

```python
>>> client = APIClient(base_url='http://127.0.0.1:8000/api')
>>> client.comments.get_comment(id=1, slug='hello-world')
```
Will be accessed.

If the routing of a `Client` class is certain, you can also declare it directly using the class decorator, such as
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

### Client-side forms and films

There are two ways to add a file for a request using a client class

* To use a single file ** Upload the file directly ** directly as the request body, you can specify the `utilmeta.core.file.File` as the request body type directly.
* ** Upload a file using a form ** Use `multipart/form-data` Forms to transfer files. You can pass in other form fields in addition to the file.

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

When passing in a file, you can pass a local file directly using File, such as

```python
client.multipart(data={
	'name': 'multipart',
	'files': [File(open('test.txt', 'r')), File(open('test.png', 'r'))] 
})
```

!!! tip


## Invoke `Client`

In the example above we have seen how to instantiate `Client` a class for invocation. Here are the complete `Client` class instantiation parameters.

*  `base_url` Specify a base URL from which `Client` the request function in the instance and the URLs of other `Client` mounted instances will be extended (unless the corresponding request function has defined an absolute URL). This URL needs to be an absolute URL (the URL containing the request protocol and the source of the request)
*  `backend`: You can pass in the name string or reference of a request library, which will be the request library that initiates the request call by default as a `Client` class function. The currently supported request libraries are `requests`, `aiohttp`, `httpx`, and `urllib`, and will be used if not set

!!! Warning “Asynchronous Request Library”

*  `service`: You can specify a UtilMeta service as `Client` the target service of the instance. If the specified `internal` parameter is True, `Client` the constructed request will not initiate a network request. Instead, it invokes the UtilMeta service’s internal route and generates a response, otherwise `Client` the instance’s `base_url` is automatically assigned to the UtilMeta service’s
*  `internal`: Used to control `Client` the instance is request mode. The default is False. If True, the response is generated by internal invocation `service` of the specified service.

!!! note

*  `mock`: Specify whether it is a mock client. If it is True, `Client` the request function will not make an actual network request or internal call, but will directly generate a mock response according to the declared response template and return it. It can be used for client development before the interface is developed.
*  `append_slash`: Whether to add an underscore at the end of the request URL by default
*  `default_timeout` Specifies the default timeout for the request function, which can be a number of `int` seconds, `float` or `timedelta` an object
*  `base_headers`: Use a dictionary to specify the default request header for the request function. The request header for each request will contain the request headers in this dictionary by default.
*  `base_cookies` Specifies the default Cookie for the requesting function, which can be a dictionary, a Cookie string, or `SimpleCookie` an object.
*  `base_query`: Specify the default query parameters for the request function
*  `proxies`: Specifies `Client` the HTTP request proxy for the instance in the form
```python
{'http': '<HTTP_PROXY_URL>', 'https': '<HTTPS_PROXY_URL>'}
```

*  `allow_redirects`: Whether to allow the underlying request library to perform request redirection. The default is None, which follows the default configuration of the request library.
*  `fail_silently`: If set to True, when the response data of the request function cannot be parsed into the declared response template class, an error is not thrown, but a generic `Response` instance is returned. The default is False.

!!! tip
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

### Cookies session persistence

A common requirement for a client is to provide a Session mechanism that, like a browser, can save and remember Cookies set in response and send them in the request. The Client class has such a mechanism built in.

When the response to your request contains a `Set-Cookie` response header, the Client class parses the cookies and stores them, and the Client class carries them in subsequent requests.

#### Isolate a session with a `with` statement

If you want the session state in the Client class to be kept in only a part of the code block, you can use `with` statements to organize and isolate these sessions. When the `with` statement exits, the session state in the client, such as cookies, will be cleaned up.

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


## Generate `Client` class code

### Generate the request code for the UtilMeta service

The request SDK code to automatically generate the Client class for the UtilMeta service requires only one command to execute the entire command in your project directory (the containing `meta.ini` directory).

```
meta gen_client
```

### Generate request code for OpenAPI documentation

You can specify the OpenAPI URL or file address as a parameter when `--openapi` using `meta gen_client` the command, and UtilMeta will generate the client request SDK code according to the OpenAPI document corresponding to this address.

##  `Client` Class code example

### Realworld article interface

As [ The Realworld blog project’s interface for getting posts](https://realworld-docs.netlify.app/specifications/backend/endpoints/#get-article) an example, use the `Client` UtilMeta class to write the client request.

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

class ErrorResponse(response.Response):
	result_key = "errors"
	message_key = "msg"
	content_type = "application/json"

class APIClient(cli.Client):
    @api.get("/articles/{slug}", tags=["articles"])
    def get_article(
        self, slug: str = request.PathParam(regex="[a-z0-9]+(?:-[a-z0-9]+)*")
    ) -> Union[
        ArticleResponse[200],
        ErrorResponse
    ]:
        pass
```

Invoke

```python
>>> client = APIClient()
>>> resp = client.get_article(slug='how-to-train-your-dragon')
>>> resp
ArticleResponse [200 OK] "GET /api/articles/how-to-train-your-dragon"
```


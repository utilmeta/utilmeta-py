# Request Parameters

API requests can carry parameters in many ways, such as

* Path parameters
* Query parameters
* Request Body (JSON/Form/File, etc.)
* Request headers (including cookies)

We will show you how to handle the various parameters of the request in UtilMeta.

!!! tip
	Request parameters declaration in UtilMeta is based on Python type annotation (type hints) stardard with [utype](https://utype.io), if you are not familiar with Python type annotation, you can read [utype - Types in Python](https://utype.io/guide/type/) first

## Path parameters

It is a common way to pass data in the request URL path. For example, use `GET/article/3` to get the article data with ID 3, the parameter of ID is provided in the URL path. The way to declare the path parameter in UtilMeta is as follows
```python hl_lines="4"
from utilmeta.core import api

class RootAPI(api.API):
	@api.get('article/{id}')
	def get_article(self, id: int):
		return {"id": id}
```

The first parameter of the  `@api` decorator is path template string, as `'article/{id}'` in the example, use the same syntax as Python string template, and declare a parameter of the same name in the function to receive with the expected type and rules.

Defining multiple path parameters is similar in usage
```python hl_lines="6"
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
In this example, we declare two path parameters:

*  `lang`:  take values in `'en'` and `'zh'`
*  `page`:  is a parameter greater than or equal to 1 and defaults to 1
 
Parameters with default values are passed in directly if they are not provided in the path, so we get the following output when we request `GET/doc/en`.
```json
{"lang": "en", "page": 1}
```

!!! tip
	If the request path lacks the path params without default, a 404 Notfound will be responsed, such as `GET /doc`

If the request parameter does not meet the declared rules or cannot be converted to the corresponding type, you will get `400 BadRequest` an error response, such as

*  `GET/doc/fr/3`: `lang` parameter does not have a value in `'en'` and `'zh'`
*  `GET/doc/en/0`: `page` The parameter does not meet the rule of greater than or equal to one

!!! warning
	If you need to combine multiple path params, there must be chars to split them (like `'/'`), `'{category}{page}'` is an invalid path template because there are no split chars between the path params
### Path regex

Sometimes we need the path parameter to satisfy certain rules, and we can easily do this by declaring a regular expression, which is used as follows
```python hl_lines="5"
from utilmeta.core import api, request

class RootAPI(API):
    @api.get('item/{code}')
    def get_item(self, code: str = request.PathParam(regex='[a-z]{1,9}')):
        return code
```

Some common path regex are built in the UtilMeta `request` module.

* `request.PathParam`: default path argument rule, that is `'[^/]+'`, matches all characters except the underscore of the path
* `request.FilePathParam`:  Matches all strings `(.*)`, including the path underscore. Commonly used when the path parameter needs to pass the file path, URL path, etc.
* `request.SlugPathParam`:  Matches a slug string such as `how-to-guide` to be used in the URL

Here is an example.
```python hl_lines="5"
from utilmeta.core import api, request

class RootAPI(API):
    @api.get('file/{path}')
    def get_file(self, path: str = request.FilePathParam):
        return open(f'/tmp/{path}', 'r')
```

In this example, the `path` parameter gets `'path/to/README.md'` this path when we request `GET/file/path/to/README.md` it.

### Declare the request path

The examples above show how to use a template string to declare the request path, but this is not the only way.

In UtilMeta, the declaration rule of the API path is

* The path template string in `@api` the decorator as the request path.
* When there is no path string, the name of the function is used as the requested path
* When the name of a function is an HTTP method, its path is automatically set to `'/'` and cannot be overridden

!!! tip "API functions"
	`@api.<METHOD>` decorated method, or function with a HTTP-method-name (get/post/put/patch/delete) in the API classes is an API function, which provides HTTP access

The following examples cover the above cases and provide a clear illustration of the path declaration rule
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

!!! Tip “Path match priority”
	When both fixed path and variable path parameters are declared in API such as the above example, the fixed path API declaration needs to be placed above, so that UtilMeta will first match the `feed` function when matching `/article/feed` request, rather than matching it as a `slug` parameter to the `get_article` function 
## Query parameters

Using query parameters to pass in key-value pairs is a very common way to pass parameters, for example, by `GET/article?id=3` getting the article data with ID 3

The way to query the parameter declaration is very simple, which can be defined directly in the function, such as
```python
from utilmeta.utils import *

class RootAPI(API):
	@api.get
	def doc(self, 
	        lang: Literal['en', 'zh'], 
	        page: int = utype.Param(1, ge=1)):
		return {"lang": lang, "page": page}
```

We get output when we ask `GET/doc?lang=en`.
```json
{"lang": "en", "page": 1}
```

!!! tip
	Query parameter is the **default** param type in API functions, so if a parameter is not defined in the path template and not assigned any other param types, it will be processed as a query parameter 
### Parameter alias
If the parameter name cannot be represented as a Python variable (such as a syntax keyword or contains special symbols), you can use `utype.Param` the parameter of the `alias` component to specify the expected name of the field, such as
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

When you visit `GET/api/doc?class=tech&@page=3`, you will get  `{"tech": 3}`

### Use the Schema class

You can also define all query parameters as a Schema class for better combination and reuse. The usage is as follows
```python
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

In the example, we defined the query parameters `lang`  and `page` in `QuerySchema` and then injected them into the API function using `query: QuerySchema = request.Query`.

In this way, you can easily reuse query parameters between APIs using class inheritance and composition.

!!! warning
	Using Schema class as query params requires to specify `request.Query` as the default value, otherwise this param will be treated as a single param in the query

## Request body

Request body data is often used to pass data such as JSON, forms, or files in POST/PUT/PATCH methods

In UtilMeta, you can use the Schema class to declare request body data in JSON or form format, using
```python
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
We declare a `LoginSchema` as a type annotation for the `data` param, and use `request.Body` as a default value  to mark the parameter as a request body parameter.

When you use a Schema class to declare the request body, the API has the ability to handle JSOM/XML and form data, for example, you can pass such a JSON request body.
```json
{
	"username": "alice",
	"password": "123abc",
	"remember": true
}
```

You can also use the request body in `application/x-www-form-urlencode`  similar in syntax to query parameters, such as
```
username=alice&password=123abc&remember=true
```

If you need to constrain `Content-Type` of the request body, you can use more request body class provided by `request`, such as 

*  `request.Json`: request body Content-Type needs to be
*  `request.Form`: request body Content-Type needs to be or

!!! tip
	You can also use the `content_type` in the `request.Body`, such as `request.Body(content_type='application/json')`

### List data
Scenarios like batch creation and update need to upload the request body data of list type, and the declaration method is to add `List[]` outside the corresponding Schema class, such as
```python hl_lines="10"
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

Client needs to pass a list of JSON ( `application/json`) type in the request body. such as
```json
[{
	"username": "alice",
	"password": "123abc"
}, {
	"username": "bob",
	"password": "XYZ789"
}]
```

!!! tip
	 If the client only passes a single JSON object or form, it will be automatically converted to a list with only this element.

### File uploads

If you need to support file upload, you just need to declare the file param's type as a file. The usage is as follows
```python hl_lines="7"
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

Several common file types are provided in the `utilmeta.core.file` that you can use to declare file parameters.

*  `File`: Receive files of any type
*  `Image`: Receive picture files ( `image/*`)
*  `Audio`: Receive audio files ( `audio/*`)
*  `Video`: Receive video files ( `video/*`)

In addition, you can use the `max_length` parameter to limit the size of the file. In the example, we only accept `avatar` file below 10 M.

!!! tip
	For forms with files, client need to pass request body with `multipart/form-data`  content type

If you need to support uploading multiple files, just add the type declaration `List[]` for the file parameter, as shown in
```python hl_lines="8"
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

#### Upload the file only
If you want the client to use the entire binary file directly as the request body, instead of using in the form, you only need to specify the file parameter as `request.Body`, such as

```python hl_lines="6"
from utilmeta.core import api, request, file
import utype

class FileAPI(api.API):
    @api.post
    def image(self, image: file.Image = request.Body) -> str:
	    name = str(int(self.request.time.timestamp() * 1000)) + '.png'
        image.save(path='/data/image', name=name)
```

### Body parameter

In addition to supporting the declaration of a complete request body Schema, you can also use `request.BodyParam` a separate declaration of fields in the request body.
```python hl_lines="5-6"
from utilmeta.core import api, request, file

class FileAPI(api.API):
	@api.post
	def upload(self, name: str = request.BodyParam,
	           file: file.File = request.BodyParam):
	    file.save(path='/data/files', name=name)
```

### Strings and other types of data
If you want API to accept a request body in the form of a string, you only need to specify the corresponding type and `content_type` of the request body param, such as
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
In this function, we use `html` to specify and receive `'text/html'` request body, and limit the maximum length of the upload text to 10000.

## Request headers

API requests usually carry request headers (HTTP Headers) to pass the meta-information of the request, such as credentials, cache negotiation , session cookies, etc. In addition to the default request headers, you can also customize the request headers in the following classes

*  `request.HeaderParam`: Declare a single request header parameter
*  `request.Headers`: Declare the complete request header Schema

```python hl_lines="10"
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

In practice, customized header usually begins with `X-` and uses hyphens `-` to connect words. We use `alias` to specify the name of the header. For example, the request headers declared in the example is

*  `auth_token`: Target request header name is `X-Auth-Token`,  a string of length 12
*  `meta`: Target request header is `X-Meta-Data`, an object that can be resolved to a dictionary.

!!! tip
	Request headers is **case-insensitive**, so `alias='X-Auth-Token'` is same as  `alias='x-auth-token'`

When we request
```http
POST /api/operation HTTP/1.1

X-Auth-Token: OZ3tPOl6
X-Meta-Data: {"version":1.2}
```
You’ll get `["OZ3tPOl6", {"version": 1.2}]` a response.

!!! note
	Before sending a request with a custom request header, browser will also send an `OPTIONS` request to check if the custom request header is within the range allowed by the `Access-Control-Allow-Headers` in the response. However, there is no need to worry, UtilMeta will automatically place your declared request headers in the `OPTIONS` response

### General parameters

A common case is that a header needs to be reused among multiple APIs, such as authentication credentials. In this case, the API class of UtilMeta provides a concise way: declare common parameters in the API class property. The usage is as follows
```python hl_lines="5"
from utilmeta.core import api, request
import utype

class RootAPI(api.API):
    auth_token: str = request.HeaderParam(alias='X-Auth-Token')
	
    @api.post
	def operation(self):
		return self.auth_token
```

In this way, all APIs defined in the API class need to provide `X-Auth-Token` header and you can also get the corresponding value through `self.auth_token`.

### Parse cookies

The cookie field of the request header can carry a series of key parameters to maintain a session with the server or carry credential information. There are two ways to declare the cookie parameter

*  `request.CookieParam`: Declare a single Cookie parameter
*  `request.Cookies`: Declare a complete Cookie object

```python
from utilmeta.core import api, request

class RootAPI(api.API):
    sessionid: str = request.CookieParam(required=True)
    csrftoken: str = request.CookieParam(default=None)

    @api.post
    def operation(self):
        return [self.sessionid, self.csrftoken]
```

In this example, we declare two generic cookie parameters in the RootAPI class, and the request passes the cookie parameters as follows
```http
POST /api/operation HTTP/1.1

Cookie: csrftoken=xxxx; sessionid=xxxx;
```

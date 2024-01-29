# Request Authentication

Most API services has the concept of “**user**” or “**permission**” are inseparable from the authentication of the request,which obtain the permission of the request or the user according to the request information. UtilMeta has a built-in simple authentication mechanism to quickly implement the authentication functions. This document will introduce the relevant usage.

## User authentication
User authentication is the most common authentication requirement, that identifies user instance of current request. In the [User Login & RESTful API](../../tutorials/user-auth) tutorial, there is a step-by-step method to implement the simplest user authentication API. In this part, we will explain the usages and mechanism in detail.
### User model
Before implementing user authentication, we must establish the “user”, which is often a user table in a database, so we must first develop the user model corresponding to the user table, taking the Django model as an example

```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)
```

This is a simple user model in which the fields of username, password, and registration time are defined.

!!! tip "PasswordField"
	You can use UtilMeta's `PasswordField` as the password field of user, which will encrypt the input password

### Authentication parameters

The user authentication is configured by instantiating a `utilmeta.core.auth.User` component, such as

```python
from utilmeta.core import auth
from .models import User

user_config = auth.User(
    User,
    authentication=...,
    login_fields=User.username,
    password_field=User.password,
)
```

The parameters supported in the `auth.User` component are

* `user_model`: the first parameter is the user model, such as the `User` class in the example.
* `authentication`: pass in an authentication method, such as Session, JWT configuration, etc., which we will introduce later.

**User field configuration**

* `field`:  the field that identifies the user. The default is the primary key ID.
* `login_fields`:  the fields used for login. all should be unique, such as username, email etc.
* `password_field`:  password field
* `login_time_field`:  a field that records the time of the most recent login, which can be automatically updated after the user login
* `login_ip_field`:   a field that records the most recently logged in IP, which can be automatically updated after the user login

**User authentication mechanism**

Whether Session or JWT, the mechanism of user authentication is to insert a key-value pair identifying the current requesting user's ID into their stored data, and then read it from the data when parsing the request. You can use the `key` parameter of `auth.User` to specify the key name that identifies the user. The default is `'_user_id'`.

### Use in API

After configured the user authentication, you can use it in the API function to receive the user object of the current request, such as

```python hl_lines="7"
from utilmeta.core import api, auth
from .models import User

user_config = auth.User(...)

class UserAPI(api.API):
    def get(self, user: User = user_config) -> UserSchema:
        return UserSchema.init(user)
```

You only need to set the user authentication configuration as the default value of the user parameter, and you can use this parameter to receive the user object identified by the current request.

Of course, such  declaration also means that the request **must** has a logged-in user, otherwise the authentication component of UtilMeta will automatically reject the request and return a `401 Unauthorized` response indicating that the request does not provide authentication information

If you want to declare **optional** user authentication, you can use `Optional` the declaration parameter type, such as

```python hl_lines="8"
from utilmeta.core import api, auth
from .models import User
from typing import Optional

user_config = auth.User(...)

class UserAPI(api.API):
    def get(self, user: Optional[User] = user_config) -> Optional[UserSchema]:
	    if not user:
	        return None
        return UserSchema.init(user)
```

So that if the user is not logged in, the API will returns `null`, and if the user is logged in, the user object serialized using UserSchema is returned
#### Login user

If you specify `login_fields` and `password_field` in the `auth.User` configuration, you can quickly implement the login logic using the `login` function it provides, such as

=== "Async API"
	```python hl_lines="20"
	import utype
	from utilmeta.utils import exceptions
	from utilmeta.core import api, auth, request
	from .models import User
	
	class LoginSchema(utype.Schema):
	    username: str
	    password: str
	
	user_config = auth.User(
	    User,
	    authentication=...,
	    login_fields=User.username,
	    password_field=User.password,
	)
	
	class UserAPI(api.API):
	    @api.post
	    async def login(self, data: LoginSchema = request.Body):
	        user = await user_config.alogin(
	            request=self.request,
	            ident=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return await UserSchema.ainit(user)
	```
=== "Sync API"
	```python hl_lines="20"
	import utype
	from utilmeta.utils import exceptions
	from utilmeta.core import api, auth, request
	from .models import User
	
	class LoginSchema(utype.Schema):
	    username: str
	    password: str
	
	user_config = auth.User(
	    User,
	    authentication=...,
	    login_fields=User.username,
	    password_field=User.password,
	)
	
	class UserAPI(api.API):
	    @api.post
	    def login(self, data: LoginSchema = request.Body):
	        user = user_config.login(
	            request=self.request,
	            ident=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return UserSchema.init(user)
	```

The login function `login` (and its async variant `alogin`) receives the following parameters

* `request`:  receives the current request object, thus `self.request`
* `ident`:  receives the user identifier used to log in, such as username, email, etc. which depend on the `login_fields` configured in `auth.User`
* `password`:  receive the unencrypted user’s password

The login function will find the matching user record for `ident`  from your user table, and compare the encrypted password entered by the user with the password in the user record. If the user exists and the password is consistent, it will log in the matching user object to the current request and return, otherwise it will return None. So if you detect the result of the t `login` function is None, you can return the response of “user name or password error”.

!!! tip
	For login API, it is not recommended to return detailed and specific information when a login request fails, such as "username does not exist" or "password error", as this can provide useful information to attackers who use brute force to crack passwords

**`login_user`: login user directly**

Sometimes you just need to login a user object to current request, such as signup, or using a third-party OAuth login, you can use the `login_user` function (or its async variant `alogin_user`) to directly log in the user, such as

=== "Async API"
	```python hl_lines="12"
	from utilmeta.core import api, auth, request
	from .models import User
	
	user_config = auth.User(...)
	
	class UserAPI(api.API):
	    @api.post
	    async def signup(self, data: LoginSchema = request.Body):
	        if await User.objects.filter(username=data.username).aexists():
	            raise exceptions.BadRequest('Username exists')
	        await data.asave()
	        await user_config.alogin_user(
	            request=self.request,
	            user=data.get_instance()
	        )
	        return await UserSchema.ainit(data.pk)
	```
=== "Sync API"
	```python hl_lines="12"
	from utilmeta.core import api, auth, request
	from .models import User
	
	user_config = auth.User(...)
	
	class UserAPI(api.API):
	    @api.post
	    def signup(self, data: LoginSchema = request.Body):
	        if User.objects.filter(username=data.username).exists():
	            raise exceptions.BadRequest('Username exists')
	        data.save()
	        user_config.login_user(
	            request=self.request,
	            user=data.get_instance()
	        )
	        return UserSchema.init(data.pk)
	```

!!! note
	The direct login just store the user ID into your authentication data store, such as Session data or JWT data.

#### Logout user

How the user logs out depends on the authentication method used

* If you use Session for authentication, logout is actually using `session.flush()` to clear the current Session data, which will be described below.
* If you use JWT for authentication, there is no concept of “server-side logout”, and the client can discard the token to implement user logout without API participation.

## Session authentication

Server-side Session is a common way to maintain user session and authentication. Usually, a data object is stored in the cache / file / database of the server according to the Cookie value of the request, and you can update the data in the API function.

UtilMeta provides the following Session configurations depending on the storage strategy

* **Cache**: Use a cache (such as redis) as storage
```python
from utilmeta.core.auth.session.cache import CacheSession
```

* **Database**: Use a database as storage
```python
from utilmeta.core.auth.session.db import DBSession
```

* **Cache + database (fallback)**:  Stored in the cache and the database at the same time. When querying, the cache is queried first. and returned directly if hits. When it misses or failed to access, the corresponding record in the database is queried.
```python
from utilmeta.core.auth.session.cached_db import CachedDBSession
```

* File: Upcoming support

### Configure the Session

After selecting the store, you can configure Session parameters by instantiation. The following is an example of using `CachedDBSession` the configuration

```python
from utilmeta.core import auth
from utilmeta.core.auth.session.cached_db import CachedDBSession
from utilmeta.conf.http import Cookoe
from .models import Session

session_config = CachedDBSession(
	session_model=Session,
	cache_alias='default',
	cookie=Cookie(
		http_only=True,
		secure=True,
		age=3600 * 24 * 30,
	),
	save_every_request=False,
	expire_at_browser_close=False,
)

user_config = auth.User(
	authentication=session_config
)
```

Parameters in the Session configuration are

* `session_model`:  if the storage uses a database ( `db`/ `cached_db`), you need to pass in a model corresponding to the Session table, whose fields we’ll introduce later.
* `cache_alias`:  if the store uses a cache ( `cache`/ `cached_db`), you need to pass in the name of a cache connection, which we’ll look at configuring later
* `cookie`:  configure cookie for Session
* `save_every_request`:  whether to store after each request
* `expire_at_browser_close`:  whether to expire when the user’s browser is closed

#### Use of Session in API

The use of Session depends on the setting and passing of Cookie, so you need to inject the plugin of Session config into the API, so that the Session configuration will automatically process the response and add the `Set-Cookie` response header. The usage method is as follows

```python hl_lines="4"
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(api.API):
    pass
```

Simply use `@session_config.plugin` to decorate an API class and the Session will be applied to all endpoints and routes in it, so if you need to enable sessions for all APIs in the service, you can inject them directly into the  **root API**.

!!! tip
	UtilMeta use plugin instead of global settings to bring extra features (such as Session), so you can specify different configuration for different APIs

So how to get the session data of the current request? Similar to the use of getting the current user, it can be declared directly in the function parameter, e.g.

```python hl_lines="7"
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(API):
    @api.get
    def user_id(self, session: session_config.schema = session_config):
        return session.get('_user_id')
```

You can use `session_config.schema` to get the type annotation corresponding to the session configuration, and use the session configuration as the default value of the parameter.

In the function you will get a Session data object, which is used like a `dict` and has some Session properties and methods.

**Session properties**

* `session_key`:  get the identitier key of the Session
* `expiry_age`: get the expiration time of Session, which is set by Cookie's `age` by default.
* `modified`:  returns whether the Session data has been modified in the current request

**Session methods**

* `flush()`:  clear all Session data and delete the record, thus revoking the corresponding `sessionid` immediately. It can be used for **user logout**
* `cycle_key()`:  replace the current Session data with a new identitier key (while leave the data unchanged)

These methods also have corresponding asynchronous methods, which only need to be prepend an `a` before the name, such as  `aflush()`, `acycle_key()`.

!!! tip
	Session config can passed to  `authentication` param of `auth.User` for user authentication, but it is not the single purpose, you can also only use Session in the API function like the above example

#### Configure cache connections

UtilMeta uses a cache connection configuration similar to Django syntax. Here is an example of configuring a redis cache
```python
from utilmeta import UtilMeta
from config.env import env

def configure(service: UtilMeta):
    from utilmeta.core.cache import CacheConnections
    from utilmeta.core.cache.backends.redis import RedisCache
    service.use(CacheConnections({
        'default': RedisCache(
            port=env.REDIS_PORT,
            db=env.REDIS_DB,
            password=env.REDIS_PASSWORD
        )
    }))
```

You can pass in `host`,  `port`, `db`, `password` parameter to define the redis connection, the name of the connection is the key `'default'`, You can pass it into the `cache_alias` parameter of Session configuration, and the Session will use this cache to store data.

#### Configure cookie

You can use `utilmeta.conf.http.Cookie` to configure Cookie behavior in a Session. The supported parameters are

* `name`: the name of the session Cookie, which is `'sessionid'` by default.
* `age`: specifies the expiration time of the Cookie, in seconds.
* `domain`: specifies the domain name of the Cookie. for example `utilmeta.com`, then the cookie will only affect `utilmeta.com` and subdomains like `ops.utilmeta.com`.
* `path`: specifies the path that the Cookie acts on (location path of browser), for example, when set to `/docs`, cookie will only acts on the `/docs` and `/docs/(.*)`

* `secure`: if set to True, cookies are sent only in secure HTTPS connections
* `http_only`: if set to True, the cookie will not be accessed or modified by the client’s JavaScript and will only be passed in the HTTP request. For the session cookie, it is recommended to set to **True** for security.
* `same_site`: specifies if/when cookies are sent by cross-site request. There are three possible values: `'Strict'`, `'Lax'` and `'None'`.

!!! tip
	These parameters all corresponding the the property of Cookie, the specific usage of Cookie can be found in [MDN - HTTP Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies), the configured cookie will be merged in `Set-Cookie` response header like
	```
	Set-Cookie:
	sessionid=xxx; expires=Thu, 25 Jan 2024 10:04:34 GMT; HttpOnly; Max-Age=604800; Path=/; SameSite=Lax
	```

### Session Model

For Session using database storage, such as `DBSession` or `CachedDBSession`, you need to specify a Session model to interact with the database. UtilMeta already provides a Session base class for you to inherit. It contains the following basic fields

```python
class AbstractSession(AwaitableModel):
    session_key = models.CharField(max_length=60, unique=True)
    encoded_data = models.TextField(null=True)
    
    created_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=None, null=True)
    expiry_time = models.DateTimeField(default=None, null=True)
    deleted_time = models.DateTimeField(default=None, null=True)

    class Meta:
        abstract = True
```

* `session_key`: stores the identifier key of the session, which is carried in the Cookie
* `encoded_data`: store encoded session data
* `created_time`: creation time of session
* `last_activity`:  most recent usage time of session
* `expiry_time`: expiration time of session
* `deleted_time`: deletion time of session. The default is None, when the session is deleted, this field will be set as the deletion time. It will not be queried later, but can be used for data retention.

After inheriting the Session base class, you can extend the fields in it, such as the request IP, the user ID, etc., for example

```python
from utilmeta.core.orm.backends.django.models import AbstractSession

class Session(AbstractSession):
    user = models.ForeignKey(
        User, on_delete=amodels.ACASCADE, 
        related_name='sessions', 
        default=None, null=True
    )
    ip = models.GenericIPAddressField(default=None, null=True)

    class Meta:
        db_table = 'session'
```

When you extend the Session fields, you need to pass in the extra data when storing the Session. You can use the following method
```python hl_lines="15"
from utilmeta.core.auth.session.cached_db import CachedDBSession, CachedDBSessionSchema
from .models import Session

class SessionSchema(CachedDBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(
            user_id=self.get('_user_id'),
            ip=str(self.request.ip_address),
        )
        return data

session_config = CachedDBSession(
	session_model=Session,
	engine=SessionSchema,
	# ...
)
```

For all XX Session configurations, there is a corresponding **XXSessionSchema** that implements the corresponding storage engine, and you can add custom field data by inheriting `get_session_data`. For example, in the example, we demonstrated how to add the fields of "**current request user ID**" and "**current request IP**". In this method, you can use `self.request` to get the request object at runtime.

### Declare Session data

If your Session data has a definite field names and types, you can declare them in the Session schema to use the prompt ability of IDE to facilitate development and avoid dirty data in the Session. The following is an example of an API that uses Session declaration data to verify email verification code

```python hl_lines="7-10"
import utype
import random
from typing import Optional
from utilmeta.core import api, request
from .auth import session_config

class EmailSessionSchema(session_config.schema):
    email: Optional[str] = utype.Field(default=None, defer_default=True)
    code: Optional[str] = utype.Field(default=None, defer_default=True)
    verified: bool = utype.Field(default=False, defer_default=True)

class EmailAPI(api.API):
    @api.post
    def send_code(self, session: EmailSessionSchema, email: str = request.BodyParam):
        session.email = email
        session.code = str(random.randint(1000, 9999))
        # send mail
        session.expiry = self.request.time + timedelta(seconds=300)
        
    @api.post
    def verify_code(self, session: EmailSessionSchema,
                    email: str = request.BodyParam,
                    code: str = request.BodyParam):
        if session.email == email and session.code == code:
            session.verified = True
            session.expiry = None
            return True
        return False
```

There is an `schema` attribute in the session configuration that can get its corresponding Schema class. We can customize the session data by inherit `session_config.schema`, such as the `EmailSessionSchema` in the example.

we have defined the `email`, `code` and `verified` fields in it, which can be directly accessed and assigned in the API function. In the example, these fields are used to implement the sending and verification functions of the email verification code.

In addition, `SessionSchema` has a built-in property `expiry` that you can assign to adjust the expiration time of a Session, which can accept `datetime` or a timestamp and string that can convert to `datetime`. In the `send_code` API, we set the Session expiration time to 300 seconds after the request time, so the session will expire after 5 minutes, and client needs to resend the verification code if not verified yet.

You can make the Session not expire by setting `expiry`  to None. In the `verify_code` endpoint, when the code is successful verified, we set `expiry`  to None so that the state of successful verification can be maintained. But in fact, whether the Session expires also depends on the Cookie `age`. When the Cookie expires, the client will discard the corresponding Cookie key-value pair, so that subsequent requests cannot access the corresponding Session data.

!!! tip
	The Schema class of Session also inherits from `utype.Schema`, so its usage is similiar to [utype - Schema class](https://utype.io/guide/cls/)


**Tutorial reference**

In the [User Login & RESTful API](../../tutorials/user-auth) tutorial, you can view the process of using Session authentication to implement the simplest user authentication APIs.

## JWT Authentication

Json Web Token (JWT) is also a commonly used authentication method, which implements authentication through a token that encrypts the data containing the user identifier, and is generally carried in the request header of the request `Authorization`, such as

```
Authorization: Bearer JWT_TOKEN_VALUE
```

JWT authentication is configured as follow

```python hl_lines="8-11"
from .env import env
from utilmeta.core import auth
from utilmeta.core.auth import jwt
from domain.user.models import User

user_config = auth.User(
	User,
	authentication=jwt.JsonWebToken(
		secret_key=env.JWT_SECRET_KEY,
		user_token_field=User.token
	),
)
```

We use `utilmeta.core.auth.jwt.JsonWebToken` to configure JWT authentication. The supported parameters are

* `secret_key`:  required. pass in a JWT key for data encryption and decryption. This key is very important and should be carefully managed. Technically, if it is leaked, the client can construct a request with any permission.
* `algorithm`:  JWT encryption algorithm, default is  `'HS256'`
* `audience`:  audience string of JWT. If specified, it will be written into the `'aud'` field of JWT and verified during decryption. If does not consistent with the `audience`, it will return a 403 response.
* `user_token_field`:  you can specify a field in the user model that will be updated to the user whenever a new JWT token is generated for the user.

!!! tip
	Reasonably specifying `audience` can prevent JWT from using APIs that do not belong to its permission scope.

**Tutorial reference**

In the [The Realworld Blog Project](../../tutorials/realworld-blog) tutorial, you can view the process of using JWT authentication to implement the API of the blog application.

## Other authentication methods

Authentication methods to be supported

* HTTP Basic Auth
* Signature Auth
* OAuth2

### Custom authentication method

If you are not satisfied with the standard authentication method provided by UtilMeta, you can also define the authentication method by yourself. The usage is as follows

=== "Async API"
	```python
	from utilmeta.core.auth.base import BaseAuthentication
	from utilmeta.core.request import Request
	
	class CustomAuth(BaseAuthentication):
	    async def getter(self, request: Request):
	        pass
	```
=== "Sync API"
	```python
	from utilmeta.core.auth.base import BaseAuthentication
	from utilmeta.core.request import Request
	
	class CustomAuth(BaseAuthentication):
	    def getter(self, request: Request):
	        pass
	```


The `getter` function only needs to receive the current request as a parameter, and then return the value of the current user ID, where you can implement your own authentication logic.

Then instantiate your custom authentication class and pass it to the `authentication` parameter in `auth.User`.

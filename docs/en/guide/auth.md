# Request Authentication

Most API services with the concept of “user” or “permission” are inseparable from the authentication of the interface and the user, that is, to obtain the permission of the request or the user according to the information of the request. UtilMeta has a built-in simple authentication mechanism to facilitate developers to quickly implement the authentication function. This document will introduce the relevant usage.

## User authentication
User authentication is the most common authentication requirement, that is, to identify the request to a user instance. In the [用户注册登录 API](../../tutorials/user-auth) tutorial, there is a step-by-step method to implement the simplest user authentication interface. In this part, we will explain the usage and principle in detail.
### User model
Before implementing user authentication, we must first have the concept of “user”, which is often a user table in a database, so we must first develop the user model corresponding to the user table, taking the Django model as an example

```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)
```

This is a simple user model in which the fields of username, password, and registration time are defined.

!!! tip “PasswordField”

### Authentication parameters

With the user model, we can configure the authentication parameters. The user authentication configuration is completed by instantiating a `utilmeta.core.auth.User` component, such as

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

*  `user_model` The first parameter is the user model, such as the defined User class in the example.
*  `authentication`: Pass in an authentication method, such as Session, JWT configuration, etc., which we will introduce later.

** User field configuration **

*  `field`: The field that identifies the user. The default is the primary key ID.
*  `login_fields`: The fields used for login should be unique for each user, such as user name, mailbox, etc.
*  `password_field`: Password field
*  `login_time_field`: a field that records the time of the most recent login, which can be automatically updated after the user logs in
*  `login_ip_field`: Automatic recording of the most recently logged in IP, which can be automatically updated after the user logs in

Principle ** of ** user authentication

Whether Session or JWT, the principle of user authentication is to insert a key-value pair identifying the current requesting user ID into their stored data, and then read it from the data when parsing the request. You can use `auth.User` the `key` parameter to specify the key name that identifies the user. The default is.

### Use in API

After you have configured the user authentication, you can use it in the API function to receive the user object for the current request, such as

```python hl_lines="7"
from utilmeta.core import api, auth
from .models import User

user_config = auth.User(...)

class UserAPI(api.API):
    def get(self, user: User = user_config) -> UserSchema:
        return UserSchema.init(user)
```

You only need to set the user authentication configuration as the default value of the user parameter, and you can use this parameter to receive the user object identified by the current request.

Of course, such a user parameter declaration also means that the request ** Must ** can identify a logged-in user, otherwise the authentication component of UtilMeta will automatically reject the request and return a `401 Unauthorized` response indicating that the request does not provide authentication information

If you want to declare optional user authentication, you can use `Optional` the declaration parameter type, such as

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

This way, if the user is not logged in, the interface returns `null`, and if the user is logged in, the user object serialized using UserSchema is returned
#### Login user

If you specify `login_fields` and `password_field` in the `auth.User` configuration, you can quickly implement the login logic using the `login` functions it provides, such as


= = = “Async API”
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
	            token=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return await UserSchema.ainit(user)
	```
= = = “Sync API”
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
	            token=data.username,
	            password=data.password
	        )
	        if not user:
	            raise exceptions.PermissionDenied('Username of password wrong')
	        return UserSchema.init(user)
	```

The login function `login` (async method `alogin`) receives the following parameters

*  `request`: receives the current request object, i.e.
*  `token`: Receives the user ID used to log in, such as username, mailbox, etc. The login fields depend on `auth.User` the `login_fields` parameters configured in.
*  `password`: Receive the user’s password (unencrypted)

The login function will find `token` the matching user record from your user table, and compare the password (encrypted) entered by the user with the password in the user record. If the user exists and the password comparison passes, it will log in the matching user object to the current request and return, otherwise it will return None. So if you detect `login` that the result of the function is None, you can return the response of “user name or password error”.

!!! tip

** `login_user`: Direct login user **

Sometimes you just need to log a user object into an existing request, such as when registering, or when using a third-party OAuth login, then you can use `auth.User` the `login_user` configured function (asynchronous method `alogin_user`) to directly log in the user, such as

= = = “Async API”
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
= = = “Sync API”
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

#### Logout user

How the user logs out depends on the authentication method used

* If you use Session for authentication, logout is actually using `session.flush()` the method to clear the current Session data, which will be described below.
* If you use JWT for authentication, there is no concept of “server-side logout”, and the client can discard the token to implement user logout without API participation.

## Session authentication

Server-side Session is a common user session maintenance and authentication method. Usually, a data object is stored in the cache/file/database of the server according to the Cookie value of the request. You can update the data in the API function according to the actual business needs. This is the principle of Session.

UtilMeta provides the following Session configurations depending on the storage strategy of the Session

* **Cache**: Use a cache (such as redis) as storage for Session
```python
from utilmeta.core.auth.session.cache import CacheSession
```

* **Database**: Use a relational database as storage for Sessions
```python
from utilmeta.core.auth.session.db import DBSession
```

* **Cache + database (fallback)**: It is stored in the cache and the database at the same time. When querying, the cache is queried first. When it hits, it is returned directly. When it misses or the cache cannot be accessed, the corresponding record in the database is queried.
```python
from utilmeta.core.auth.session.cached_db import CachedDBSession
```

* File: Upcoming Support

### Configure the Session

After selecting which stored Session configuration to use, you can configure Session parameters by instantiation. The following is an example of using `CachedDBSession` the configuration

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

*  `session_model`: If the storage uses a database ( `db`/ `cached_db`), you need to pass in a model corresponding to the Session table, whose fields we’ll cover later.
*  `cache_alias`: If the store uses a cache ( `cache`/ `cached_db`), you need to pass in the name of a cache connection, which we’ll look at configuring later
*  `cookie`: Configure cookies for Session
*  `save_every_request`: Whether to store after each request
*  `expire_at_browser_close`: Whether to expire when the user’s browser is closed

#### Use of Session in API

Because the use of Session depends on the setting and passing of Cookie, you need to inject the plug-in of Session setting into the API, so that the Session configuration will automatically process the response and add the `Set-Cookie` correct response header. The usage method is as follows

```python
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(api.API):
    pass
```

Simply use `@session_config.plugin` the decorator in an API class and the Session will be applied to all interfaces defined and mounted in it, so if you need to enable sessions for all APIs in the service, you can inject them directly into the ** Root API **.

!!! tip

So how to get the session data corresponding to the request in the interface? Similar to the use of getting the current user, it can be declared directly in the function parameter, e.g.

```python
from utilmeta.core import api
from config.auth import session_config

@session_config.plugin
class RootAPI(API):
    @api.get
    def user_id(self, session: session_config.schema = session_config):
        return session.get('_user_id')
```

You can use to `session_config.schema` get the data type corresponding to the session configuration as the type annotation of the session parameter, and use the session configuration as the default value of the parameter.

In the function you will get a Session data object, which is used like `dict` a dictionary and has some Session properties and methods.

** Session property **

*  `session_key`: Get the identity ID of the Session
*  `expiry_age`: Obtain the expiration time of Session, which is Cookie by default.
*  `modified`: Returns whether the Session data has been modified in the current request

** Session method **

*  `flush()`: Clear all Session data and delete the record, that is, the corresponding `sessionid` one will be invalid immediately. It can be used for
*  `cycle_key()`: Replace the current Session data with a new identity ID (leave the data unchanged)

These methods also have corresponding asynchronous methods, which only need to be added `a` before the name, such as,


!!! tip

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

You can pass in `host` the, `port`, `db`, `password` parameter to define the redis connection, which is `'default'` named, You can pass it into the parameters of the `cache_alias` Session configuration, and the Session will use this cache to store data.

#### Configure cookie

You can use `utilmeta.conf.http.Cookie` components to configure Cookie behavior in a Session. The supported parameters are

*  `name`: The name of the Cookie, which is defaulted to in Session authentication
*  `age`: Specifies the expiration time of the Cookie, in seconds.
*  `domain` Specifies the domain name of the Cookie. If a domain name is specified, for example `utilmeta.com`, then the cookie will only affect utilmeta. Com and subdomains like `ops.utilmeta.com` this.
*  `path`: Specifies the path that the Cookie acts on (the path displayed by the client). For example, when set to `/docs`, only acts on the

*  `secure`: If set to True, cookies are sent only on HTTPS connections
*  `http_only`: If set to True, the cookie will not be accessed or modified by the client’s JavaScript and will only be passed in the HTTP request. For the session cookie, it is recommended to set to True for security.
*  `same_site`: Specifies if/when cookies are sent by cross-site request. There are three possible values: `Strict`, and.

!!! tip
	
	```
	Set-Cookie:
	sessionid=xxx; expires=Thu, 25 Jan 2024 10:04:34 GMT; HttpOnly; Max-Age=604800; Path=/; SameSite=Lax
	```
### Session Model

For Session authentication using database storage, such as `DBSession` or `CachedDBSession`, you need to specify a Session model to complete the interaction with the database. UtilMeta already provides a Session base class for you to inherit. It contains the following basic fields

```python
class AbstractSession(AwaitableModel):
    session_key = models.CharField(max_length=60, unique=True)
    encoded_data = models.TextField(null=True)
    
    created_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=None, null=True)
    expiry_time = models.DateTimeField(default=None, null=True)
    deleted_time = models.DateTimeField(default=None, null=True)    # already expired

    class Meta:
        abstract = True
```

*  `session_key`: Stores the access ID of the session, which is carried in the Cookie
*  `encoded_data`: Store encoded Session data
*  `created_time`: Creation time of the Session
*  `last_activity`: Session’s most recent usage time
*  `expiry_time`: Expiration time of Session
*  `deleted_time`: The deletion time of the Session. The default is None. When the Session is deleted, this field will be set as the deletion time. It will not be queried later, but it can be used for data retention.

After inheriting the Session base class, you can extend the fields in it, such as the IP of the session, the user ID, etc., for example

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

When you extend the Session data, of course, you need to pass in the data for the field you added when storing the Session. You can use the following method
```python hl_lines="15"
from utilmeta.core.auth.session.cached_db import CachedDBSession, CachedDBSessionSchema
from .models import Session

class SessionSchema(CachedDBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(
            user_id=self.get('_user_id'),
            ip=str(self._request.ip_address),
        )
        return data

session_config = CachedDBSession(
	session_model=Session,
	engine=SessionSchema,
	...
)
```

For all XX Session configurations, there is a corresponding XX Session Schema that implements the corresponding storage engine, and you can add custom field data by inheriting `get_session_data` it. For example, in the example, we demonstrated how to add the fields of [current request user ID] and [current request IP]. In this method, you can use `self._request` to get the request object at runtime.

After inheriting from the Session Schema class, remember to pass the new class to the `engine` Session configuration parameter

### Declare Session data

If your server-side Session data has a definite field name and type, you can declare them out, so that you can use the IDE property prompt to facilitate development and avoid dirty data in the Session. The following is an example of an interface that uses Session declaration data to verify an Email verification code

```python
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

There is an `schema` attribute in the session configuration that can access its corresponding Schema class. We can customize the session data through inheritance `session_config.schema`, such as the Email Session Schema in the example.

Among them, we have defined the `email` `code` `verified` field, which can be directly accessed and assigned in the API function. In the example, these fields are used to realize the sending and verification functions of the mailbox verification code.

In addition, SessionSchema has a `expiry` built-in property that you can assign to adjust the expiration time of a Session, which can accept `datetime` or convert to `datetime` a timestamp and string of type. In the `send_code` interface, we set the Session expiration time after sending the mail to 300 seconds after the request time, that is, the session will expire after 5 minutes, and the request needs to resend the verification code.

You can make the Session not expire by `expiry` setting to None. In the `verify_code` interface, when the verification code is successful, we `expiry` set to None so that the state of successful verification can be maintained. But in fact, whether the Session expires also depends on the `age` Cookie. When the Cookie expires, the client will discard the corresponding Cookie key-value pair, so that subsequent requests cannot access the corresponding Session data.

!!! tip

** Tutorial reference **

In [User Login & RESTful API](../../tutorials/user-auth) tutorial, you can refer to the process of using Session authentication to implement the simplest user authentication interface

## JWT Authentication

The Json Web Token (JWT) technology is also a commonly used authentication method, which implements authentication through a token that encrypts the data containing the user identifier with a key, and is generally carried in the request header of the request `Authorization`, such as

```
Authorization: Bearer JWT_TOKEN_VALUE
```

JWT authentication is configured as follow

```python
from .env import env
from utilmeta.core import auth
from utilmeta.core.auth import jwt
from domain.user.models import User

user_config = auth.User(
	User,
	authentication=jwt.JsonWebToken(
		key=env.JWT_SECRET_KEY,
		user_token_field=User.token
	),
)
```

We use `utilmeta.core.auth.jwt.JsonWebToken` to configure JWT authentication. The supported parameters are

*  `key`: Required. A JWT key is passed in for data encryption and decryption. This key is very important and should be carefully managed. In theory, if it is leaked, the client can construct a request for any permission.
*  `algorithm`: JWT encryption algorithm, default is
*  `audience`: The audience string of JWT. If specified, it will be written into the `'aud'` field of JWT and verified during decryption. If `audience` it does not meet the requirements of JWT, it will return a 403 response.
*  `user_token_field` You can specify a field in the user model that will be updated to the user whenever a new JWT is generated for the user.

!!! tip


** Tutorial reference **

In the [ The Realworld Blog Project ](../../tutorials/realworld-blog) tutorial, you can refer to the process of using JWT authentication to implement the API of the blog application.

## Other authentication methods

Authentication methods to be supported

* HTTP Basic Auth
* Signature Auth
* OAuth2

### Custom authentication method

If you are not satisfied with the standard authentication method provided by UtilMeta, you can also define the authentication method by yourself. The usage is as follows

```python
from utilmeta.core.auth.base import BaseAuthentication
from utilmeta.core.request import Request

class CustomAuth(BaseAuthentication):
    def getter(self, request: Request):
        pass
```

The `getter` function only needs to receive the current request object as a parameter, and then return the value of the current user ID, where you can implement your own authentication logic.

Then instantiate your custom authentication class `CustomAuth` and pass it `auth.User` in the `authentication` parameters.

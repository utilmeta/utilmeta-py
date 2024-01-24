# User Login & RESTful API

In this case, we will use UtilMeta to build an API to provide user registration, login, query and update information (RESTful API), which are required by most applications. We will also learn how to use UtilMeta to handle database queries and authentication.

!!! abstract "Tech Stack"

	* Using Django as an HTTP and ORM backend
	* Use SQLite as the database
	* Use Session to handle the user’s login status

## 1. Create project

We use the `meta setup` command to create a new project.
```shell
meta setup demo-user
```
Enter `django` when prompted to select backend

After the project is created, we need to configure the database connection of the service, open it `server.py`, and insert the following code

```python
service = UtilMeta(...)

# new +++++
from utilmeta.core.server.backends.django import DjangoSettings
from utilmeta.core.orm import DatabaseConnections, Database

service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
))

service.use(DatabaseConnections({
    'default': Database(
        name='db',
        engine='sqlite3',
    )
}))
```

In the inserted code, we declare the configuration information of Django and the configuration of the database connection. Because Django uses the app (application) to manage the data model, we use the following command to create an app named `user`

```shell
meta add user
```

You can see that a new folder named `user` has been created in our project folder, which includes
```
/user
    /migrations
    api.py
    models.py
    schema.py
```

The `migrations` folder is where Django handles the database migrations of the models

Once the app is created, we insert a line into the  Django settings of  `server.py` to specify the app.

```python hl_lines="3"
service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
    apps=['user']
))
```

So far, we have completed the configuration and initialization of the project.

## 2. Write user model

The user’s login registration API, of course, revolves around the “user”. Before developing the API, we first write the user’s data model. We open `user/models.py` and write
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import AbstractSession, PasswordField

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = PasswordField(max_length=100)
    signup_time = models.DateTimeField(auto_now_add=True)

class Session(AbstractSession):
    user = models.ForeignKey(
        User, related_name='sessions', 
        null=True, default=None, 
        on_delete=models.CASCADE
    )
```

It can be seen that in addition to the `User` model, we have also written a `Session` model for users to record user sessions and login status. We will implement user login and authentication through this model.

!!! tip "PasswordField"
	the `password` field of User model is using `PasswordField` to auto-encrypt the input password (with pbkdf2)
### Connect database

After we write the data model, we can use the migration command provided by Django to easily create the corresponding data table. Since we use SQLite, we do not need to install the database software in advance. We only need to run the following two commands to complete the creation of the database.

```shell
meta makemigrations
meta migrate
```

When you see the following output, you have finished creating the database

```
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying user.0001_initial... OK
```

The database migration command created a SQLite database named `db` in the project folder according to the database configuration in `server.py` , where the table of User and Session models have been created

## 3. Session and Authentication

After writing the user models, we can start to develop the authentication logic. We create a  new file named `auth.py` in the user folder and write the configuration of session and user authentication.
```python
from utilmeta.core import auth
from utilmeta.core.auth.session.db import DBSessionSchema, DBSession
from .models import Session, User

USER_ID = '_user_id'

class SessionSchema(DBSessionSchema):
    def get_session_data(self):
        data = super().get_session_data()
        data.update(user_id=self.get(USER_ID))
        return data

session_config = DBSession(
    session_model=Session,
    engine=SessionSchema,
    cookie=DBSession.Cookie(
        name='sessionid',
        age=7 * 24 * 3600,
        http_only=True
    )
)

user_config = auth.User(
    user_model=User,
    authentication=session_config,
    key=USER_ID,
    login_fields=User.username,
    password_field=User.password,
)
```

In this code, `SessionSchema` is the core engine that processes and stores Session data, `session_config`  declares the Session configuration with Session model and engine we just wrote, and configures the corresponding Cookie policy

!!! tip
	We use session store based on database to simply our tutorial, in practive, we often use cache+db as the store, you can find more in [Session Authentication](../../guide/auth#session)

We also declare the user authentication configuration `user_config` with the following params

* `user_model` Specify the user model for authentication, which is the User model I wrote in the previous section.
* `authentication`: Specify the authentication method. We pass `session_config` in to declare that user authentication is performed using Session.
* `key`: Specify the key of the current user ID in the session data
* `login_fields`: Fields that can be used for login, such as username, email, etc., which need to be unique.
* `password_field`: The user’s password field. Declaring these allows UtilMeta to automatically handle the login verification logic for you.

## 4. Write user API

### Signup API

First, we will write the user signup API. It should receive the user name and password fields, complete the signup  after verifying that the user name is not occupied, and return the newly registered user data.

We open the `user/api.py` and write

```python
from datetime import datetime
from utilmeta.core import api, orm
from utilmeta.utils import exceptions
from .models import User
from . import auth

class SignupSchema(orm.Schema[User]):
    username: str
    password: str
    
class UserSchema(orm.Schema[User]):
    id: int
    username: str
    signup_time: datetime

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self, data: SignupSchema = request.Body) -> UserSchema:
        if User.objects.filter(username=data.username).exists():
            raise exceptions.BadRequest('Username exists')
        data.save()
        auth.user_config.login_user(
            request=self.request,
            user=data.get_instance()
        )
        return UserSchema.init(data.pk)
```
The logic in the signup API function is

1. Detect whether the in `username` the request has been registered
2. Call `data.save()` method to save the signup data
3. Login the registered user to the current request using `login_user`
4. Returns after initializing the new user’s data to a UserSchema instance using `UserSchema.init(data.pk)`

!!! abstract "Declarative ORM"
	UtilMeta has developed an efficient declarative ORM mechanism, also known as Scheme Query. We use `orm.Schema[User]` to define a Schema class with the User model injected, so that we can use the methods of the schema class to create, update, and serialize data. You can find more in [Data Query and ORM Document](../../guide/schema-query)

We can also find that a decorator named `@auth.session_config.plugin` is plug-in to the UserAPI class. This is the where the Session configuration is applied to the API. This plugin can save the Session data after each request and patch the response with corresponding `Set-Cookie` header

### Login & Logout API

Next, we'll write the user’s login and logout APIs

```python
from datetime import datetime
from utilmeta.core import api, orm, request
from utilmeta.utils import exceptions
from .models import User
from . import auth
import utype

class LoginSchema(utype.Schema):
    username: str
    password: str

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self): ...

    # new ++++
    @api.post
    def login(self, data: LoginSchema = request.Body) -> UserSchema:
        user = auth.user_config.login(
            request=self.request,
            ident=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('Username of password wrong')
        return UserSchema.init(user)

    @api.post
    def logout(self, session: auth.SessionSchema = auth.session_config):
        session.flush()
```

In The login API, we call the `login()` method in our authentication configuration to complete the login simply. Since we have configured the login field and password field, the UtilMeta can help us complete the password verification and login automatically. If the login is successful, the corresponding user instance is returned. So we can throw an error if the `login()` result is None, and after a successful login, we can call `UserSchema.init` to return the login user data to the client.

!!! tip
	The use of `login()` method is not mandatory, you can write your custom login logc if you need

For the logout API, we just need to get the current session and use `session.flush()` to empty the session data.

!!! tip
	After session configured, you can get the session of the request like the example in the `logout` function, you will get a `SessionSchema` instance, and can use it like a dict or other Schema instance
### Get & Update user data

When we understand the usage of declarative ORM, it is very simple to write the get & update API of User

```python
from datetime import datetime
from utilmeta.core import api, orm, request
from utilmeta.utils import exceptions
from .models import User
from . import auth
import utype

class UserUpdateSchema(orm.Schema[User]):
    id: int = orm.Field(no_input=True)
    username: str = orm.Field(required=False)
    password: str = orm.Field(required=False)

@auth.session_config.plugin
class UserAPI(api.API):
    @api.post
    def signup(self): ...
    @api.post
    def login(self): ...
    @api.post
    def logout(self): ...

    # new ++++
    def get(self, user: User = auth.user_config) -> UserSchema:
        return UserSchema.init(user)

    def put(self, data: UserUpdateSchema = request.Body, 
            user: User = auth.user_config) -> UserSchema:
        data.id = user.pk
        data.save()
        return UserSchema.init(data.pk)
```

After we declare the user authentication configuration, we can declare `user: User = auth.user_config` in the API function parameters to get the instance of the current request user in any API that requires user login. If the request is not logged in, UtilMeta will automatically process and return `401 Unauthorized`

In the `get` API, we directly serialize the current request user using `UserSchema` and return it to the client
In the `put` API, we assign the current request user's ID to the `id` field of `UserUpdateSchema`, and return the updated user data after saving.

Since we can’t allow the requesting user to arbitrarily specify the user ID to be updated, we use the `no_input=True` option for `id` field, which is actually a common practice, that is a user can only update his own information.

!!! tip "Core Methods"
	If your API function using the name of HTTP methods (such as get/put/patch/post/delete), it will bind the method and mount the same route of the API class, these methods are called **core methods** of the API class

At this point, our API is all developed.
### Mount API

In order to provide access to our developed UserAPI, we need to mount it on the root API of the service. Let’s go back to `server.py` and modify the declaration of the RootAPI.
```python hl_lines="6"
# new +++
service.setup()
from user.api import UserAPI

class RootAPI(api.API):
    user: UserAPI
	
service.mount(RootAPI, route='/api')
```

We mount the developed UserAPI to the RootAPI's `user` property, which means that the UserAPI path is mounted to `/api/user`

!!! tip
	You should call `service.setup()` before import any Django models

## 5. Run the API

Run the API service using the following command in the project folder
```
meta run
```

Or you can use.
```shell
python server.py
```

When you see the following output, the service has started successfully

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

!!! tip
	You can alter the `host` and `port` params of UtilMeta service in `server.py`  to change the address of the API service

## Source Code

the source code of this tutorial can be found at [github](https://github.com/utilmeta/utilmeta-py/tree/main/examples/user_auth)
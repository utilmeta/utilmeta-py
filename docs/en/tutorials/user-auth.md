# User Login & RESTful API

In this case, we will use UtilMeta to build an API to provide user registration, login, query and modify information, which is the standard of most applications. We will also learn how to use UtilMeta to handle database query and authentication.

!!! abstract "Tech Stack"

	* Using Django as an HTTP and ORM backend
	* Use SQLite as the database
	* Use Session to handle the user’s login status

## 1. Create project

We use the `meta setup` command to create a new project.
```shell
meta setup demo-user
```
Enter when prompted to select backend

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

You can see that a `user` new folder has been created in our project folder, which includes
```
/user
    /migrations
    api.py
    models.py
    schema.py
```

The `migrations` folder where Django handles the `models.py` database migration file is where we write the data model.

Once the app is created, we `server.py`’ll insert a line into the Django settings to specify the app.

```python
service.use(DjangoSettings(
    secret_key='YOUR_SECRET_KEY',
    apps=['user']     # new
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

It can be seen that in addition to the User model, we have also written a Session model for users to record user sessions and login status. We will implement user login and authentication through this model.

!!! tip “PasswordField”

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

The database migration command creates a `db` SQLite database named in the project folder according to `server.py` the database configuration in, in which the User and Session models have been tabulated

## 3. Session and Authentication

After writing the model related to user authentication, we can start to develop the logic related to authentication. We create a `auth.py` new file in the user folder and write the configuration of Session and user authentication.
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

In this code, SessionSchema is the core engine that processes and stores Session data, `session_config` is the component that declares the Session configuration, defines the Session model and engine we just wrote, and configures the corresponding Cookie policy

!!! tip


In addition, we also declare the `user_config` user authentication configuration in the code, in which the parameters

*  `user_model` Specify the user model for authentication, which is the User model I wrote in the previous section.
*  `authentication`: Specify the authentication policy. We pass `session_config` in to declare that user authentication is performed using Session.
*  `key`: Saves the name of the current user ID in the Session data
*  `login_fields`: Fields that can be used for login, such as user ID, mailbox, etc., need to be unique.
*  `password_field`: The user’s password field. Declaring these allows UtilMeta to automatically handle the login verification logic for you.

## 4. Write user API

### Signup API

First, we will write the user registration interface. The registration interface should receive the user name and password fields, complete the registration after verifying that the user name is not occupied, and return the newly registered user data.

We open the `user/api.py` write registration interface.

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
The logic in the registration interface I

1. Detect whether the in `username` the request has been registered
2. Call `data.save()` method to save data
3. Log in as a newly registered user using `login_user` the method for the current request
4. Returns after initializing the new user’s data to a UserSchema instance using `UserSchema.init(data.pk)`

!!! abstract “Schema Query”

In addition, we find that this decorator plug-in is applied `@auth.session_config.plugin` to the UserAPI class. This is the way the Session configuration is applied to the API. This plug-in can save and process the Session data updated by the request after each request.

### Login & Logout API

Next, we write the user’s login and logout interfaces.

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
            token=data.username,
            password=data.password
        )
        if not user:
            raise exceptions.PermissionDenied('Username of password wrong')
        return UserSchema.init(user)

    @api.post
    def logout(self, session: auth.SessionSchema = auth.session_config):
        session.flush()
```

In The login interface, we directly call the method in the `login()` authentication configuration to complete the login. Since we have configured the login field and password field, the UtilMeta field can help us complete the password verification and login. If the login is successful, the corresponding user instance is returned. We throw an error to return a login failure, and after a successful login, we call `UserSchema.init` to return the login user data to the client.

!!! tip

For the logout interface, we just need to get the current session and empty the data in it. What we call here is to `session.flush()` empty the data.

!!! tip

### Get & Update user data

When we understand the usage of Schema Query, it is very simple to write the interface for obtaining and updating user information, as follows
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

After we declare the user authentication configuration, we can declare `user: User = auth.user_config` in the interface parameters to get the instance of the current requesting user in any interface that requires the user to log in. If the request is not logged in, UtilMeta will automatically process and return

In the `get` interface, we directly initialize the data `UserSchema` of the current requesting user and return it to the client `put`. We will receive the field of `id` the UserUpdateSchema instance to assign the ID of the current user, and then return the updated user data after saving.

Since we can’t allow the requesting user to arbitrarily specify the user ID to be updated, we use the `no_input=True` option for the field requesting data `id`, which is actually a common permission policy, that is, a user can only update his own information.

!!! Naming and Routing of tip “API Functions

At this point, our API is all developed.
### Mount API

In order for the User API we developed to provide access, we need to mount it on the root API of the service. Let’s go back `server.py` and modify the declaration of the Root API.
```python
# new +++
service.setup()
from user.api import UserAPI

class RootAPI(api.API):
    user: UserAPI    # new
	
service.mount(RootAPI, route='/api')
```

We mount the developed UserAPI to the RootAPI `user` property, which means that the UserAPI path is mounted to

!!! tip

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

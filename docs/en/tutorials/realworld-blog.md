# Realworld Blog Project

This tutorial will takes you through the implementation of a classic blog project API using UtilMeta, with the following features

* User signup, login, get, update info, follow, unfollow
* Article creation, modification, likes, list comments, create and delete comments

Don’t worry, the UtilMeta code that does all of the above is less than 600 lines. Here’s a step-by-step guide on how to do it, starting with the creation of your project

!!! tip
	We will implement the APIs based on [Realworld API Docs](https://realworld-docs.netlify.app/specifications/backend/endpoints), The code of this tutorial is in [this Github repo](https://github.com/utilmeta/utilmeta-py-realworld-example-app)
## 1. Create project

### Install dependencies

Before creating the project, install the dependent libraries required for this tutorial
```shell
pip install utilmeta starlette django databases[aiosqlite]
```

!!! abstract "Tech Stack"
	* Develop asynchronous API using `starlette` as the HTTP backend
	* Using `Django` as a data models
	* Use `SQLite` as the database
	* User authentication using `JWT`

### setup command

Create a new UtilMeta project using the following command

```shell
meta setup utilmeta-realworld-blog --temp=full
```

Then follow the prompts or skip, and enter `starlette` when prompted to select backend

```
Choose the http backend of your project 
 - django (default)
 - flask
 - fastapi
 - starlette
 - sanic
 - tornado
>>> starlette
```

!!! tip "--temp=full"
	The blog project contains various APIs and models, to organize them in a better way, we use `--temp=full` in our setup command to create a full template project

We can see that the project structure created by this command is as follows
```
/config
	conf.py
	env.py
	service.py
/domain
/service
	api.py
main.py
meta.ini
```

The recommended corresponding usage are:

* `config`: Store configuration files, environment variables, service running parameters, etc.
* `domain`: Store domain applications (django apps), models, and RESTful APIs.
* `service`: Integrate internal APIs and external services
* `main.py`: The entry file to run, which can be used `python main.py` to run the service directly during debugging.
* `meta.ini`: Declare metadata, and determines the root directory of the project for `meta` command

## 2. Write the data model

For an API system like blog, which focuses on the data CRUD, we often start to develop from the data models. In the [API Specs](https://realworld-docs.netlify.app/specifications/backend/endpoints), we can conclude that we need to write user, article, comment and other models.

### Create an application

Since we use Django as the ORM implementation, we organize our project the way Django organizes apps, and we can simply divide the blog project into two domain applications: **user** and **article**.

First add a user application named `user` to the project using the following command
```shell
meta add user
```
After running the command, you can see that a new folder has been created under the folder `domain`, with the following structure

``` hl_lines="2"
/domain
	/user
		/migrations
		api.py
		models.py
		schema.py
```

The user models for the blog and the related APIs for user and authentication will be placed in this folder

!!! tip
	It's ok if you are not familiar with Django apps usage, you can understand it as a organize approach to split code for different domains,

Let’s add an article app called `article`. which will place article and comment models and APIs.
```shell
meta add article
```

### User model

We will write the data model as described for the user data structure in [API Documentation: User](https://realworld-docs.netlify.app/specifications/backend/api-response-format#users-for-authentication) . We open `domain/user/models.py` and write the user’s model.
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField, AwaitableModel

class User(AwaitableModel):
    username = models.CharField(max_length=40, unique=True)
    password = PasswordField(max_length=100)
    email = models.EmailField(max_length=60, unique=True)
    token = models.TextField(default='')
    bio = models.TextField(default='')
    image = models.URLField(default='')
```

!!! abstract "AwaitableModel"
	`AwaitableModel`  is a model base class in UtilMeta to provide fully async query in Django using  [encode/databases](https://github.com/encode/databases), which will unleash the async performance for Django ORM

### Article & Comment Model

We follow the [API Documentation: Article](https://realworld-docs.netlify.app/specifications/backend/api-response-format/#single-article) to write article and comment models, open `domain/article/models.py` and write.
```python
from django.db import models
from utilmeta.core.orm.backends.django import models as amodels

class BaseContent(amodels.AwaitableModel):
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author_id: int

    class Meta:
        abstract = True

class Tag(amodels.AwaitableModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Article(BaseContent):
    slug = models.SlugField(db_index=True, max_length=255, unique=True)
    title = models.CharField(db_index=True, max_length=255)
    description = models.TextField()
    author = models.ForeignKey(
	    'user.User', on_delete=models.CASCADE, related_name='articles')
    tags = models.ManyToManyField(Tag, related_name='articles')

class Comment(BaseContent):
    article = models.ForeignKey(
	    Article, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(
	    'user.User', on_delete=models.CASCADE, related_name='comments')
```

!!! tip "Model Inheritance"
	You can find similiar fields in Article and Comment data structure, so we can use model inheritance in Django to reduce the redundant fields declaration 

### Add m2m model

The blog project needs to record the following relationship between users and the liking relationship between users and articles, so we need to add `Favorite` and `Follow` intermediate table model to record the relationship between users, and articles.

We open `domain/user/models.py` again, create the relational table and add a many-to-many relational field to the `User` table
```python
from django.db import models
from utilmeta.core.orm.backends.django.models import PasswordField, AwaitableModel, ACASCADE

class User(AwaitableModel):
    username = models.CharField(max_length=40, unique=True)
    password = PasswordField(max_length=100)
    email = models.EmailField(max_length=60, unique=True)
    token = models.TextField(default='')
    bio = models.TextField(default='')
    image = models.URLField(default='')

	# new +++
    followers = models.ManyToManyField(
        'self', related_name='followed_bys', through='Follow', 
        through_fields=('following', 'follower'),
        symmetrical=False
    )
    favorites = models.ManyToManyField(
	    'article.Article', through='Favorite', related_name='favorited_bys')

class Favorite(AwaitableModel):
    user = models.ForeignKey(User, related_name='article_favorites', on_delete=ACASCADE)
    article = models.ForeignKey(
	    'article.Article', related_name='user_favorites', on_delete=ACASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'article')

class Follow(AwaitableModel):
    following = models.ForeignKey(
	    User, related_name='user_followers', on_delete=ACASCADE)
    follower = models.ForeignKey(
	    User, related_name='user_followings', on_delete=ACASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('following', 'follower')
```

We have added two new models.

* `Favorite`:  the like relation model between user and article.
* `Follow`:  the follow relation model between users

We add many-to-many relationship fields `followers` and `favorites` to the User model, which will be used in the query APIs

!!! tip
	`ACASCADE` in the example is a asynchronous CASCADE function for Django

### Migrate to database

After writing the data model, we can use the migration command provided by Django to easily create the corresponding data table. Since we are using SQLite, we do not need to install the database software in advance. We only need to run the following two commands in the project directory to complete the creation of the database.

```shell
meta makemigrations
meta migrate
```

When you see the following output, you have created the database successfully

```
Operations to perform:
  Apply all migrations: article, contenttypes, user
Running migrations:
  Applying article.0001_initial... OK
  Applying user.0001_initial... OK
  Applying article.0002_initial... OK
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
```

!!! tip "Database Migration Commands"
	The above commands is Django migration commands, `makemigrations` will save the migrations in the models to files, while `migrate` applies all the unapplied migration files to SQLs that create or alters tables

After completing the above command, you will see the SQLite database named `db` just created in the project folder. If you want to know how the database is configured, please open `config/conf.py`. You will find the following code in it

```python
service.use(DatabaseConnections({
	'default': Database(
		name='db',
		engine='sqlite3',
	)
}))
```

This code is used to config the database connections

## 3. User APIs and Authentication

The Realworld blog project needs to use JWT as request authentication, handling user login and identifying the user of the current request.
### JWT authentication

The built-in authentication component of UtilMeta already has the implementation of JWT authentication. We only need to declare the corresponding parameters to obtain the JWT authentication capability. We create a file named `auth.py` in the `config` folder and write the configuration related to authentication.

```python
from .env import env
from utilmeta.core import api, auth
from utilmeta.core.auth import jwt
from utilmeta.core.request import var
from domain.user.models import User

class API(api.API):
    user_config = auth.User(
        User,
        authentication=jwt.JsonWebToken(
            secret_key=env.JWT_SECRET_KEY,
            user_token_field=User.token
        ),
        login_fields=User.email,
        password_field=User.password,
    )

    async def get_user(self) -> User:
        return await self.user_config.getter(self.request)

    async def get_user_id(self) -> int:
        return await var.user_id.get(self.request)
```

We create a new API base class to declare the configuration related to authentication, so that the API classes that need authentication can directly inherit the new API base class., so that the endpoint functions can use `await self.get_user()` to get the current request user.

For any API that requires a user login to access, you can declare `user: User = API.user_config` in the parameters, so that you can get the instance of the current requesting user directly by  `user`.

!!! tip
	For more about user authentication, you can refer to [Request Authentication](../../guide/auth)
#### Environment variables

You should not hard-coded secret keys like `JWT_SECRET_KEY` into the code, but defined using environment variables. UtilMeta provides a set of environment variable declaration class that we can open `config/env.py` and write.

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

In this way, we can define the key of JWT in the variable of the `CONDUIT_JWT_SECRET_KEY` runtime environment and use `env.JWT_SECRET_KEY` to access.

### User API

For users, we need to implement the user’s signup, login, query and update the current user data API, which is actually consistent with the method of the previous [User login & RESTful API](../user-auth) tutorial, so we will directly show the corresponding code.

=== "domain/user/api.py"
	```python
	from utilmeta.core import response, request, api, orm
	from config.auth import API
	from .schema import UserSchema
	
	class UserResponse(response.Response):
		result_key = 'user'
		result: UserSchema
	
	class UserAPI(API):
		response = UserResponse
	
		async def get(self):      # get current user
			user_id = await self.get_user_id()
			if not user_id:
				raise exceptions.Unauthorized('authentication required')
			return await UserSchema.ainit(user_id)
	
		async def put(self, user: UserSchema[orm.WP] = request.BodyParam):
			user.id = await self.get_user_id()
			await user.asave()
			return await self.get()
	
	class AuthenticationAPI(API):
	    response = UserResponse
	
	    async def post(self, user: UserRegister = request.BodyParam):        # signup
	        if await User.objects.filter(username=user.username).aexists():
	            raise exceptions.BadRequest(f'duplicate username: {repr(user.username)}')
	        if await User.objects.filter(email=user.email).aexists():
	            raise exceptions.BadRequest(f'duplicate email: {repr(user.username)}')
	        await user.asave()
	        await self.user_config.alogin_user(
	            request=self.request,
	            user=user.get_instance(),
	        )
	        return await UserSchema.ainit(user.pk)
	
	    @api.post
	    async def login(self, user: UserLogin = request.BodyParam):
	        user_inst = await self.user_config.alogin(
	            self.request, ident=user.email, password=user.password)
	        if not user_inst:
	            raise exceptions.PermissionDenied('email or password wrong')
	        return await UserSchema.ainit(user_inst)
	```
	
=== "domain/user/schema.py"
	```python
	from utilmeta.core import orm
	from .models import User, Follow
	from utilmeta.core.orm.backends.django import expressions as exp
	from utype.types import EmailStr
	
	class UsernameMixin(orm.Schema[User]):
		username: str = orm.Field(regex='[A-Za-z0-9][A-Za-z0-9_]{2,18}[A-Za-z0-9]')
	
	class UserBase(UsernameMixin):
		bio: str
		image: str
	
	class UserLogin(orm.Schema[User]):
		email: str
		password: str
	
	class UserRegister(UserLogin, UsernameMixin): pass
	
	class UserSchema(UserBase):
		id: int = orm.Field(no_input=True)
		email: EmailStr
		password: str = orm.Field(mode='wa')
		token: str = orm.Field(mode='r')
	```


The `AuthenticationAPI` iherits from the API class defined in `config/auth.py`. In the user-signup `post` endpoint, After the user is registered, we directly login the user to the current request using `alogin_user` method
(that is, generate the corresponding JWT Token and then update the user `token`’s field).

In addition, according to the requirement of the request and response body structure in [API Specs](https://realworld-docs.netlify.app/specifications/backend/api-response-format#users-for-authentication), we declare that the request body parameter using `request.BodyParam`, so that the parameter name `user` will be used as the corresponding key. Our response also uses the template key specified `'user'` as the result in `result_key` of the response template, so the structure of the request and response of the user interface is consistent with the documentm, like

```json
{
  "user": {
    "email": "jake@jake.jake",
    "token": "jwt.token.here",
    "username": "jake",
    "bio": "I work at statefarm",
    "image": null
  }
}
```

### Profile API
According to [API Specs](https://realworld-docs.netlify.app/specifications/backend/endpoints#get-profile), the Realworld blog project also needs to develop a Profile API to get user details, follow and unfollow

=== "domain/user/api.py"
	```python
	# new +++
	from .schema import ProfileSchema
	from .models import Follow
	
	class ProfileResponse(response.Response):
	    result_key = 'profile'
	    result: ProfileSchema
	
	@api.route('profiles/{username}')
	class ProfileAPI(API):
	    username: str = request.PathParam(regex='[A-Za-z0-9_]{1,60}') 
	    response = ProfileResponse
	
	    def __init__(self, *args, **kwargs):
	        super().__init__(*args, **kwargs)
	        self.profile: Optional[User] = None
	
	    @api.get
	    async def get(self, user: Optional[User] = API.user_config):
	        return await ProfileSchema.get_runtime(user).ainit(self.profile)
	
	    @api.post
	    async def follow(self, user: User = API.user_config):
	        await Follow.objects.aget_or_create(following=self.profile, follower=user)
	        return await self.get(user)
	
	    @api.delete(follow)
	    async def unfollow(self, user: User = API.user_config):
	        await Follow.objects.filter(following=self.profile, follower=user).adelete()
	        return await self.get(user)
	
	    @api.before('*')
	    async def handle_profile(self):
	        profile = await User.objects.filter(username=self.username).afirst()
	        if not profile:
	            raise exceptions.NotFound(f'profile({repr(self.username)}) not found')
	        self.profile = profile
	```
=== "domain/user/schema.py"
	```python
	class ProfileSchema(UserBase):
		following: bool = False
	
		@classmethod
		def get_runtime(cls, user):
			if not user:
				return cls
	
			class ProfileRuntimeSchema(cls):
				following: bool = orm.Field(
					exp.Exists(
						Follow.objects.filter(
						following=exp.OuterRef('pk'), follower=user)
					)
				)
	
			return ProfileRuntimeSchema
	```


In `domain/user/api.py`, the ProfileAPI reuses the path parameter `username` in API class. And the `handle_profile` before hook queried the corresponding user instance and assigned to `self.profile`, 
so in the API functions `get`, `follow`, `unfollow`, you can use `self.profile` to get the target user instance, In addition, `follow` and `unfollow` reused the serialization logic of the `get` API by calling it directly.

!!! tip "hook function"
	Hooks in UtilMeta API classes are called before/after the target endpoints or handle the errors. to reuse the logics better, you can refer to [Hooks Mechanism in API class](../../guide/api-route/#hook-mechanism)

In addition, for the Profile object eturned by the API, it needs to return a dynamic field `following` that is not from user model. This field should return whether **The user of the current request** followed the target user, so its query expression cannot be written directly in the Schema class

Therefore in  `domain/user/schema.py`,  `ProfileSchema` defined a dynamic query function `get_runtime`, pass in the user of the current request, generate the corresponding query expression according to the requesting user, and then return a new class

In the get endpoint of the `ProfileAPI`, you can see how the dynamic query function is called

```python hl_lines="4"
class ProfileAPI(API):
    @api.get
    async def get(self, user: Optional[User] = API.user_config):
        return await ProfileSchema.get_runtime(user).ainit(self.profile)
```

## 4. Article & Comment APIs

### Article API structure

Based on [API Documentation | Article API](https://realworld-docs.netlify.app/specifications/backend/endpoints#get-article) , we can develop the basic structure of the APIs at the begining
```python
from utilmeta.core import api, request, orm, response
from config.auth import API
from typing import List, Optional

class ArticleSchema(orm.Schema[Article]):
    pass

class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    result: List[ArticleSchema]

class SingleArticleResponse(response.Response):
    result_key = 'article'
    result: ArticleSchema
    
class ArticleAPI(API):
    class BaseArticleQuery(orm.Query[Article]):
        offset: int
        limit: int

    class ListArticleQuery(BaseArticleQuery):
        tag: str
        author: str
        favorited: str

    async def get(self, query: ListArticleQuery) -> MultiArticlesResponse: pass

    @api.get
    async def feed(self, query: BaseArticleQuery) -> MultiArticlesResponse: pass

    @api.get('/{slug}')
    async def get_article(self) -> SingleArticleResponse: pass

    @api.post('/{slug}/favorite')
    async def favorite(
        self, user: User = API.user_config) -> SingleArticleResponse: pass

    @api.delete('/{slug}/favorite')
    async def unfavorite(
        self, user: User = API.user_config) -> SingleArticleResponse: pass

    @api.put('/{slug}')
    async def update_article(self, 
        article: ArticleSchema[orm.WP] = request.BodyParam, 
        user: User = API.user_config) -> SingleArticleResponse: pass

    @api.delete('/{slug}')
    async def delete_article(self, user: User = API.user_config): pass

    async def post(self, 
        article: ArticleSchema[orm.A] = request.BodyParam, 
        user: User = API.user_config) -> SingleArticleResponse: pass
```


!!! tip
	When writing APIs based on the givin specs, you can write the name, input, output of the endpoints first, then filling with the corresponding logics

### Write Article Schema

The article API needs to add, delete, update and query around the article data. we can use the ORM Schema query of UtilMeta to complete it easily. You only need to write a simple class to declare the schema you need and use it directly. Let’s take the article as an example.

```python
from utype.types import *
from utilmeta.core import orm
from .models import Article
from domain.user.schema import ProfileSchema
from django.db import models

class ArticleSchema(orm.Schema[Article]):
    id: int = orm.Field(no_input=True)
    body: str
    created_at: datetime
    updated_at: datetime
    author: ProfileSchema
    author_id: int = orm.Field(mode='a', no_input=True)
    
    slug: str = orm.Field(no_input='aw', default=None, defer_default=True)
    title: str = orm.Field(default='', defer_default=True)
    description: str = orm.Field(default='', defer_default=True)
    tag_list: List[str] = orm.Field(
	    'tags.name', alias='tagList',
	    mode='rwa', no_output='aw', default_factory=list
	)
    favorites_count: int = orm.Field(
        models.Count('favorited_bys'),
        alias='favoritesCount'
    )
```

In the Schema class we wrote, there are many kinds of fields, and we will explain them one by one.

* `author`: **Relational object**, it is a foreign key field, and uses a type annotation to specify another Schema class. When querying, `author` will query out the data of the author user of the article with the fields in `ProfileSchema`.

!!! tip "Relational Query Field"
	All related fields (ForeignKey, M2M, ...) supports query relational object, for example, the `author` field in the example has a reverse relation `articles`, so you can query all articles of a user using `articles: List[ArticleSchema]` in the user's Schema 

* `tag_list`：**Multi-level relation field**，Sometimes you just need to query a single field in a relational table, This field declares `orm.Field('tags.name')`, so it will query along the path of  `tags`  and  `name`. The final query is the name list of the tag corresponding to the article.

* `favorites_count`: **Query expression field**: You have declared `favorites = models.ManyToManyField('article.Article', related_name='favorited_bys')` in the User model, so, `favorites_count` using `models.Count('favorited_bys')` to query "**number of users who liked the article**".

Also for the `tag_list` and `favorites_count` fields, we use `alias` parameters to give them real names for input and output (camelCase styled naming according to API specs).

#### Field Mode
You can see that in the above example, many fields specified `mode`, this parameter can be used to declare the applicable mode (scenario) of a field, so that it can show different behaviors in different scenarios. The commonly used scenarios in the data CRUD are

* `'r'`: **Read/Retrieve**: returned as the result of a database query
* `'w'`: **Write/Update**: Update existing record in the database using requested data
* `'a'`: **Add/Create**: Add new record to database using requested data.

You can combine mode chars to indicate that a field supports multiple modes. By default, UtilMeta will automatically assign a pattern based on the model field.

!!! tip "Automatic mode"
	Even if you didn't specify `mode`, UtilMeta will assign `mode` based on the features of the model fields, for instance, field like `created_at` with auto_now_add cannot be updated or provided in creation, so its mode will be assigned to `'r'`, you can also specify the `mode` explicitly to override the default behaviour

For example
```python
author_id: int = orm.Field(mode='a', no_input=True)
```
field `author_id` indicate

* This field applies only to the mode `'a'` (data creation).
* No input is required for this field

From the perspective of actual development, the author field of an article should be assigned from current request user, ignoring other values that may be provided by the client, and should not be allowed to be modified. So the field will be assigned before the data is saved, as shown in
```python
class ArticleAPI(API):
    @api.post
    async def post(self, article: ArticleSchema, user: User = API.user_config):
        article.author_id = user.pk
        await article.asave()
```

!!! tip
	`no_input=True` will ignore the data provided in the Schema initialization (like data from the client), but still allow developer to assign values in the function

**Mode generation** 

You can use `YourSchema['<mode>']` to quickly generate Schema classes in sepcific mode. The UtilMeta module `orm` provides several commonly used modes.

* `orm.A`:  This is a `'a'` mode that is commonly used for POST methods to create new objects.
* `orm.W`:  This is a `'w'` mode that is commonly used for PUT methods to update objects.
* `orm.WP`:  This is a `'w'` mode that ignores the required ( `required`) attribute. It is often used in the PATCH method to partially update an object.

So you can use `ArticleSchema[orm.A]` directly to generate the ArticleSchema class in creation mode as the data input annotation for the create article interface.

!!! tip
	 Of course, if you think the mode way is too complex, you can split the input / output of different endpoints into different Schema
#### Dynamic query field
In a blog project, we need to return the  "**whether the current user likes it**" field for each article, and we can still use the runtime Schema function method to handle such dynamic queries.
```python
class ArticleSchema(orm.Schema[Article]):
	...
    favorited: bool = False
    
    @classmethod
    def get_runtime(cls, user_id):
        if not user_id:
            return cls

        class ArticleRuntimeSchema(cls):
            favorited: bool = exp.Exists(
				Favorite.objects.filter(article=exp.OuterRef('pk'), user=user_id)
			)
            
        return ArticleRuntimeSchema
```

We write a `get_runtime` class function that takes the user’s ID as input to generate the corresponding query field, so that we can use `ArticleSchema.get_runtime(user_id)` to dynamically obtain the Schema class in the API function.

### Article Query API

We can article list API as an example of how to write a query API. refer to [API docs](https://realworld-docs.netlify.app/specifications/backend/endpoints/#list-articles) 
```python
class MultiArticlesResponse(response.Response):
    result_key = 'articles'
    count_key = 'articlesCount'
    result: List[ArticleSchema]
    
class ArticleAPI(API):
    # new +++
    class ListArticleQuery(orm.Query[Article]):
        tag: str = orm.Filter('tags.name')
        author: str = orm.Filter('author.username')
        favorited: str = orm.Filter('favorited_bys.username')
        offset: int = orm.Offset(default=0)
        limit: int = orm.Limit(default=20, le=100)

    async def get(self, query: ListArticleQuery) -> MultiArticlesResponse:
        schema = ArticleSchema.get_runtime(
            await self.get_user_id()
        )
        return MultiArticlesResponse(
            result=await schema.aserialize(
                query.get_queryset()
            ),
            count=await query.acount()
        )
```

Our query API needs to support data filtering through `tag`, `author`, `favorited`, and also needs to support the use `offset` of, `limit` to control the number of returns. As you can see, we only need to write a Query schema,

* `tag`: Use `orm.Filter('tags.name')` as the target field of the specified query. When the query parameters of the request contain `tag`, the corresponding filter query will be added, the usage of `author` and `favorited` is similar
* `offset`: Use `orm.Offset` to defines a standard begining offset. The default is 0.
* `limit`: Use `orm.Limit` to defines limit on the number of results returned, 20 by default and 100 by maximum

!!! tip "Paging parameters"
	`offset` and `limit` is a pair of common paging parameters in API development, the generated queryset can be expressed as `queryset[offset: offset + limit]`, which means client can query a small slice of the result, and alter the next `offset` query based on the returning values

 `orm.Query` as the type annotation of API function parameter will parse the querystring of the request by default, and it has several common methods.

* `get_queryset()`: Generate the corresponding queryset according to the query parameters. If you use Django as the ORM library, you will get the **Django QuerySet**. This query set will apply all the filtering and paging parameters. You can directly use it as the input of the serialization method to get the corresponding data.

* `count()`: Get the total number of queries by ignoring the paging parameters. This method is very useful for paging queries, because the client not only needs to get the data of the current request, but also needs to get the total number of results corresponding to the query, so that the client can correctly display the number of pages for paging, or know whether the query has been completed. The asynchronous implementation of this method is `acount`

In the `get` method, we not only call `schema.aserialize` to serialize the generated target query set, but also call `query.acount()`  to return the total number of articles. Combined with the response body structure defined in `MultiArticlesResponse`, we can get the following response required by the document

```json
{
    "articles": [],
    "articlesCount": 0
}
```

#### Using hooks to reuse logic

Reading the API specs in the article section, we can see that there are many endpoints with repetitive logic, such as

* In the Create Article/Update Article endpoints, you need to generate new `slug` fields for the article based on the title in the request data
* To query/update/like/unlike/delete endpoints, you need to query whether the corresponding article exists according to `slug` the path parameter
* To query/update/like/unlike/create endpoints, you need to return the target article object or the newly created article object

For these repeated logics, we can use **hook function** to reuse, and the example is as follows
```python
class SingleArticleResponse(response.Response):
    result_key = 'article'
    result: ArticleSchema

class ArticleAPI(API):
    @api.get('/{slug}')
    async def get_article(self): pass

    @api.post('/{slug}/favorite')
    async def favorite(self): pass

    @api.delete('/{slug}/favorite')
    async def unfavorite(self): pass

    @api.put('/{slug}')
    async def update_article(self): pass

    @api.delete('/{slug}')
    async def delete_article(self): pass
        
    async def post(self): pass
 
    # new ++++
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tags = []
        self.article: Optional[Article] = None
        
    @api.before(get_article, favorite, unfavorite, update_article, delete_article)
    async def handle_slug(self, slug: str = request.SlugPathParam):
        article = await Article.objects.filter(slug=slug).afirst()
        if not article:
            raise exceptions.NotFound('article not found')
        self.article = article

    @api.before(post, update_article)
    async def gen_tags(self, article: ArticleSchema[orm.A] = request.BodyParam):
        for name in article.tag_list:
            slug = '-'.join([''.join(filter(str.isalnum, v)) 
                for v in name.split()]).lower()
            tag, created = await Tag.objects.aupdate_or_create(
                slug=slug, defaults=dict(name=name))
            self.tags.append(tag)

    @api.after(get_article, favorite, unfavorite, update_article, post)
    async def handle_response(self) -> SingleArticleResponse:
        if self.tags:
            # create or set tags relation in creation / update
            await self.article.tags.aset(self.tags)
        schema = ArticleSchema.get_runtime(
            await self.get_user_id()
        )
        return SingleArticleResponse(
            await schema.ainit(self.article)
        )
```

We defined several hook functions in our example.

* `handle_slug`:  a before hook defined by `@api.before` to query the corresponding article and assign a value to `self.article` using the `slug` path parameter before the API functions executed. The corresponding API functions can access the target article directly using this instance attribute.
* `gen_tags`:  a before hook that called before created or updated. A series of tag instances are generated by parsing the fields `tag_list` and stored in the `self.tags` attribute.
* `handle_response`:  an after hook defined by `@api.after`, executed after endpoints that get/update/create a single article object, serialize the `self.article` instance using dynamic subclasses of ArticleSchema and returned, and if `self.tags` generated by `gen_tags` is not empty, it will be assigned to the article tags relation

### Comment API

Next we'll develop the comment APIs, from [API documentation for the comment APIs](https://realworld-docs.netlify.app/specifications/backend/endpoints#add-comments-to-an-article), we can see that the comment endpoints are all started with `/api/articles/:slug/comments`, and the path is located in the subdirectory of the article API, that is to say, the API class of the comment API needs to be mounted on the API class of the article API. We open `domain/article/api.py` and add the code for the comment API

```python
from utilmeta.core import api, request, orm, response
from config.auth import API
from .models import Article, Comment
from .schema import CommentSchema

# new +++
class CommentSchema(orm.Schema[Comment]):
	id: int = orm.Field(mode='r')
	article_id: int = orm.Field(mode='a', no_input=True)
	body: str
	created_at: datetime
	updated_at: datetime
	author: ProfileSchema
	author_id: int = orm.Field(mode='a', no_input=True)
	
@api.route('{slug}/comments')
class CommentAPI(API):
	slug: str = request.SlugPathParam

	class ListResponse(response.Response):
		result_key = 'comments'
		name = 'list'
		result: List[CommentSchema]

	class ObjectResponse(response.Response):
		result_key = 'comment'
		name = 'object'
		result: CommentSchema

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.article: Optional[Article] = None

	async def get(self) -> ListResponse:
		return self.ListResponse(
			await CommentSchema.aserialize(
				Comment.objects.filter(article=self.article)
			)
		)

	async def post(self, comment: CommentSchema[orm.A] = request.BodyParam,
				   user: User = API.user_config) -> ObjectResponse:
		comment.article_id = self.article.pk
		comment.author_id = user.pk
		await comment.asave()
		return self.ObjectResponse(
			await CommentSchema.ainit(comment.pk)
		)

	@api.delete('/{id}')
	async def delete_comment(self, id: int, user: User = API.user_config):
		comment = await Comment.objects.filter(
			id=id,
		).afirst()
		if not comment:
			raise exceptions.NotFound('comment not found')
		if comment.author_id != user.pk:
			raise exceptions.PermissionDenied('permission denied')
		await comment.adelete()

	@api.before('*')
	async def handle_article_slug(self):
		article = await Article.objects.filter(slug=self.slug).afirst()     
		if not article:
			raise exceptions.NotFound('article not found')
		self.article = article

class ArticleAPI(API):
	comments: CommentAPI
```

We need the comment API's path to be `articles/{slug}/comments`, so we use the decorator `@api.route('{slug}/comments')` on the CommentAPI, so that when we mount the CommentAPI on the ArticleAPI, The path to the ArticleAPI is extended `{slug}/comments` to become the path of the CommentAPI.

The `{slug}`  path param in the comment APIs identifies the article. We use a before hook named `handle_article_slug` in the CommentAPI to uniformly query out the corresponding article before the endpoint functions is executed.

!!! tip "API genernal parameters"
	In the CommentAPI, every endpoints need to receive `{slug}` path param, so we can declare this param directly to API class, and use `self.slug` to access this param, this kind of params is called **General Parameters** of the API class, will also be integrated to the API docs

You can view the full code of ArticleAPI and CommentAPI at [here](https://github.com/utilmeta/utilmeta-py-realworld-example-app/blob/master/conduit/domain/article/api.py)
## 5. Mount API and handle errors

We have written all the APIs, and then we just need to integrate them according to the documentation. We use the API class mounting to assign the path to the written APIs, open `service/api.py` and update the code of root API.
```python
import utype
from utilmeta.utils import exceptions, Error
from domain.user.api import UserAPI, ProfileAPI, AuthenticationAPI
from domain.article.api import ArticleAPI
from domain.article.models import Tag
from utilmeta.core import api, response
from typing import List

class TagsSchema(utype.Schema):
	tags: List[str]

class ErrorResponse(response.Response):
	message_key = 'msg'
	result_key = 'errors'

@api.CORS(allow_origin='*')
class RootAPI(api.API):
    user: UserAPI
    users: AuthenticationAPI
    profiles: ProfileAPI
    articles: ArticleAPI
    
    @api.get
    async def tags(self) -> TagsSchema:
        return TagsSchema(
            tags=[name async for name in Tag.objects.values_list('name', flat=True)]
        )

    @api.handle('*', Exception)
    def handle_errors(self, e: Error) -> ErrorResponse:
        detail = None
        exception = e.exception
        if isinstance(exception, exceptions.BadRequest):
            status = 422
            detail = exception.detail
        else:
            status = e.status
        return ErrorResponse(detail, error=e, status=status)
```

We have write `handle_errors` as the error handling hook, using `@api.handle('*', Exception)` to indicates that all errors of all APIs will be handled. According to the requirements of [API Documentation | Error Handling](https://realworld-docs.netlify.app/specifications/backend/error-handling), we adjust the response status code of the error type `exceptions.BadRequest` to 422 (400 by default). And return detailed error information obtained through `detail` of the Error instance.

For example, when we try to access `GET/api/articles?limit=x`, the response results will clearly reflect the parameters and reasons for the error.
```json
{
  "errors": {
    "name": "query",
    "field": "Query",
    "origin": {
      "name": "limit",
      "value": "x",
      "field": "Limit",
      "schema": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100
      },
      "msg": "invalid number: 'x'"
    }
  },
  "msg": "BadRequest: parse item: ['query'] failed: parse item: ['limit'] failed: invalid number: 'x'"
}
```

In addition, the RootAPI we wrote uses a `@api.CORS` decorator to specify a cross-source policy for all APIs, and we use `allow_origin='*'` to allow all front-end origins to be accessed.

!!! tip "CORS requests"
	Cross domain request (or cross origin request) refers to a request where the source origin (protocol+hostname+port) of the browser is different from the source origin of the backend API. In this case, the browser uses a CORS mechanism to control resource access
	
	The CORS plugin of UtilMeta automatically processes cross origin requests, including responding to the `OPTIONS` method and returning the correct `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers` response headers based on declaration and configuration
	
	For a detailed explanation of CORS, please refer to [this MDN document](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)


## 6. Configure and run

### Time configuration
Since the output time given in the API documentation is in a format like `"2016-02-18T03:22:56.637Z"`, we open `config/conf.py` and add the code for the time configuration
```python hl_lines="19-23"
from utilmeta import UtilMeta
from config.env import env

def configure(service: UtilMeta):
    from utilmeta.core.server.backends.django import DjangoSettings
    from utilmeta.core.orm import DatabaseConnections, Database
    from utilmeta.conf.time import Time

    service.use(DjangoSettings(
        apps_package='domain',
        secret_key=env.DJANGO_SECRET_KEY
    ))
    service.use(DatabaseConnections({
        'default': Database(
            name='conduit',
            engine='sqlite3',
        )
    }))
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%S.%fZ"
    ))
```

The `Time` configuration class configures the timezone, UTC, and output time format used by the API
### Environment variables
Remember that we introduced an environment variable called `JWT_SECRET_KEY` in the JWT authentication section? We need to set it, otherwise the project will not run properly, and we can open `config/env.py` it to see the environment variables we declared.
```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

Before running, you need to set this key first. The command can be referred to as follows

=== "Windows"
	```shell
	set CONDUIT_JWT_SECRET_KEY <YOUR_KEY>
	```
=== "Linux"
	```shell
	export CONDUIT_JWT_SECRET_KEY=<YOUR_KEY>
	```

### Run the project

Next we can run the project, and we can see that there is a `main.py` file in the root directory of the project, with the following code
```python
from config.service import service

service.mount('service.api.RootAPI', route='/api')
app = service.application()

if __name__ == '__main__':
    service.run()
```

So we just need to execute the following command to run the project
```shell
python main.py
```

Since we are using  `starlette` as the asynchronous runtime implementation, UtilMeta will use `uvicorn` to run the project. When you see the following output, the project runs successfully.
```
INFO:     Started server process [26428]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Our service runs on port 8000 of the localhost. This setting can be found and adjusted in `config/service.py`.
```python
from utilmeta import UtilMeta
from config.conf import configure
from config.env import env
import starlette

service = UtilMeta(
    __name__,
    name='conduit',
    description='Realworld DEMO - conduit',
    backend=starlette,
    production=env.PRODUCTION,
    version=(1, 0, 0),
    host='0.0.0.0' if env.PRODUCTION else '127.0.0.1',
    port=80 if env.PRODUCTION else 8000,
    asynchronous=True
)
configure(service)
```

!!! warning "Port conflict"
	If you have multiple services running at the same port, you will see the error message like follows
	```
	[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of e
	ach socket address (protocol/network address/port) is normally permitted
	```
	But all you need to do is adjust the port number and restart the project

### Blog frontend
Frontend development and deployment of the blog project does not fall into the category of UtilMeta, but the tutorial here simply demonstrates how to install and run the frontend code of the blog project in the case locally, so that you can use and debug your API directly.

!!! tip
	This chapter requires the node.js environment and the knowledge of `npm`

Let’s use [Client implementation of Vue3](https://github.com/mutoe/vue3-realworld-example-app) the client demo. First, let’s clone the project.
```shell
git clone git@github.com:mutoe/vue3-realworld-example-app.git
```

Open `.env` file and change the API address to the blog API that just ran.
```env
BASE_URL=/api
VITE_API_HOST=http://127.0.0.1:8000
```

Then we go into the project to install the dependencies and run the project.

```shell
cd vue3-realworld-example-app
npm install
npm dev
```

The following info indicates that the project has been started

```
➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

We can click to visit [http://localhost:5173/](http://localhost:5173/) to open the client of the blog.

Then you can experience your own blog.

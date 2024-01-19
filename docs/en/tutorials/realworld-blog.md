# Realworld Blog Project

The tutorial in this chapter takes you through the implementation of a classic blog project API using UtilMeta, which provides the following functionality

* User registration, login, access, update information, follow, unfollow
* Article creation, modification, likes, recommendations, article comment creation and deletion

Don’t worry, the UtilMeta code that does all of the above is less than 600 lines. Here’s a step-by-step guide on how to do it, starting with the creation of your project

!!! tip
	We will implement the APIs based on [Realworld API Docs](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints), The code of this tutorial is in [this Github repo](https://github.com/utilmeta/utilmeta-py-realworld-example-app)
## 1. Create project

### Installation dependency

Before creating the project, install the dependent libraries required for this tutorial
```shell
pip install utilmeta starlette django databases[aiosqlite]
```

!!! Abstract "Tech Stack"
	* Develop an asynchronous API using `starlette` as the HTTP backend
	* Using `Django` ORM as a data model repository
	* Use `SQLite` as the database
	* User authentication using `JWT`

### setup project

Create a new UtilMeta project using the following command

```shell
meta setup utilmeta-realworld-blog --temp=full
```

Then follow the prompts or skip, and enter starlette when prompted to select backend

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

!!! Tip “Template Parameters”


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

Of these, we propose to organize the

*  `config`: Store configuration files, environment variables, service running parameters, etc.
*  `domain`: Store domain applications, models, and RESTful interfaces
*  `service`: Integrate internal interfaces with external services
*  `main.py`: Run the entry file, which can be used `python main.py` to run the service directly during debugging.
*  `meta.ini`: Metadata declaration file, `meta` Command line tool determines the root directory of the project by identifying the location of this file

## 2. Write the data model

For an API system like blog, which focuses on the addition, deletion, modification and query of data, we often start to develop from the data model. In the [API Specs](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints), we can conclude that we need to write user, article, comment and other models.

### Create an application

Since we use Django as the underlying ORM implementation, we organize our project the way Django organizes apps, and we can simply divide the blog project into two domain applications: [user] and [post].

First add a user application named user to the project using the following command
```shell
meta add user
```
After running the command, you can see that `domain` a new folder has been created under the folder, with the following structure

```
/domain
	/user       # new folder
		/migrations
		api.py
		models.py
		schema.py
```

The user model for the blog and the related interfaces for user and authentication will be placed in this folder

!!! tip

Let’s add another article app called article.
```shell
meta add article
```

### User model

We will write the data model as [ API Documentation: User](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#users-for-authentication) described for the user data structure in. We open `domain/user/models.py` and write the user’s model.
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

!!! abstract “AwaitableModel”

!!! tip

### Article & Comment Model

We follow the [ API Documentation: Article](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format/#single-article) model of writing articles and comments, open `domain/article/models.py` and write.
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

!!! Tip “Model Inheritance”

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

* The `Favorite` article likes the model.
*  `Follow`: Attention between users Attention model

At the same time, the corresponding many-to-many relationship fields `followers` and `favorites` are added in the User model, which will be used in the writing of the next query interface

!!! tip

### Migrate to database

After writing the data model, we can use the migration command provided by Django to easily create the corresponding data table. Since we are using SQLite, we do not need to install the database software in advance. We only need to run the following two commands in the project directory to complete the creation of the database.

```shell
meta makemigrations
meta migrate
```

When you see the following output, you have finished creating the database

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

!!! Tip “Database Migration Commands”


After completing the above command, you will see `db` the SQLite database named just created in the project folder. If you want to know how the database is configured, please open `config/conf.py` the file. You will find the following code in it

```python
service.use(DatabaseConnections({
	'default': Database(
		name='db',
		engine='sqlite3',
	)
}))
```

This code is used to declare the connection configuration of the database.

## 3. User APIs and Authentication

The Realworld blog project needs to use JWT as a means of request authentication, handling user login and identifying the user of the current request.
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
            key=env.JWT_SECRET_KEY,
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

We create a new API base class to declare the configuration related to authentication, so that the API classes that need authentication can directly inherit the new API base class.

After that, the interface classes we write that need authentication can inherit this API class, so that the interface function can `await self.get_user()` obtain the current request user.

For any interface that requires a user login to access, you can declare `user: User = API.user_config` it directly in the interface parameter, so that you can `user` get the instance of the current requesting user directly.

!!! tip

#### Environment variables

Important keys like `JWT_SECRET_KEY` this are generally not hard-coded into the code, but defined using environment variables. UtilMeta provides a set of environment variable definition templates that we can open `config/env.py` and write.

```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

In this way, we can define the key of JWT in the variable of the `CONDUIT_JWT_SECRET_KEY` runtime environment and use `env.JWT_SECRET_KEY` access.

### User API

For users, we need to implement the user’s registration, login, query and update the current user data interface, which is actually consistent with the method of the previous tutorial [ Write user login registration API ](tutorials/user-auth), and we will directly show the corresponding code.

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
	        await self.user_config.login_user(
	            request=self.request,
	            user=user.get_instance(),
	        )
	        return await UserSchema.ainit(user.pk)
	
	    @api.post
	    async def login(self, user: UserLogin = request.BodyParam):
	        user_inst = await self.user_config.login(
	            self.request, token=user.email, password=user.password)
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


The Authentication API we wrote inherits from the API class defined earlier `config/auth.py` in, and in the user-registered `post` interface, After the user is registered, the method is used `self.user_config.login_user` to directly log the user into the current request (that is, generate the corresponding JWT Token and then update the user `token`’s field).

In addition, due to [API Specs](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#users-for-authentication) the requirement of the request and response body structure in, we declare that the request body parameter is `request.BodyParam` used, so that the parameter name `user` will be used as the corresponding template key. Our response also uses the template key specified `'user'` as the result in `result_key` the response template, so the structure of the request and response of the user interface is consistent with the document.

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
According to [API Specs](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints#get-profile), the Realworld blog project also needs to develop a Profile interface to get user details, follow and unfollow

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


First `domain/user/api.py`, In, the Profile API reuses the path parameter `username` with the public parameter of the API class. And that target us instance obtained by inquire the target user instance in the `handle_profile` preprocessing hook can complete the corresponding logic in the API interface function `get` `follow` `unfollow` by only `self.profile` access the target user instance, In addition `follow` `unfollow`, the serialization logic of the `get` interface is reused on return with the interface.

!!! Tip “hook function”

In addition, for the Profile object [API Specs](https://realworld-docs.netlify.app/docs/specs/backend-specs/api-response-format#profile) to be returned by the interface, it needs to return a dynamic field `following` that is not a user model. This field should return whether **The user of the current request** followed the target user, so its query expression cannot be written directly in the Schema class

Therefore `domain/user/schema.py`, in, we `ProfileSchema` define a dynamic query function `get_runtime`, pass in the user of the current request, generate the corresponding query expression according to the requesting user, and then return a new class

In the get interface of the Profile API, you can see how the dynamic query function is called

```python
class ProfileAPI(API):
    @api.get
    async def get(self, user: Optional[User] = API.user_config):
        return await ProfileSchema.get_runtime(user).ainit(self.profile)
```

## 4. Article & Comment APIs

### Article API structure

Based on [ API Documentation | Article Interface ](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints#get-article) the definition of the section, we can first develop the basic structure of the interface.
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

### Write Article Schema

The article interface we write needs to add, delete, modify and query around the article data. At this time, we can use the Schema query of UtilMeta to complete it easily. You only need to write a simple class to declare the template you need and use it directly. Let’s take the article as an example.
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

*  `author`: **Relational object**, it is a foreign key field, and uses a type declaration to specify another Schema class. When querying, `author` it will query out the information of the author and user of the article according to the declaration of ProfileSchema.

!!! Tip “Relational Query Field”

* `tag_list`：**Multi-level relation field**，Sometimes you just need to query out a field in a relational table, and you can use this usage. This field declares `orm.Field('tags.name')` that it will query along `tags` the path of- `name`. The final query is the name list of the tag corresponding to the article.

*  `favorites_count`: **Expression field**: Remember the `favorites = models.ManyToManyField('article.Article', related_name='favorited_bys')` fields you declared in the User model? You can flexibly use these relation names or inverse relations to create expression fields `favorites_count` using `models.Count('favorited_bys')` the query [number of users who liked the article].

Also for the `tag_list` and `favorites_count` fields, we use `alias` parameters to give them real names for input and output.

#### Field mode
You can see that in the above example, many fields specify `mode` this parameter. `mode` The parameter can be used to declare the applicable mode (scenario) of a field, so that it can show different behaviors in different scenarios. The commonly used scenarios in the addition, deletion, modification and query of data are

*  `'r'`: **Read/Retrieve**: returned as the result of a database query
*  `'w'`: **Write/Update**: An existing record in the database needs to be updated as requested data
*  `'a'`: **Add/Create**: As the requested data, a new record needs to be created in the database

You can combine pattern letters to indicate that a field supports multiple patterns. By default, UtilMeta will automatically assign a pattern based on the nature of the model field.

!!! Tip “Automatic mode assignment”

For example, the field
```python
author_id: int = orm.Field(mode='a', no_input=True)
```
The meaning of which is

* This field applies only to the schema `'a'` (create data).
* No entry is required for this field

From the perspective of actual development, the author field of an article should be passed in to the user of the current request when the article is created, ignoring other values that may be provided by the client, and should not be allowed to be modified. In actual interface development, the field will be assigned before the data is saved, as shown in
```python
class ArticleAPI(API):
    @api.post
    async def post(self, article: ArticleSchema, user: User = API.user_config):
        article.author_id = user.pk
        await article.asave()
```

!!! tip

** Pattern generation ** You can use `YourSchema['<mode>']` the UtilMeta module directly to quickly generate Schema classes for patterns. The UtilMeta module `orm` provides several commonly used patterns.

*  `orm.A` This is a `'a'` pattern that is commonly used for POST methods to create new objects.
*  `orm.W` This is a `'w'` pattern that is commonly used for PUT methods to update objects.
*  `orm.WP`: a pattern that ignores the required ( `required`) attribute `'w'`. It is often used in the PATCH method to partially update an object.

So you can use `ArticleSchema[orm.A]` directly to generate the ArticleSchema class in create mode as the data input for the create article interface.

!!! tip
#### Dynamic query field
In a blog project, we need to return the information [whether the current user likes it or not] for each post, and we can still use the runtime Schema function method to handle such dynamic queries.
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

We write a `get_runtime` class function that takes the user’s ID as input to generate the corresponding query field, so that we can use `ArticleSchema.get_runtime(user_id)` this way to dynamically obtain the Schema class in the API function.

### Article Query API

We can [Article list API](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints/#list-articles) use UtilMeta as an example of how to write a query interface.
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

Our query interface needs to support data filtering through `tag` parameters such as, `author` `favorited`, and also needs to support the use `offset` of, `limit` to control the number of returns. As you can see, we only need to write a Query template,

*  `tag`: Use `orm.Filter('tags.name')` the target field of the specified query. When the query parameters of the request contain `tag` parameters, the corresponding filter query will be added, which is consistent with `author` the principle of such fields as. `favorited`
*  `offset`: Use `orm.Offset` a field that defines a standard starting quantity. The default is 0.
*  `limit`: Use `orm.Limit` a defined limit on the number of results returned, 20 by default and 100 by maximum

!!! Tip “Tile Control Parameters”

 `orm.Query` The template class as an API function parameter will resolve the query parameters of the request by default, and it has several common methods.

*  `get_queryset()`: Generate the corresponding query set according to the query parameters. If you use Django as the ORM library, you will get the Django QuerySet. This query set will apply all the filtering and paging parameters. You can directly use it as the input of the serialization method to get the corresponding data.

*  `count`: Obtain the total number of queries by ignoring the paging parameter. This method is very useful for paging queries, because the client not only needs to get the data of the current request, but also needs to get the total number of results corresponding to the query, so that the client can correctly display the number of pages for paging, or know whether the query has been completed. The asynchronous implementation of this method is

Because the interface needs to return the total number of articles queried, in the `get` method, we not only call `schema.aserialize` to serialize the generated target query set, but also call to `query.acount()` return the total number of articles. Combined with the response body structure defined in MultiArticles Response, we can get the following response required by the document

```json
{
    "articles": [],
    "articlesCount": 0
}
```

#### Using hooks to reuse logic

Reading the API interface documentation in the article section, we can see that there are many interfaces with repetitive logic, such as

* In the Create Article/Update Article interface, you need to generate new `slug` fields for the article based on the title in the request data
* To query/update/like/cancel like/delete the interface, you need to query whether the corresponding article exists according to `slug` the path parameter
* To query/update/like/unlike/create an interface, you need to return the target article object or the newly created article object

For these repeated logics, we can use ** Hook function ** them to complete the reuse, and the example is as follows
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

*  `handle_slug`: Use `@api.before` the preprocessing hook defined by the decorator to query the corresponding article and assign a value to `self.article` it before the interface using the `slug` path parameter is executed. The corresponding interface function can be accessed directly using this instance attribute.
* A preprocessing hook that is executed before the article interface is `gen_tags` created or updated. A series of tag instances are generated by parsing the fields of the ArticleSchema `tag_list` and stored in a `self.tags` property.
*  `handle_response`: a response processing hook defined with `@api.after` a decorator, executed after manipulating or creating an interface for a single article object, where the article object is relationally assigned if an instance of `tags` hook generation is detected `gen_tags`, And the `self.article` instance is serialized using dynamic subclasses of ArticleSchema and returned

### Comment API

Next, we develop the comment interface, from [ API documentation for the comment interface](https://realworld-docs.netlify.app/docs/specs/backend-specs/endpoints#add-comments-to-an-article) which we can see that the comment interface starts with `/api/articles/:slug/comments` the path, and the path is located in the subdirectory of the article interface, that is to say, the API class of the comment interface needs to be mounted on the API class of the article interface. We `domain/article/api.py` add the code for the comment interface in the

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

We need to configure the comment API path to `articles/{slug}/comments`, so we use the decorator `@api.route('{slug}/comments')` to decorate the CommentAPI directly, so that when we mount the CommentAPI on the ArticleAPI, The path to the Article API is extended `{slug}/comments` directly to the path to the CommentAPI.

The path parameter in `{slug}` the comment interface path is the path parameter that identifies the article. We have implemented a preprocessing hook named `handle_article_slug` in the Comment API to uniformly query out the corresponding article before the interface function is executed.

!!! Tip “API Public Parameters”

You can [this](https://github.com/utilmeta/utilmeta-py-realworld-example-app/blob/master/conduit/domain/article/api.py) browse the complete sample code of the post and comment interface.
## 5. Mount API and handle errors

We have written all the interfaces, and then we just need to integrate them according to the documentation. We use the API class mounting method to give the path to the written API interface, and open `service/api.py` the root API code.
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

We have declared an `handle_errors` error handling hook, which `@api.handle('*', Exception)` indicates that all errors of all interfaces will be handled. According to [ API Documentation | Error Handling](https://realworld-docs.netlify.app/docs/specs/backend-specs/error-handling) the requirements of, we adjust the response status code of the error type `exceptions.BadRequest` of check failure to 422 (400 by default). And detailed error reporting information is obtained through the attribute of the error instance `detail`.

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

In addition, the root API we wrote uses a `@api.CORS` decorator to specify a cross-source policy for all API interfaces, and we use `allow_origin='*'` to allow all front-end source addresses to be accessed.

!!! Tip “CORS Cross-Source Request Processing
	
	
## 6. Configure and run

### Time configuration
Since the output time given in the API documentation is in a similar `"2016-02-18T03:22:56.637Z"` format, we open `config/conf.py` and add the code for the time configuration
```python
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
    # new +++
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%S.%fZ"
    ))
```

The Time configuration class configures the time zone, UTC, and output time format used by the API
### Environment variables
Remember that we introduced an environment variable called JWT _ SECRET _ KEY in the JWT authentication section? We need to set it, otherwise the project will not run properly, and we can open `config/env.py` it to see the environment variables we declared.
```python
from utilmeta.conf import Env

class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    JWT_SECRET_KEY: str = ''
    DJANGO_SECRET_KEY: str = ''

env = ServiceEnvironment(sys_env='CONDUIT_')
```

Before running, you need to set this key first. The command can be referred to as follows

=== “Windows”
	```shell
	set CONDUIT_JWT_SECRET_KEY <YOUR_KEY>
	```
=== “Linux”
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

So we just need to execute
```shell
python main.py
```

Run the project. Since we are `starlette` using the asynchronous interface provided as a runtime implementation, UtilMeta will use `uvicorn` it to run the project. When you see the following output, the project runs successfully.
```
INFO:     Started server process [26428]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Our service runs on port 8000 of the local machine. This setting can be `config/service.py` found and adjusted in.
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

!!! Tip “Port conflict”
	```
	ERROR:    [Errno 10048] error while attempting to bind on address 
	('127.0.0.1', 8000): 通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
	```

### Blog frontend
Front-end development and deployment of blogs does not fall into the category of UtilMeta, but the tutorial here simply demonstrates how to install and run the front-end code of the blog project in the case locally, so that you can use and debug your API directly.

!!! tip


Let’s use [ Client implementation of Vue3 ](https://github.com/mutoe/vue3-realworld-example-app) the client demo. First, let’s clone the project.
```shell
git clone git@github.com:mutoe/vue3-realworld-example-app.git
```

Open `.env` the file and change the API address to the blog API that just ran.
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

The following prompt indicates that the project has been started

```
➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

We can click visit [http://localhost:5173/](http://localhost:5173/) to open the client of the blog.

Then you can experience your own blog.

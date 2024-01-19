# Query and ORM operations

UtilMeta implements a unique and efficient declarative Schema query mechanism to quickly implement add, delete, modify and query operations and develop RESTful interfaces. We can see the concise case code of declarative ORM and API in  [UtilMeta Framework Homepage ](https://utilmeta.com/py).

![img](https://utilmeta.com/img/py.section1.png)

In this document, we will explain the corresponding usage in detail.

## Overview of ORM

One of the most common requirements in Web development is to provide RESTful interfaces to add, delete, modify and query data, and ORM (Object Relational Mapping, object-relational mapping) is a common way to map tables in relational databases to object-oriented programming (such as classes in Python). It is convenient for us to develop the interface of adding, deleting, modifying and querying to a great extent, and it also eliminates the hidden danger of SQL injection compared with SQL splicing.

We use Django ORM, which is common in Python Web, as an example of how to define a user model and a post model in a simple blog application.

```python
from django.db import models

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)

class Article(models.Model):
    author = models.ForeignKey(
        User, related_name="articles", 
        on_delete=models.CASCADE
    )
    content = models.TextField()
```

* A field of `username` type is declared `VARCHAR(20)` in the User model, and the value of the field cannot be repeated ( `unique=True`)
* A foreign key named `author` pointing to the User model is declared in the Article model to represent the author of the article. Its reverse relationship is `"articles"`, that is, it represents [all articles] of a user. When the corresponding author user is deleted, the article will be deleted in cascade ( `CASCADE`).

!!! tip

The rest of the ORM usage in this document will basically revolve around [ The Realworld Blog Project ](../../tutorials/realworld-blog) the Django model in, such as users, articles, comments, follow, etc.
## UtilMeta Declarative ORM

UtilMeta’s declarative ORM allows you to use the Schema class to declare the data structure of the expected query result in advance, and then you can directly call the method of the Schema class to query the data you need. Let’s still use the model example declared above for simple declarative ORM usage.
```python
from utilmeta.core import api, orm
from .models import User, Article
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str
```

When I declare the ORM Schema class, I need to `orm.Schema[<model_class>]` inject the corresponding ORM Schema class in the way we defined in the example.

**UserSchema**: The User model is injected, where the fields defined are

*  `username`: corresponds to the same-name field of the user model and serializes it to the `str` type
*  `articles_num`: An expression field that queries the number of articles for a user, using the `Count` inverse relationship of the expression query article author field.

**ArticleSchema**: The Article model is injected, in which the defined fields are

* A table has a primary key, `id` whether defined in the model or not, and the default name of the primary key field is
* The `author` author field, which use that previously defined UserSchema as a type declaration, indicate that the author information corresponding to the article will be directly serialized using UserSchema as the value of the entire field
*  `content`: Content field

If you declare an attribute with the same name as a model field in the Schema class, the corresponding field will be serialized according to the declared type. For a relationship field such as a foreign key, you can choose to serialize only the corresponding foreign key value, or specify a Schema class to serialize the entire relationship object. There are other field uses that we’ll look at below.

!!! tip

## `orm.Schema` methods

Now that we know `orm.Schema` the basic declaration methods, let’s introduce `orm.Schema` the important methods of classes or instances. By calling these methods, you can query, create, update, and save data in batches.

### `init` -  Single object

 `Schema.init(obj)` Method serializes the passed object parameters to ** A single Schema instance **, where the object parameters can be passed in

* The ID value, for example `ArticleSchema.init(1)`, serializes the article object with ID 1 into an ArticleSchema instance
* Incoming Model Object Instance
* Pass in a QuerySet, which serializes the objects in ** The first ** the QuerySet into a Schema instance

The first piece [ UtilMeta Framework Home Page](https://utilmeta.com/zh/py) of sample code in contains a call to `init` a method or its asynchronous variant `ainit`.

=== "Async API"
	```python
	class ArticleAPI(api.API):
	    async def get(self, id: int) -> ArticleSchema:
	        return await ArticleSchema.ainit(id)
	```
=== "Sync API"
	```python
	class ArticleAPI(api.API):
	    def get(self, id: int) -> ArticleSchema:
	        return ArticleSchema.init(id)
	```


The method in `get` the example directly passes the ID parameter of the request to the `ainit` method of ArticleSchema, which can directly serialize the article instance with ID 1.

!!! Tip “Asynchronous query method”

So if the path to the Article API is `/article`, when we access `GET/article?id=1` it, we get something like the following JSON data result
```json
{
  "id": 1,
  "author": {
    "username": "alice",
    "articles_num": 3
  },
  "content": "hello world"
}
```

This result is completely consistent with the declaration of ArticleSchema, so the core idea of declarative ORM is **What you define is what you get**

### `serialize` - List of objects

 `Schema.serialize(queryset)` It serializes a QuerySet into ** List of Schema instances **, which is a very common serialization method that is used when the API needs to return list data

When you use Django ORM, `serialize` the accepted parameter is a model-consistent Django QuerySet. For example, for ArticleSchema, the accepted parameter should be a QuerySet of the Article model. Here is an example.

=== "Async API"
	```python
	class ArticleAPI(API):
	    @api.get
	    async def feed(self, user: User = API.user_config, 
	            limit: int = utype.Param(10, ge=0, le=50)) -> List[ArticleSchema]:
	        return await ArticleSchema.aserialize(
				Article.objects.filter(author__followers=user)[:limit]
			)
	```
=== "Sync API"
	```python
	class ArticleAPI(API):
	    @api.get
	    def feed(self, user: User = API.user_config, 
	            limit: int = utype.Param(10, ge=0, le=50)) -> List[ArticleSchema]:
	        return ArticleSchema.serialize(
				Article.objects.filter(author__followers=user)[:limit]
			)
	```

The interface in `feed` the example will return the articles published by the author that the current user follows. We just need to pass the constructed QuerySet to the `ArticleSchema.serialize` method, and we will get a list with the ArticleSchema instance as the element. Finally, it is processed by the API interface as a JSON response to the client.

!!! tip
### `save` - Save to database

A `orm.Schema` ** Instance ** call is made to save the data in the data table corresponding to the model. If the Schema instance contains a primary key in the data table, the corresponding table record will be updated. Otherwise, a new table record will be created.

In addition to the default behavior based on the primary key, you can adjust `save` the behavior of the method through two parameters

*  `must_create`: If set to True, the method is forced to be processed as a creation method, although an error is thrown if the data contains a primary key that has already been created.
*  `must_update`: If set to True, the method is forced to be processed as an update method, and an error is thrown when the update cannot be completed, such as when the primary key is missing or does not exist.

The following example shows `save` the use of the method in the interface by writing and creating the article API.

=== "Async API"
	```python  hl_lines="12"
	from utilmeta.core import orm
	from .models import Article
	
	class ArticleCreation(orm.Schema[Article]):
	    content: str
	    author_id: int = orm.Field(no_input=True)
	
	class ArticleAPI(API):
	    async def post(self, article: ArticleCreation = request.Body, 
	                   user: User = API.user_config):
	        article.author_id = user.pk
	        await article.asave()
	        return article.pk
	```
=== "Sync API"
	```python  hl_lines="12"
	from utilmeta.core import orm
	from .models import Article
	
	class ArticleCreation(orm.Schema[Article]):
	    content: str
	    author_id: int = orm.Field(no_input=True)
	
	class ArticleAPI(API):
	    def post(self, article: ArticleCreation = request.Body, 
	            user: User = API.user_config):
	        article.author_id = user.pk
	        article.save()
	        return article.pk
	```

In this example, we first define the ArticleCreation class, which includes a content field `content` and an author field `author_id`, where the author field is `no_input=True` configured not to accept input from the client, because typically for this content-authoring interface, The Current Requesting User is directly used as the Author field of the new content, so there is no need for the client to provide

In the `post` method, we also assign the primary key of the current user to the field requesting data `author_id` through attribute assignment, and then call the save method of the Schema instance, which will save the data in the database. And assign the primary key value of the new record to the attribute of the Schema instance `pk`

### `bulk_save` - Save data in batch

A ** List ** data `Schema.bulk_save(data)` will be saved in batch. Each element in the list should be a Schema instance or dictionary data conforming to the Schema declaration. This method will perform batch creation or batch update according to the data group of each element.

The following is an example of an interface for creating users in bulk

=== "Async API"
	```python  hl_lines="10"
	from utilmeta.core import api, orm, request
	from .models import User
	
	class UserSchema(orm.Schema[User]):
	    username: str
	
	class UserAPI(api.API):
	    @api.post
	    async def bulk(self, data: List[UserSchema] = request.Body):
	        await UserSchema.abulk_save(data)
	```
=== "Sync API"
	```python   hl_lines="10"
	from utilmeta.core import api, orm, request
	from .models import User
	
	class UserSchema(orm.Schema[User]):
	    username: str
	
	class UserAPI(api.API):
	    @api.post
	    def bulk(self, data: List[UserSchema] = request.Body):
	        UserSchema.bulk_save(data)
	```

The method in the example uses `List[UserSchema]` the type declaration as the body of the request, indicating that it accepts a list of JSON data. The interface will automatically parse and convert it into a list of UserSchema instances. You only need to call `UserSchema.bulk_save` the method to create or update the data in this list in batches.

!!! tip
 
### `commit` - Update the queryset

A `orm.Schema` ** Instance ** call to batch update the data in it to all records covered by the query set

### Asynchronous methods

When you call `orm.Schema` the asynchronous method of, for example `ainit` `asave` `aserialize`, UtilMeta, the underlying UtilMeta will implement the asynchronous query. Generally speaking, in the asynchronous API function, The asynchronous methods you should use `orm.Schema`, such as

```python hl_lines="3"
class ArticleAPI(api.API):
    async def get(self, id: int) -> ArticleSchema:
        return await ArticleSchema.ainit(id)
```

But even if you call a `orm.Schema` synchronous method in an asynchronous function, such as

```python hl_lines="3"
class ArticleAPI(api.API):
    async def get(self, id: int) -> ArticleSchema:
        return ArticleSchema.init(id)
```

The interface in the example can still process requests normally, but because Django’s native query engine does not support direct execution in an asynchronous environment, synchronous queries in the asynchronous interface are processed by a thread in the thread pool on the Django implementation

Although UtilMeta’s declarative ORM will automatically adjust the execution strategy based on the asynchronous environment and ORM engine running, if you use Django’s synchronous method query directly in the asynchronous function, there will be errors, such as

```python hl_lines="4"
class ArticleAPI(api.API):
    @api.get
    async def exists(self, id: int) -> bool:
        return Article.objects.filter(id=id).exists()
```

You will get the following errors
```
SynchronousOnlyOperation: You cannot call this from an async context 
- use a thread or sync_to_async.
```

Because Django’s synchronous query methods use a query engine that is strictly dependent on the current thread, you should use their asynchronous variants (prepended `a` to the method name).
```python hl_lines="4"
class ArticleAPI(api.API):
    @api.get
    async def exists(self, id: int) -> bool:
        return await Article.objects.filter(id=id).aexists()
```

## Relational query

It is a very common Web development requirement to return the information of relational objects when querying. For example, the corresponding author information is required when returning articles, and the corresponding product information is required when returning orders. These can be collectively referred to as relational queries. UtilMeta’s declarative ORM can handle such queries very concisely. The corresponding usage is described in detail below.

### Relation field

You can query only one field of a relational object, and the way to declare it is very simple, as follows.

```python
class ArticleSchema(orm.Schema[Article]):
    author_name: str = orm.Field('author.username')
```

In the `author_name` example, the field is declared `'author.username'` as the value of the query field to query `author` the field of `username` the user corresponding to the foreign key.

In addition to foreign keys, you can also query a single field in a multi-pair relationship, but you need to use a list type as the type hint for the field, as shown in
```python

class ArticleSchema(orm.Schema[Article]):
    tag_list: List[str] = orm.Field('tags.name')
```

The Article model has a `'tags'` many-to-many relationship named pointing to a Tag model with `name` fields, so you can use `'tags.name'` to serialize the fields of `name` all the tags associated with the article into a list of strings.

Of course, if you use it `orm.Field('tags')`, it will query the primary key value list of all the associated tags.

### Relation object

The common way of relational query is to serialize the whole associated object according to a certain structure, such as the article-author ( `author`) field in the above example. The way to query the relational object is very simple, that is, to declare the expected query structure `orm.Schema` as the type of the relational field.

For a ** Foreign key ** field, there is only one relationship object, so you can specify the Schema class directly, such as

```python  hl_lines="11"
from utilmeta.core import orm
from .models import User, Article
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str
```
The field of `author` ArticleSchema directly specifies UserSchema as the type declaration, and the field will get the corresponding UserSchema instance when `author` serialized.

!!! Warning “Use Optional”

For ** Many-to-many/one-to-many ** fields such as may contain multiple relational objects, you should use `List[Schema]` as the type declaration, such as

```python hl_lines="12"
from utilmeta.core import api, orm
from .models import User, Article
from django.db import models

class ArticleSchema(orm.Schema[Article]):
    id: int
    author_name: str = orm.Field('author.username')
    content: str

class UserSchema(orm.Schema[User]):
    username: str
    articles: List[ArticleSchema]
```

The `articles` field in UserSchema is `List[ArticleSchema]` specified as a type declaration, and when serialized, the `articles` field gets a list of all articles authored by the user (if not, an empty list).

!!! Note “Automatically optimize execution to avoid N + 1 problems”
	```python
	for user in user_queryset:
		articles = Article.objects.filter(author=user).values()
	```

### Relational query function

If we need to query a list of articles, each article object also needs to return the two comments with the highest number of likes. Can such a requirement be implemented by declarative ORM? The answer is yes, just use the relational query function

The relational query function provides a function hook that can be customized. You can write any condition for the relational query, such as adding filtering and sorting conditions, controlling the quantity, etc. The relational query function can be declared in the following ways

#### Single primary-key function
The function accepts a single primary key in the target query set as input, and returns the query set of a relational model. Let’s take a requirement as an example: we need to query a list of users, each of whom needs to be attached ** 2 articles with the most likes **. The code example for implementation is as follows
```python
class ArticleSchema(orm.Schema[Article]):
    id: int
    content: str
    
class UserSchema(orm.Schema[User]):
    username: str
    top_2_articles: List[ArticleSchema] = orm.Field(
		lambda user_id: Article.objects.annotate(
            favorites_num=models.Count('favorited_bys')
        ).filter(
			author_id=user_id
		).order_by('-favorites_num')[:2]
	)
```

In this example, the field of `top_2_articles` UserSchema specifies a relational query function, which accepts a primary key value of the target user and returns the corresponding article query set. After that, UtilMeta will complete the serialization and result distribution according to the type declaration ( `List[ArticleSchema]`) of the field

** Optimized compression of a single relationship object ** Looking at the above example, we can clearly see that in order to get the conditional relation value of the target, the query in the function needs to run N times, N is the length of the target query set, so what can be compressed into a single query? The answer is that when you only need to query ** 1 ** the target relational object, you can directly declare the query set, and UtilMeta will process it into a subquery to compress it into a single query, such as

```python
class ArticleSchema(orm.Schema[Article]):
    id: int
    content: str
    
class UserSchema(orm.Schema[User]):
    username: str
    top_article: Optional[ArticleSchema] = orm.Field(
        Article.objects.annotate(
            favorites_num=models.Count('favorited_bys')
        ).filter(
			author_id=models.OuterRef('pk')
		).order_by('-favorites_num')[:1]
	)
```

!!! tip “OuterRef”

#### Primary-Key List Function
Let’s take another requirement as an example. Suppose we need to query a list of users, in which each user needs to attach “which followers of the current requesting user follow the target user”, which is a common requirement in social media such as Weibo and Twitter (X). In the front end, it will probably be displayed as “you follow A, B also follows him” or “Followers you known” ”, so the requirement can be simply and efficiently implemented by using the primary key list function.

```python
class UserSchema(orm.Schema[User]):
    username: str
    
	@classmethod
	def get_runtime_schema(cls, user_id):
		def get_followers_you_known(*pks):
			mp = {}
			for val in User.objects.filter(
				followings__in=pks,
				followers=user_id
			).values('followings', 'pk'):
				mp.setdefault(val['followings'], []).append(val['pk'])
			return mp

		class user_schema(cls):
			followers_you_known: List[cls] = orm.Field(
				get_followers_you_known
			)
		return user_schema
```

In the example, UserSchema defines a class function that can generate different queries for different requesting users, in which we define a `get_followers_you_known` query function that accepts a list of primary keys and constructs a dictionary whose key is a primary key from the list of primary keys passed in. The corresponding value is the primary key list of the target relationship (Followers you known) user. After this dictionary is returned, UtilMeta will complete the subsequent aggregate query and result distribution. Finally, the field of each user Schema instance `followers_you_known` will contain the query results that meet the condition requirement

!!! Tip “Dynamic Schema Query”

### Query Expression

Aggregation or calculation of a relational field is also a common development requirement, such as

* Query how many followers or followed people a user has
* Find out how many people liked, viewed and commented on the article
* Inquire how many orders there are for the product

Almost all models with relational fields require a query for the number of correspondences. For Django ORM, you can use `models.Count('<relation_name>')` to query the number of correspondences, such as in the example above.
```python
from utilmeta.core import orm
from .models import User
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')
```

The `articles_num` UserSchema field is used `models.Count('articles')` to indicate the number of query `'articles'` relationships, that is, how many articles a user has created.

In addition to quantities, expression queries can be used for some common data calculations, such as

*  `models.Avg` Average calculation, such as calculating the average rating of a store or product
*  `models.Sum` Summation calculation, such as calculating the total sales of a commodity.
*  `models.Max`: Maximum value calculation
*  `models.Min`: Minimum value calculation

!!! tip

Here are some expression types that are commonly used in real-world development
#### `Exists`
Sometimes you need to return the field of whether a conditional query set exists, for example, when querying a user, you can use `Exists` an expression to return [whether the user currently requested has followed the user].

```python
from utilmeta.core import orm
from django.db import models

class UserSchema(orm.Schema[User]):
    username: str
    following: bool = False

    @classmethod
    def get_runtime(cls, user_id):
        class user_schema(cls):
            following: bool = models.Exists(
				Follow.objects.filter(
					following=models.OuterRef('pk'), 
					follower=user_id
				)
			)
        return user_schema
```
#### `SubqueryCount`
For some relation counts you may need to add some conditions, for example, when querying an article, you need to return [how many of the current user’s followers like the article], in which case you can use `SubqueryCount` expressions.

```python
from utilmeta.core.orm.backends.django import expressions as exp

class ArticleSchema(orm.Schema[Article]):
    id: int
    content: str
    
    @classmethod
    def get_runtime_schema(cls, user_id):
        class article_schema(cls):
            following_likes: int = exp.SubqueryCount(
                User.objects.filter(
                    followers=user_id,
                    likes=exp.OuterRef('pk')
                )
            )
        return article_schema
```

## `orm.Schema` usage

This section will introduce `orm.Schema` common usage and application techniques.

### `orm.Field` parameters

Each field `orm.Schema` declared in can be specified `orm.Field(...)` as a property value to configure the behavior of the field. Common field configuration parameters are

The first is the first parameter `field`. When the field you want to query is not in the current model (cannot be directly represented as the attribute name of Schema class), you can use this parameter to specify the field value you want to query. The above example has shown the relevant usage, such as

* Pass in a relational query field, such as
* Pass in a relational query function, such as
* Pass in a query set
* Pass in a query expression, such as

In addition to the first parameter, you can use the following parameters to implement more field behaviors

*  `no_input`: Set to True to ignore the field input. For example, when creating an article `author_id`, the field should not be provided by the request data, but should be assigned to the user ID of the current request in the API function, so it needs to be declared.
*  `no_output`: Set to True to ignore the field output. For example, when creating an article, the request data can be required to contain a list of tags, but it does not need to be saved in the article model instance. Instead, the creation and assignment of tags are handled in the API function. At this time, it can be declared.
*  `mode` You can specify a schema for a field so that the field only works in the corresponding schema. In this way, you can use a Schema class to handle various scenarios [ The Realworld Blog Project ](tutorials/realworld-blog) such as query, create, update, etc. Detailed examples of the use of the field schema are given in.

!!! Tip “field parameter configuration”

###  `@property` field
You can use the attribute fields of the Schema class `@property` to quickly develop fields that are calculated based on the query result data, such as

```python
from datetime import datetime

class UserSchema(orm.Schema[User]):
    username: str
	signup_time: datetime
	
	@property  
	def joined_days(self) -> int:  
	    return int((datetime.now() - self.signup_time).total_seconds() / (3600 * 24))
```

In the `joined_days` example, the attribute calculates the number of days the user has registered through the user’s registration time and outputs it as the value of the field.

### Schema Inheritance
 `orm.Schema` Classes can also reuse declared fields using class inheritance, composition, etc. For example,
```python
from utilmeta.core import orm
from .models import User

class UsernameMixin(orm.Schema[User]):
    username: str = orm.Field(regex='[A-Za-z0-9_]{1,20}')

class UserBase(UsernameMixin):
    bio: str
    image: str

class UserLogin(orm.Schema[User]):
    email: str
    password: str

class UserRegister(UserLogin, UsernameMixin): pass
```

In the example we defined

*  `UsernameMixin`: contains `username` only one field, which can be reused by other Schema classes
*  `UserBase`: Inherit UsernameMixin and return the basic information of the user
*  `UserLogin`: Parameters required for user login
*  `UserRegister`: The parameter required for user registration is the combination of the login parameter UserLogin and the UsernameMixin containing the username parameter.

All of the above Schema classes can be used and queried independently
#### Model inheritance

Django models can reuse model fields using class inheritance, such as
```python
from django.db import models

class BaseContent(models.Model):
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        
class Article(BaseContent):
    slug = models.SlugField(db_index=True, max_length=255, unique=True)
    title = models.CharField(db_index=True, max_length=255)
    description = models.TextField()
    author = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='articles')
    tags = models.ManyToManyField(Tag, related_name='articles')

class Comment(BaseContent):
    article = models.ForeignKey(Article, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='comments')
```

In the above example, the repeated fields in the Article model and Comment model are integrated into the `BaseContent` abstract model. Similar techniques can be used to reuse fields in the ORM Schema class. For the Schema base class, you can not specify the model. Inject at inheritance time, such as
```python
from utype.types import *
from utilmeta.core import orm
from domain.user.schema import UserSchema
from .models import Comment, Article

class ContentSchema(orm.Schema):
    body: str
    created_at: datetime
    updated_at: datetime
    author: UserSchema
    author_id: int = orm.Field(mode='a', no_input=True)

class CommentSchema(ContentSchema[Comment]):
    id: int = orm.Field(mode='r')
    article_id: int = orm.Field(mode='a', no_input=True)

class ArticleSchema(ContentSchema[Article]):
    id: int = orm.Field(no_input=True)
    slug: str = orm.Field(no_input='aw', default=None, defer_default=True)
    title: str = orm.Field(default='', defer_default=True)
    description: str = orm.Field(default='', defer_default=True)
```

In the example, we define the ContentSchema base class, which hosts the common data structure in articles and comments, but does not inject the model. CommentS chema and ArticleSchema declared later inherit from it and inject the corresponding model.

!!! warning

## `orm.Query` parameters

UtilMeta’s declarative ORM also supports query parameters of the declarative model, such as filter conditions, sorting, quantity control, etc. The following is a simple example. You can directly add ID and author filter parameters to the query interface of the article.

= = = “Async API”
	```python
	from utilmeta.core import orm
	
	class ArticleQuery(orm.Query[Article]):
		id: int
		author_id: int
	
	class ArticleAPI(api.API):
		async def get(self, query: ArticleQuery) -> List[ArticleSchema]:
			return await ArticleSchema.aserialize(query)
	```
= = = “Sync API”
	```python
	from utilmeta.core import orm
	
	class ArticleQuery(orm.Query[Article]):
		id: int
		author_id: int
	
	class ArticleAPI(api.API):
		def get(self, query: ArticleQuery) -> List[ArticleSchema]:
			return ArticleSchema.serialize(query)
	```

We use a similar `orm.Schema` syntax to `orm.Query[<model>]` declare the query parameters of a model, and the declared Query class will be automatically processed as the query parameters of the request ( `request.Query`) when it is used in the type declaration of API function parameters. You can pass an instance of it directly to `orm.Schema` a `serialize` method in a function to serialize the corresponding query result.

### Filter params

The field declared in `orm.Query` the class, if it has the same name in the model, will be automatically processed as a filter parameter. When the request provides this filter parameter, the corresponding condition will be added to the target query. For example, when the request is made `GET/article?author_id=1`, You’ll get `author_id=1` a set of article queries.

When you need to define more complex query parameters, you need to use `orm.Filter` components. Here is an example of the common use of filter parameters.

```python
from utilmeta.core import orm
from datetime import datetime
from django.db import models

class ArticleQuery(orm.Query[Article]):
	author: str = orm.Filter('author.username')
	keyword: str = orm.Filter('content__icontains')
	favorites_num: int = orm.Filter(models.Count('favorited_bys'))
	within_days: int = orm.Filter(query=lambda v: models.Q(
        created_at__gte=datetime.now() - timedelta(days=v)
    ))

class ArticleAPI(api.API):
	def get(self, query: ArticleQuery) -> List[ArticleSchema]:
		return ArticleSchema.serialize(query)
```

The `orm.Filter` first parameter can specify the name of the query field, and several types are shown in the example.

*  `author`: Query the relationship field `'author.username'`, which is the user name of the author user
*  `keyword`: The query field `content` case-insensitively contains ( `icontains`) the target parameter, i.e., a simple search
*  `favorites_num`: The query field is a relational count expression `models.Count('favorited_bys')`, that is, the number of likes.

In addition, `orm.Filter` you can specify a query expression with `query` a parameter, receive a parameter (that is, the corresponding query parameter value in the request), and return a query expression, which should be an `models.Q` expression in Django. It can contain custom query conditions, such as the `within_days` query in the example of articles within a few days of creation.

!!! tip

Inherits from the `utype.Field` `orm.Field` `orm.Filter` same as, so other field configurations are still valid, such as

*  `required`: Required. The default `orm.Filter` is `required=False` yes, which means it is a non-required parameter. The corresponding query condition will be applied only when it is requested to be provided.
*  `default`: Specify default values for query parameters
*  `alias`: Specify an alias for the query parameter

### Sorting params

Fields used to control the sorting of query results can also be declared in the `orm.Query` class. You can declare the supported sorting fields and the corresponding configuration. Examples are as follows
```python
from utilmeta.core import orm
from django.db import models
from .models import Article

class ArticleQuery(orm.Query[Article]):
	order: List[str] = orm.OrderBy({
        "comments_num": orm.Order(field=models.Count("comments")),
        "favorited_num": orm.Order(field=models.Count("favorited_bys")),
        Article.created_at: orm.Order(),
    })

class ArticleAPI(api.API):
	def get(self, query: ArticleQuery) -> List[ArticleSchema]:
		return ArticleSchema.serialize(query)
```

First, the sort parameter needs to use a `orm.OrderBy` field declaration, in which a dictionary is defined to declare the sort option. The key of the dictionary is the name of the sort option, and the value is the configuration of the sort.

After the sort parameter is declared, the client can pass in a list of sort options. The sort options are selected from the declaration of the sort parameter. You can add `-` a (minus sign) before the options to indicate that they are sorted in reverse order. For example, for the above example, when the client requests `GET/article?order=-favorited_num,created_at`, the detected sort options are

1.  `-favorited_num`: Sort in reverse order of the number of people you like. The more people you like, the higher you are.
2.  `created_at`: Sorted in positive order of creation time, the earlier, the higher

Each of the sort options supported by the sort parameter can be configured by `orm.Order`. The supported parameters are

*  `field`: The sorting target field or expression can be specified. If the name of the corresponding sorting option is the name of the model field, it can not be specified (such as in `created_at` the example).
*  `asc`: Whether positive sequence is supported. The default value is True. If it is set to False, positive sequence is not provided.
*  `desc`: Whether reverse order is supported. The default value is True. If it is set to False, reverse order is not supported.
* Specify a documentation string `document` for the sort field that will be incorporated into the API documentation.

In sorting, there is a kind of value that is more difficult to handle, that is, null value. When querying, the result of null field value should be arranged at the top, and at the end, it should be filtered out, which is determined by the following parameters

*  `notnull`: Whether to filter out the null instances of this field. The default is False.
*  `nulls_first`: sort the instances with null values in the sort field first (first in forward order, last in reverse order)
*  `nulls_last`: sort the instances with null values in the sort field last (forward last, reverse first)

If none of these parameters are specified, the sorting of instances with null sort fields will be determined by the database

### Paging params

In actual development, we are unlikely to return hundreds of records hit by the query at one time. Instead, we need to provide ** Paging control ** a mechanism. `orm.Query` The class also supports defining several preset paging parameters so that you can quickly implement the paging query interface. The following is an example.

```python
from utilmeta.core import orm
from django.db import models
from .models import Article

class ArticleQuery(orm.Query[Article]):
	offset: int = orm.Offset(default=0)
    limit: int = orm.Limit(default=20, le=100)

class ArticleAPI(api.API):
	def get(self, query: ArticleQuery) -> List[ArticleSchema]:
		return ArticleSchema.serialize(query)
```

The two paging control parameters defined in the example are as follow

*  `offset`: Specify a `orm.Offset` field to control the starting offset of the query. For example, if the client has queried 30 results, the next request will be sent `?offset=30` to query the results after 30.
*  `limit`: Specify a `orm.Limit` field to control the limit of the number of results returned by the query. The default value is 20, that is, the maximum number of results returned is 20 when no parameter is provided. The maximum value is 100. The requested parameter cannot be greater than this value.

For example, when the client requests `GET/article?offset=10&limit=30`, it will return 10 to 40 of the query results.

In addition to the offset/limit mode, there is another way for the client to pass the “number of pages” of the page directly, such as

```python
from utilmeta.core import orm
from django.db import models
from .models import Article

class ArticleQuery(orm.Query[Article]):
	page: int = orm.Page()
    rows: int = orm.Limit(default=20, le=100)

class ArticleAPI(api.API):
	def get(self, query: ArticleQuery) -> List[ArticleSchema]:
		return ArticleSchema.serialize(query)
```

The parameter in `page` the example specifies a `orm.Page` field, which exactly corresponds to the concept of the number of pages in the front end and starts counting from 1. For example, when the client requests `GET/article?page=2&rows=10`, it will return 10 to 20 items in the query results, that is, “Page 2“ in the client data.

#### `count()` Total number of results

In order to enable the client to display the total number of pages queried, we often need to return the total number of results queried (ignoring the paging parameter). To address this requirement, `orm.Query` the instance provides a `count()` method (asynchronous variant is `acount ())

The following demonstrates how the post pagination interface for a blog project is handled

= = = “Async API”
	```python hl_lines="17"
	from utilmeta.core import orm, api, response
	
	class ArticlesResponse(response.Response):
	    result_key = 'result'
	    count_key = 'count'
	    result: List[ArticleSchema]
	    
	class ArticleAPI(api.API):
	    class ListArticleQuery(orm.Query[Article]):
	        author: str = orm.Filter('author.username')
	        offset: int = orm.Offset(default=0)
	        limit: int = orm.Limit(default=20, le=100)
	
	    async def get(self, query: ListArticleQuery) -> ArticlesResponse:
	        return ArticlesResponse(
	            result=await ArticleSchema.aserialize(query),
	            count=await query.acount()
	        )
	```
= = = “Sync API”
	```python  hl_lines="17"
	from utilmeta.core import orm, api, response
	
	class ArticlesResponse(response.Response):
	    result_key = 'result'
	    count_key = 'count'
	    result: List[ArticleSchema]
	    
	class ArticleAPI(api.API):
	    class ListArticleQuery(orm.Query[Article]):
	        author: str = orm.Filter('author.username')
	        offset: int = orm.Offset(default=0)
	        limit: int = orm.Limit(default=20, le=100)
	
	    def get(self, query: ListArticleQuery) -> ArticlesResponse:
	        return ArticlesResponse(
	            result=ArticleSchema.serialize(query),
	            count=query.count()
	        )
	```

In the example, we use the response template to define a nested response structure, including the query result ( `result`) and the total number of queries ( `count`), and the corresponding list data serialized using ArticleSchema is also passed in the function. Total number of results from the and calls `query.count()`

When the client receives the `count` data, it can calculate the total number of pages displayed.
```js
let pages = Math.ceil(count / rows)
```

### Field Control Params
UtilMeta also provides a result field control mechanism similar to GraphQL, which allows the client to select which fields to return or which fields to exclude, so as to further optimize the query efficiency of the interface. Examples are as follows

```python hl_lines="18"
from utilmeta.core import orm
from .models import User, Article
from django.db import models
from datetime import datetime

class UserSchema(orm.Schema[User]):
    username: str
    articles_num: int = models.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str
    created_at: datetime
    favorites_count: int = models.Count('favorited_bys')
    
class ArticleQuery(orm.Query[Article]):
	scope: List[str] = orm.Scope()
	exclude: List[str] = orm.Scope(excluded=True)

class ArticleAPI(api.API):
	def get(self, query: ArticleQuery) -> List[ArticleSchema]:
		return ArticleSchema.serialize(query)
```

In ArticleQuery, we define a `scope` `orm.Scope` parameter named, which can be used by the client to specify a list of fields, so that the result only returns the fields in the list. For example, the request `GET/article?scope=id,content,created_at` will only return `id`, `content` and the `created_at` field

Another `exclude` parameter is also used `orm.Scope`, but it is specified `excluded=True` in it, which means that the field given in the parameter will be excluded, and the request `GET/article?exclude=author` will return the result data without the `author` field.

!!! tip

### `get_queryset`

For `orm.Query` an instance, in addition to being serialized directly as `serialize` a parameter to a method such as, you can also call its `get_queryset` method to get the generated query set, such as a Django QuerySet for a Django model.

 `get_queryset` Method can also accept a base _ queryset parameter, and the filtering, sorting, and paging effects contained in the query parameter can be added to the query set

```python  hl_lines="11"
class ArticleAPI(API):
    class ListArticleQuery(orm.Query[Article]):
        author: str = orm.Filter('author.username', required=True)
        offset: int = orm.Offset(default=0)
        limit: int = orm.Limit(default=20, le=100)
        scope: dict = orm.Scope()

    @api.get
    async def list(self, query: ListArticleQuery):
        return await ArticleSchema.aserialize(
			queryset=query.get_queryset(
				Article.objects.exclude(comments=None)
			),
			context=query.get_context()
		)
```


In the example, we use the `query.get_queryset` method to get the query set generated by the query parameters, and pass in a custom base QuerySet to pass the results of the generated query set to the parameters of the serialization method `queryset`.

!!! tip

## Database and ORM configuration

We have introduced the usage of UtilMeta declarative ORM, but if you need to access the database, you need to complete the configuration of the database and ORM.

As a meta-framework, UtilMeta’s declarative ORM is able to support a range of ORM engines implemented as a model layer. The current support status is

* **Django ORM**：**Fully supported**
* Tortoise-orm: support coming soon
* Peewee: Upcoming support
* Sqlachemy: coming soon

So let’s take Django ORM as an example of how to configure database connections and models.

First assume that your project is created using the following command
```shell
meta setup blog --temp=full
```

The folder structure is similar
```
/blog
	/config
		conf.py
		service.py
	/domain
		/article
			models.py
		/user
			models.py
	/service
		api.py
	main.py
	meta.ini
```

You can configure the following code in `config/conf.py`

=== “config/conf.py”
	```python
	from utilmeta import UtilMeta
	from config.env import env
	
	def configure(service: UtilMeta):
	    from utilmeta.core.server.backends.django import DjangoSettings
	    from utilmeta.core.orm import DatabaseConnections, Database
	
	    service.use(DjangoSettings(
	        apps_package='domain',
	        secret_key=env.DJANGO_SECRET_KEY
	    ))
	    service.use(DatabaseConnections({
	        'default': Database(
	            name='db',
	            engine='sqlite3',
	        )
	    }))
	    service.setup()
	```
=== “config/sevice.py”
	```python
	from utilmeta import UtilMeta
	from config.conf import configure
	from config.env import env
	import starlette
	
	service = UtilMeta(
	    __name__,
	    name='blog',
	    backend=starlette,
	    production=env.PRODUCTION,
	)
	configure(service)
	```

We define the `configure` function in `config/conf.py` to configure the service, receive `UtilMeta` the service instance of the type, and use `use()` the method to configure it.

To use Django ORM, you need to complete the configuration of Django. UtilMeta provides `DjangoSettings` an easy way to configure Django. The important parameters are

*  `apps_package`: Specify a directory in which each folder will be treated as a Django App, and Django will scan the `models.py` files in it to detect all models, such as in the example.
*  `apps` You can also specify a list of Django App references to single out all model directories, such as
*  `secret_key` Specify a key, which you can manage using environment variables.

### Database connection

In UtilMeta, you can use `DatabaseConnections` to configure the database connection, where you can pass in a dictionary. The key of the dictionary is the name of the database connection. We follow the syntax of Django to define the database connection, and use `'default'` to represent the default connection. The corresponding value is an `Database` instance that is used to configure a specific database connection, and the parameters include

*  `name`: The name of the database (in SQLite3, the name of the database file)
*  `engine`: Database engine, Django ORM supported engines are `sqlite3`, `mysql`,
*  `user`: Username of the database
*  `password`: The user password for the database
*  `host`: Host of the database, local by default ( `127.0.0.1`)
*  `port`: The port number of the database, which is determined by the type of the database by default, such as `mysql` 3306 `postgresql` or 5432

!!! tip “SQLite3”


**PostgreSQL / MySQL**

When you need to use PostgreSQL or MySQL connections that require a database password, we recommend that you use environment variables to manage this sensitive information. Examples are as follows

=== “config/conf.py”
	```python
	from utilmeta import UtilMeta
	from config.env import env
	
	def configure(service: UtilMeta):
		from utilmeta.core.server.backends.django import DjangoSettings
		from utilmeta.core.orm import DatabaseConnections, Database
	
		service.use(DjangoSettings(
			apps_package='domain',
			secret_key=env.DJANGO_SECRET_KEY
		))
		service.use(DatabaseConnections({
	        'default': Database(
	            name='blog',
	            engine='postgresql',
	            host=env.DB_HOST,
	            user=env.DB_USER,
	            password=env.DB_PASSWORD,
	            port=env.DB_PORT,
	        )
	    }))
		service.setup()
	```
=== “config/env.py”
	```python
	from utilmeta.conf import Env
	
	class ServiceEnvironment(Env):
	    PRODUCTION: bool = False
	    DJANGO_SECRET_KEY: str = ''
	    DB_HOST: str = '127.0.0.1'
	    DB_PORT: int = None
	    DB_USER: str
	    DB_PASSWORD: str
	
	env = ServiceEnvironment(sys_env='BLOG_')
	```


In `config/env.py`, we declare the key information required for the configuration and pass `sys_env='BLOG_'` it in the initialization parameter, which means that `BLOG_` the environment variable with the prefix will be picked up, so you can specify an environment variable like

```env
BLOG_PRODUCTION=true
BLOG_DJANGO_SECRET_KEY=your_key
BLOG_DB_USER=your_user
BLOG_DB_PASSOWRD=your_password
```

After initialization `env`, it will resolve the environment variables to the corresponding attributes and complete the type conversion, and you can use them directly in the configuration file.

### Django Migration

When we have written the data model, we can use the migration command provided by Django to easily create the corresponding data table. If you use SQLite, you do not need to install the database software in advance. Otherwise, you need to install PostgreSQL or MySQL database to your computer or online environment first. Then create a database with the same configuration `name` as your connection. After the database is ready, you can use the following command to complete the data migration.

```shell
meta makemigrations
meta migrate
```

Migration is successful when you see the following output

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

For SQLite database, the corresponding database files and data tables will be created directly, while for other databases, the corresponding data tables will be created according to your model definition

!!! Tip “Database Migration Commands”

### Asynchronous query

Asynchronous queries do not require additional configuration, but depend on how you call them. If you use `orm.Schema` asynchronous methods such as `ainit`, `aserialize` `asave`, etc., then the implementation of asynchronous queries will be called internally.

Each method in Django ORM also has a corresponding asynchronous implementation, but in fact it only uses `sync_to_async` methods to turn the synchronous function into an asynchronous function as a whole, and its internal query logic and driver implementation are still all synchronous and blocking.


**AwaitableModel**

UtilMeta ORM completes the pure asynchronous implementation of all methods in Django ORM, and uses [ encode/databases ](https://github.com/encode/databases) the library as the asynchronous driver of each database engine to maximize the performance of asynchronous queries. The model base class hosting this implementation is located in

```python
from utilmeta.core.orm.backends.django.models import AwaitableModel
```

If your Django model is self-integrated `AwaitableModel`, all of its ORM methods will be implemented completely asynchronously.

!!! warning “ACASCADE”

In fact, encode/databases also integrates the following asynchronous query drivers respectively

* [asyncpg](https://github.com/MagicStack/asyncpg)
* [aiopg](https://github.com/aio-libs/aiopg)
* [aiomysql](https://github.com/aio-libs/aiomysql)
* [asyncmy](https://github.com/long2ice/asyncmy)
* [aiosqlite](https://github.com/omnilib/aiosqlite)

So if you need to specify the asynchronous query engine when you select the database, you can pass it in the `engine` parameter `sqlite3+aiosqlite`. `postgresql+asyncpg`

### Transaction plugin

Transaction is also a very important mechanism for data query and operation, which guarantees the atomicity of a series of operations (either overall success or overall failure does not affect).

In UtilMeta, you can use `orm.Atomic` an interface decorator to enable database transactions for an interface, and we have shown the corresponding usage in the example of creating an interface in the article.

```python hl_lines="4"
from utilmeta.core import orm

class ArticleAPI(API):
    @orm.Atomic('default')
    async def post(self, article: ArticleSchema[orm.A] = request.Body, 
                   user: User = API.user_config):
        tags = []
        for name in article.tag_list:
            tag, created = await Tag.objects.aget_or_create(name=name)
            tags.append(tag)
        article.author_id = user.pk
        await article.asave()
		if self.tags:
            # create or set tags relation in creation / update
            await self.article.tags.aset(self.tags)
```

The post interface in this example also needs to complete the creation and setting of tags when creating articles. We directly use `@orm.Atomic('default')` the decorator on the interface function to indicate that the transaction is opened for the `'default'` database (corresponding `DatabaseConnections` to the defined database connection). If this function completes successfully, the transaction is committed, and if any errors occur ( `Exception`), the transaction is rolled back

So in the example, the article and tag are either created and set successfully at the same time, or the overall failure has no effect on the data in the database.


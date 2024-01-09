# Schema query and ORM

UtilMeta implements a unique and efficient declarative Schema query mechanism to quickly implement add, delete, modify and query operations and develop RESTful interfaces. We will describe the corresponding usage in detail below


* init
* serialize
* save
* bulk_save
* commit

All the above methods have corresponding asynchronous methods, which can be added `a` before the method name. For example `ainit`, `asave` asynchronous ORM needs the support of asynchronous query library. UtilMeta uses the encode/databases library by default to provide asynchronous query support for mainstream databases.


## Data request parameters

### Query parameters

Filter

### Sorting parameters

OrderByOrder

### Paging parameters

* offset
* limit
* page

### Result control parameter



### Database configuration

* django
* Tortoise-orm (asynchronous ORM, similar to Django syntax)
* peewee
* sqlachemy



### Django ORM

Reference [ Django Model documentation ](https://docs.djangoproject.com/en/3.2/topics/db/models/ )

Because Django does not have a native asynchronous query implementation (its database queries are all synchronous operations), UtilMeta implements a set of Django native asynchronous interfaces (based on asynchronous database query libraries, such as encode/databases), which can be used to the greatest extent.

### Tortoise-ORM
https://github.com/tortoise/tortoise-orm

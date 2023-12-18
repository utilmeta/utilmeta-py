# 数据查询与序列化



* init
* serialize
* save
* bulk_save
* commit

以上方法都有对应的异步方法，只需在方法名前加 `a` 即可，如 `ainit`, `asave` 
异步 ORM 需要有异步查询库的支持，UtilMeta 默认使用 encode/databases 库为主流的数据库提供异步查询支持


## 数据请求参数

### 查询参数

Filter

### 排序参数

OrderBy
Order

### 分页参数

* offset
* limit
* page

### 结果控制参数





### 数据库配置

* django
* tortoise-orm（异步 ORM，类似 django 语法）
* peewee
* sqlachemy





### Django ORM

参考 [Django Model 文档](https://docs.djangoproject.com/en/3.2/topics/db/models/ )

由于 django 没有原生的异步查询实现（其数据库查询都是同步操作），UtilMeta 实现了一套 django 原生异步接口（底层基于异步数据库查询库，如 encode/databases），能够最大程度利用


### Tortoise-ORM
https://github.com/tortoise/tortoise-orm

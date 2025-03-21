# 版本发布记录

## v2.7.5

发布时间：2025/3/21

### 新特性

* ·Operations 系统支持配置 `connection_key` 对本地或内网的直连管理模式请求进行鉴权，配置 `connection_key` 与 `private_scope` 参数后可以在 UtilMeta 管理平台中直接管理与客户端位于同一内网的 UtilMeta 服务
* 新增 `meta check` 命令用于检测 UtilMeta 服务是否加载正常（启动无错误）

### 优化项

* 优化 `orm.Field` 支持与模型字段名冲突的表达式或 lookup 查询处理
* 优化各 Adaptor 适配器（包括响应，客户端请求，文件等）的运行时识别，指定 `__backends_package__`
* 优化 File 文件对于 ResponseFile (HTTP 响应作为文件) 的文件名识别
* 优化数据库驱动的 Session 的保存（`save`） 行为
* 优化 Filter 组件的 `query` 查询函数对于 `@classmethod` 类方法的处理
* orm 支持查询和序列化 `managed=False` 的 Django 模型（如没有主键的数据库视图） 

### 问题修复

* 修复 Django 应用挂载路由（`__as__` 方法） 的问题

## v2.7.4

发布时间：2025/2/10

### 优化项

* 优化 `orm.Field` 的 queryset 处理逻辑，优化子查询判定并增加鲁棒性
* ORM 支持级联多层的关系对象更新，并避免 Self 自引用和循环引用可能造成的无限递归问题

## v2.7.3

发布时间：2025/1/24

### 优化项

* `DjangoSettings` 的 `apps_package` 支持指定多个 app 目录
* 对可选模型字段（设置了 `default`）的 orm 行为进行优化
* Operations 系统的任务日志支持更详细的控制和输出
* 优化 Operations 系统数据管理接口，对创建于更新时的约束错误返回 400 响应
* 优化包含类型逻辑嵌套的请求体的 Content-Type 识别

## v2.7.2

发布时间：2024/12/26

### 优化项

* `Client` 类对于响应码不匹配任何响应模板的响应，会在 `fail_silently=False` 时抛出错误，提高响应结果的确定性

### 问题修复

* Operations 系统的数据管理功能（对应 UtilMeta 平台的 Data 板块）的数据查询问题修复

## v2.7.1

发布时间：2024/12/25

### 新特性

* `orm.Schema` 的 `save` / `asave` / `bulk_save` / `abulk_save` 方法支持 `using` 参数，可以传入数据库连接的名称（默认是 `default` 或模型配置的数据库）作为查询的数据库连接

### 优化项

* 对 `orm.Schema` 查询的无限循环嵌套问题解决方式进行优化，增加了 `Perference.orm_schema_query_max_depth` 设置限制 Schema 查询深度，默认为 100
* 对 FastAPI / Starlette 应用优化服务端报错的处理逻辑，能够在日志中记录 FastAPI 接口抛出的异常调用栈信息

### 问题修复

* 修复了 **MySQL** 异步连接数据库的一些问题
* 修复了 Retry 插件的一些问题
* 修复了命令行工具中 `--` 参数的解析问题

### API 变更

* `utilmeta.core.orm.ModelAdaptor`：模型适配器的方法进行了变更，新增了 `ModelQueryAdaptor` 处理模型适配器的查询方法

## v2.7.0

发布时间：2024/12/19

### 新特性

* 支持连接到 **代理节点** 进行内网服务集群的管理
* 支持解析与同步 **Django Ninja** 的 OpenAPI 文档
* 支持 `meta.ini` 中指定 `pidfile` 存储当前服务进程 PID，同时支持 `restart` 重启服务命令和 `down` 停止服务命令 

### 优化项

* `Client` 类的 `base_url` 参数支持携带 URL 查询参数，将会解析为 `base_query` 添加到每个 `Client` 类的请求中

### 问题修复

* 修复 API 类上定义的 `response` 响应模板的结果类型在生成的 OpenAPI 文档中缺失的问题

## v2.6.4

发布时间：2024/11/22

### 新特性

* 支持直接连接与管理本地服务
* 支持管理 Django 的 ASGI 应用
* Operations 系统支持监控与观测数据库连接与存储数据，支持时序数据的降采样查询

### 优化项

* 优化 OperationsAPI 的挂载逻辑，支持 **懒挂载** 以增加鲁棒性
* 支持在服务启动前检查与按照数据库依赖
* 优化  Operations 系统中 `secret_names` 的数据处理逻辑，增加对嵌套结构的检测
* 支持 `@api` 装饰器中声明的 `tags` 参数整合到生成的 OpenAPI 文档中
* 优化 `setup` 命令的模板配置
* 优化数据库 Session 的 `must_create` 参数逻辑

### 问题修复

* 修复异步 API 服务使用 Operations 系统的连接关闭问题

### 兼容性

* Django 向下支持到 3.0 版本（可支持管理 Django >= 3.0 的项目）

### API 变更

* `utilmeta.core.cache.Cache` 的异步 API 函数变更，不再使用与同步函数同名的函数（如 `get`, `update`），而是使用前缀为 `a` 的函数，如 `aget`, `aupdate`，原有的用法保留，但会在后续的版本中移除

## v2.6.0

发布时间：2024/11/11

### 新功能

* 新增一个内置的 [Operations 运维管理系统](../../guide/ops)，能够对 API 服务进行实时观测与管理
* 支持 `Perference` 配置，调整 UtilMeta 框架的一些特性参数
* 支持 [声明式 Web 客户端](../../guide/client) 的挂载，钩子与客户端代码的自动生成
* 支持 `orm.Schema` 中关系字段与关系对象的创建与更新

### 优化项

* 重构优化 API 插件系统的实现，使得 API 插件的执行顺序逻辑与装饰器相同
* 优化 `orm.Query` 的 `distinct` 逻辑，增加可配置 `__distinct__` 参数
* 优化支持局域变量（`locals()`）的类型提示解析
* `Error` 错误对象新增 `request` 参数与属性可以访问当前的 API 请求，更方便错误处理插件的处理
* 支持 Response 对象的 `pprint` 方法 [#7](https://github.com/utilmeta/utilmeta-py/pull/7)

### 问题修复

* 修复异步插件的调用
* 修复发送与处理 `multipart/form-data` 数据中的 `filename` 文件名逻辑
* 优化响应中对文件的处理

### 兼容性

* 修复 SQLite 在 windows 与低版本 Python（3.9）上的异常行为

## v2.5.8

发布时间：2024/9/21

### 优化项

* 支持 yaml 配置文件 [#6](https://github.com/utilmeta/utilmeta-py/pull/6)
* 支持自动安装运行服务端 `backend` 所需的依赖

### 问题修复

* 修复了 openapi 文档生成的一些问题

## v2.5.6
发布时间：2024/8/16

### 问题修复

* 修复了 jwt 鉴权相关的兼容性问题

## v2.5.5
发布时间：2024/7/20

### 问题修复

* 修复了 OpenAPI 文档生成相关的问题

## v2.5.2
发布时间：2024/4/24

## v2.4
发布时间：2024/1/29

### 新特性

* 支持了基本的  [声明式 Web 客户端](../guide/client) 特性

## v2.3
发布时间：2024/1/24

### API 变更

* 调整了用户鉴权的登录函数 `login` 参数与 JWT 鉴权组件参数

## v2.2
发布时间：2024/1/20

### 优化项

* 优化鉴权与 Session 相关的 API 用法

## v.2.1
发布时间：2023/12/18

### 新特性

* V2 版本框架的首次发布，提供了声明式的 API 与 ORM 特性

## v1
版本时间：2019/11 ~ 2023/11

旧版本的 UtilMeta 框架，现已不进行支持
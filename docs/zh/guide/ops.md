# 运维监控与服务管理

UtilMeta 框架内置了一个 API 服务管理系统，可以方便地观测与管理对本地与线上的 API 服务，提供了数据，接口，日志，监控，测试，报警等一系列运维管理功能，本篇文档将详细介绍 UtilMeta 的 Operations 运维管理系统的配置与 UtilMeta 平台的连接方式

## 配置引入

UtilMeta 的 API 服务管理系统使用的配置是 `utilmeta.ops.Operations`，将它导入并使用 `service.use` 配置到服务中，如
```python hl_lines="20"
from utilmeta import UtilMeta
from utilmeta.core import api
import starlette

@api.CORS(allow_origin='*')
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=starlette,
    api=RootAPI,
    route='/api'
)

from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
```

!!! note
	正常使用 Operations 配置功能需要你的 UtilMeta 框架版本大于 2.6.1

Operations 配置项的主要参数包括

* `route`：必填，指定管理系统的标准接口 OperationsAPI 挂载的路由，这个路由是相对你的服务的根 API 的，比如你的根 API 挂载到了 `http://mysite.com/api`，设置 `route=’ops‘` 将会把 OperationsAPI 挂载到  `http://mysite.com/api/ops`

!!! tip
	如果你不希望让 OperationsAPI 与你的其他 API 使用同一个域，你的 `route` 参数也可以指定为一个绝对路径，例如 `route='https://ops.mysite.com'` 表示通过 `https://ops.mysite.com` 来提供 OperationsAPI ，这种情况你需要自行处理 OperationsAPI 的挂载与前端代理

* `database`：必填，设置管理系统存储日志，监控等运维数据的数据库，你可以向上面的例子一样指定一个 SQLite 数据库，在生产环境中也可以指定一个 `postgresql` 数据库

!!! tip
	如果你需要配置 MySQL 或 PostgreSQL 数据库，请记得指定数据库的地址，用户名，密码等信息


* `base_url`：为你的 API 服务指定一个可以在网络上访问到的基准 API 地址，这个地址会用于生成的 OpenAPI 文档的 `server.url`，设置后 OperationsAPI 的地址 = `base_url` + `route`

!!! note
	很多情况下你的 API 服务在部署时只是监听本地或内网的地址，由前端的负载均衡对外提供访问，此时自动生成的基准 URL 是你的内网或本地地址，比如 `http://127.0.0.1:8000/api` ，这样的地址无法从其他地方进行访问或调用，所以你需要使用 `base_url` 设置服务的真实地址，比如 `https://mysite.com/api` ，这个地址能够直接在互联网上访问到的，这样生成的 OperationsAPI 地址和生成的 OpenAPI 文档的接口地址就是可以被访问到的了

!!! warning
	当你指定的 `base_url` 中包含路径时，比如  `http://mysite.com/api` ，那么如果接口的路径定义为 `/api/user`，则生成的 API 文档中的路径将会是 `/user`，但如果接口定义的路径不以 `base_url` 中的路径开头，如定义为 `/settings` ，那么这个接口将不会被 API 文档自动生成并同步

!!! warning
	如果你指定的是 `0.0.0.0` 作为服务的 `host`，请在 `base_url` 中指定有效的可访问的地址，否则无法对服务进行管理
 
**任务与监控配置**

* `worker_cycle`：Operations 系统在服务启动后会在每个进程（worker）中启动一个运维任务线程，用于收集并存储请求日志，监控服务数据和报警等，你可以使用 `worker_cycle` 参数指定这些任务每次运行的间隔时间（`int` 描述或 `timedelata`），默认为 30 秒，也就是说默认服务每个进程的请求日志会每 30 秒持久化一次，服务器，数据库和服务实例的监控与报警会每 30 秒进行一次

* `max_backlog`：设置请求日志的最大积压量，除了运维任务的每个 `worker_cycle` 会持久化日志外，当你的进程中积压的未存储日志超过了 `max_backlog` 的值也会触发日志存储，默认是 100 
* `secret_names`：运维管理系统的日志模块会在请求出错（抛出异常，返回 400 及以上状态码）时存储请求和响应的信息用于调试，为了数据安全，你可以指定一系列可能包含密钥或敏感数据的字段名，在日志进行存储时，检测到字段名包含其中任何一个的请求参数，请求体，请求头，响应体和响应头字段都会使用 `'******'` 来代替，默认的 `secret_names` 为
```python
DEFAULT_SECRET_NAMES = (
    'password',
    'secret',
    'dsn',
    'sessionid',
    'pwd',
    'passphrase',
    'cookie',
    'authorization',
    '_token',
    '_key',
)
```

* `max_retention_time`：指定运维系统中所有时序数据的最大存储时间，时序数据包括日志，服务监控，报警记录等数据，这里指定的是所有数据最大存储时间，超过这个时间的数据会被清理，对于细分的数据类别和状态下面将会也介绍更具体的存储时间配置


**管理权限配置**

* `disabled_scope`：禁用的管理权限，如果你不希望某项管理权限被任何管理员用户使用，可以使用这个选项进行禁用，默认为空
* `local_scope`：本地管理节点授予的权限，本地管理指的是观测与管理 localhost / 127.0.0.1 上的本地服务，所以默认权限为 `('*',)`，即全部，如果你将这个值设置为空或者 None，表示将不允许一切本地管理操作

UtilMeta 服务端目前的权限 scope 列表与对应的含义如下：

* `api.view`：查看服务的 API 文档
* `data.view`: 查看数据模型和表结构（即表的字段名称，类型等，不包含查询表中的数据）
* `data.query`：查询表中的数据，支持字段查询
* `data.create`：创建数据，即向表中插入数据
* `data.update`：更新数据
* `data.delete`：删除数据
* `log.view`：查询日志
* `log.delete`：删除日志
* `metrics.view`：查询服务的监控数据

### Log 日志配置

运维管理系统的日志模块负责记录和查询请求日志，日志模块的配置可以让你更细致地调控日志的存储

Operations 配置中的 `log` 参数可以传入日志模块的配置组件，如

```python  hl_lines="8"
from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    log=Operations.Log(
	    default_volatile=False,
	    exclude_methods=['head'],
	    exclude_statuses=[301, 302, 404]
    )
))
```

Log 的配置参数包括

* `default_volatile`：默认是否标记为 `volatile` (不长期保存的日志，聚合后就清理)
* `volatile_maintain`：标记为 `volatile` 的日志的保存时间，传入一个 `timedelta`，默认为 7 天

!!! tip
	为了避免系统中存储过多的冗余日志，一般请求正常无错误的日志在经过聚合处理（计算出请求数，UV 和各接口请求数等）过的一段时间后就可以删除了，日志在存储时会根据配置计算是否为 `volatile`，标记为 `volatile=True` 的日志将在 `volatile_maintain` 时间后被清理

**日志存储规则**

* `persist_level`：请求日志达到什么样的级别以上将会持久化存储（`volatile=False`），默认为 WARN

!!! tip
	UtilMeta 的日志分为 DEBUG, INFO, WARN, ERROR 几个级别，对应着 0，1，2，3，日志如果无报错且状态码在 399 以下则默认归为 INFO 日志，4XX 响应的日志默认归为 WARN 级别，5XX 响应默认归为 ERROR 级别，你可以使用如 `Operations.Log.INFO` 来引用对应的日志等级

* `persist_duration_limit`：请求生成响应的时间超过多长会持久化存储，传入一个秒数，默认为 5 秒
* `store_data_level`：请求日志达到什么样的级别以上将会存储请求体数据
* `store_result_level`：请求日志达到什么样的级别以上将会存储响应体数据
* `store_headers_level`：请求日志达到什么样的级别以上将会存储请求与响应头数据

!!! tip
	如果服务是生产环境（ `production=True`），以上三个参数将默认为 WARN，即生产服务默认只会存储 WARN 级别日志的请求响应数据（请求体，响应体，请求头与响应头），调试环境的服务则默认会存储所有的请求与响应数据 

* `exclude_methods`：排除一些 HTTP 方法，在无出错情况下不存储日志，默认为 `OPTIONS`, `HEAD`, `TRACE`, `CONNECT`
* `exclude_statuses`：可以排除一些响应码，在无出错情况下不存储日志，默认为空
* `exclude_request_headers`：可以排除一些请求头，若请求头中包含其中的值，则在无出错情况下不存储日志，默认为空
* `exclude_response_headers`：可以排除一些响应头，若响应头中包含其中的值，则在无出错情况下不存储日志，默认为空

**日志展示规则**

* `hide_ip_address`：为了数据安全或隐私保护，你可以选择开启这个选项，管理员在 UtilMeta 平台将不会看到日志的 IP 信息
* `hide_user_id`：为了数据安全或隐私保护，你可以选择开启这个选项，管理员在 UtilMeta 平台将不会看到日志的 用户 ID 信息

### Monitor 监控配置

运维管理系统的监控模块会定期（以 Operations 配置的 `worker_cycle` 为周期）对服务器，服务实例，服务进程，数据库和缓存等服务依赖的资源进行监控，并将数据存储到 Operations 配置的数据库中

Operations 配置中的 `monitor` 参数可以传入监控模块的配置组件，如

```python  hl_lines="8"
from utilmeta.ops import Operations
from datetime import timedelta

service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    monitor=Operations.Monitor(
	    server_retention=timedelta(days=30)
    )
))
```

Monitor 的配置参数包括

* `server_disabled`：是否禁用服务器 Server 的监控，默认为 False
* `instance_disabled`：是否禁用服务实例 Instance 的监控，默认为 False
* `worker_disabled` 是否禁用服务进程 Worker 的监控，默认为 False
* `database_disabled`：是否禁用数据库 Database 的监控，默认为 False
* `cache_disabled`：是否禁用缓存 Cache 的监控，默认为 False

!!! tip "服务实例 | 服务进程"
	在 UtilMeta 中，**服务实例（Instance）** 指的是一个运行中的可以处理 API 请求的进程组（后续也会支持容器实例），服务实例中可以包括一个或多个**服务进程（Worker）**（取决于你部署配置的 `workers` 数量），服务实例和服务进程会定期记录和监控它们处理的请求数，平均响应时间，传递的数据量，CPU 与内存的消耗等

* `server_retention`：服务器 Server 监控数据的保存时间，传入 `timedelta`，默认为 7 天
* `instance_retention`：服务实例 Instance 监控数据的保存时间，传入 `timedelta`，默认为 7 天
* `worker_retention`：服务进程 Worker 监控数据的保存时间，传入 `timedelta`，默认为 24 小时
* `database_retention`：数据库 Database 监控数据的保存时间，传入 `timedelta`，默认为 7 天
* `cache_retention`：缓存 Cache 监控数据的保存时间，传入 `timedelta`，默认为 7 天

!!! tip
	保存超过对应时间的监控数据会被清理

### OpenAPI 配置

对于 UtilMeta 框架编写的接口和支持适配的框架接口（如 DRF, FastAPI, Sanic, APIFlask），UtilMeta 运维管理系统可以自动识别并生成 OpenAPI 文档同步到 UtilMeta 平台，但如果你使用的框架不支持自动生成接口文档，或者需要额外注入接口文档，可以使用 Operations 配置的 `openapi` 参数指定额外的 OpenAPI 文档，可以是以下的格式

* 一个 URL，指向能访问和下载的 OpenAPI 文档
* 一个 本地 OpenAPI 文档文件地址
* 一个 OpenAPI 的 json / yaml 字符串
* 一个 OpenAPI 的字典
* 一个列表，用于整合多份 API 文档，其中的元素可以是上述任何一种

例如

```python hl_lines="10"
from utilmeta.ops import Operations
from datetime import timedelta

service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    openapi='/path/to/openapi.json',
    # openapi='https://mysite.com/openapi.json',
    # openapi={...},
))
```

额外指定的 OpenAPI 文档会与自动生成的接口文档进行整合后同步到 UtilMeta 平台

## 连接到 UtilMeta 管理平台

UtilMeta 为 API 服务运维管理系统的观测与管理操作提供了一个管理平台：[UtilMeta API 服务管理平台](https://ops.utilmeta.com)
你可以进入平台连接和管理自己的 UtilMeta 服务，查看 API 文档，数据，日志与监控
### 连接本地节点

如果你已引入了 Operations 配置，成功运行本地服务，并且看到了以下提示

```
UtilMeta OperationsAPI loaded at http://127.0.0.1[...], connect your APIs at https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1[...]
```

你就可以连接本地节点进行调试了，可以直接用浏览器打开上面的第二个链接，或在服务目录 （包含 `meta.ini` 的目录）内部运行以下命令

```
meta connect
```

!!! note
	UtilMeta 版本 2.6.2 及以上支持这个用法

即可看到浏览器中打开了 UtilMeta 管理平台的窗口，你可以在其中看到你服务的 API，数据表，日志和监控等

<img src="https://utilmeta.com/assets/image/connect-local-api.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
!!! warning "Cookie"
	在本地直连（以及内网服务直连）模式下，无法直接从浏览器发送 Cookie 到 API 服务（因为 UtilMeta 平台与本地服务是跨域的），连接线上公网服务则不会有这样的问题因为请求可以通过 UtilMeta 平台进行转发，后续 UtilMeta 平台会上线浏览器插件和桌面版客户端解决直连服务的 Cookie 调试问题，目前你可以使用 [UtilMeta 的声明式 Web 客户端](../client) 来编写调试脚本和测试用例

### 连接线上服务

连接在线上部署的，提供网络访问地址的 API 服务需要你进入 UtilMeta 平台注册一个账号，因为管理线上服务需要更严格的授权与鉴权机制，所以需要你在 UtilMeta 平台中先创建一个项目团队，进入空的项目团队中时，你可以看到 UtilMeta 平台的连接提示

<img src="https://utilmeta.com/assets/image/connect-node-hint.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
如果你已经按照上面的配置方法进行了引入，你可以直接将 UtilMeta 平台给出的命令复制，在你服务器中的项目目录（包含 `meta.ini` 的目录）内部执行命令，如果命令成功执行，你将会看到控制台输出了一个 URL

```
connecting: auto-selecting supervisor...
connect supervisor at: https://api-sh.utilmeta.com/spv
supervisor connected successfully!
please visit [URL] to view and manage your APIs'
```

点击那个 URL 就可以进入平台访问你已连接好的线上服务了，或者在执行成功后点击平台中的【I've executed successfully】按钮刷新状态


### 连接内网集群【代理模式】

除了在公网部署和提供访问的 API 服务外，我们有时也需要管理内网集群中的 API 服务，比如公司内网的内部服务，这些服务没有公开的 IP 地址或访问 URL，管理这些内网服务需要设置内网集群中的公网代理，部署一个代理服务节点进行内网穿透与服务注册，同时具备内网访问鉴权的功能

UtilMeta 已经提供了一个开源的代理服务 [utilmeta-proxy](https://github.com/utilmeta/utilmeta-proxy)

在 UtilMeta 平台中也有连接和管理内网集群的操作指引，点击【Add Cluster】即可进入添加集群功能

<img src="https://utilmeta.com/assets/image/add-cluster-hint.png" href="https://ops.utilmeta.com" target="_blank" width="300"/>

沿着其中的步骤指引进行操作将会自动搭建好一个集群的内网代理节点并连接到 UtilMeta 平台，之后集群中的服务只需要配置连接到代理节点即可，无需再手动连接到平台，代理节点会作为内网集群的服务注册中心向 UtilMeta 平台进行同步

在 Operations 配置中，可以使用 `proxy` 参数配置代理服务节点的地址与设置，主要的参数有

* `base_url`：代理节点的公网 URL 地址，在添加集群并设置代理域名后会自动生成这个地址
* `forward`：是否正向代理节点的出向管理同步请求，比如同步源信息，汇报数据，报警通知等，这个参数在内网节点无法向公网地址发送请求时需要设置为 `True`

```python
from utilmeta import UtilMeta
service = UtilMeta(__name__, ...)

from utilmeta.ops import Operations
from utilmeta.conf import Env

env = Env(file='utilmeta-proxy.env')

service.use(Operations(
  route='ops',
  database=Operations.Database(
      name='utilmeta_proxy_ops',
      host=env.get('UTILMETA_OPERATIONS_DB_HOST'),
      port=env.get('UTILMETA_OPERATIONS_DB_PORT'),
      engine=env.get('UTILMETA_OPERATIONS_DB_ENGINE'),
      user=env.get('UTILMETA_OPERATIONS_DB_USER'),
      password=env.get('UTILMETA_OPERATIONS_DB_PASSWORD'),
  ),
  proxy=Operations.Proxy(
      base_url=env.get('UTILMETA_PROXY_BASE_URL'),
      forward=False
  ),
  base_url='http://$IP/api'
))
```

!!! note
	集群中的服务节点需要与代理节点配置相同的 Operations 数据库，这个共同的数据库将会作为集群中的服务鉴权依据和管理存储中心，目前主要支持 PostgreSQL 和 MySQL 作为集群 Operations 存储，未来的版本会支持其他的存储源

### 直连内网节点

除了上文的连接管理整个内网集群的 **代理模式** 外，UtilMeta 还提供了一种类似于连接本地节点的方式直接管理内网中的服务节点，这种直连内网服务管理需要满足两个条件：

* 你的客户端（你打开 UtilMeta 管理平台的浏览器的电脑）与你要管理的 UtilMeta 服务位于同一 **内网**，也就是说你的电脑可以直接通过服务的内网地址直接访问到服务的 API 接口
* 你的内网服务节点需要提供 HTTPS 协议的访问（需要配置 SSL 证书）

!!! note
	对 HTTPS 协议的要求是浏览器对每一个使用 HTTPS 协议服务的网页（UtilMeta 管理平台）所调用任何除了本机地址（localhost / 127.0.0.1）外的 URL 的要求（参考文档：[Mixed Content | MDN](https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content)），之后 UtilMeta 也规划上线桌面客户端或浏览器插件，可以绕过这个限制

满足以上条件后，直连内网节点需要你对 Operations 增加两项配置：

* `connection_key`：为了保障内网节点的安全，直连内网节点需要你在 Operations 配置中预先设置一个密钥（最好是一个较长的随机字符串），UtilMeta 对于来自内网的管理请求会先校验这个密钥，校验通过后才会执行对应的请求
* `private_scope`：对内网请求的权限范围的授权，权限范围的取值参考上文 `local_scope` 部分的介绍，如果需要授予全部权限，可以使用 `['*']`

配置示例如下：
```python
from config.env import env
from utilmeta.ops import Operations

service.use(Operations(
	base_url='https://my-private-service.com/api',   # replace with your domain
	# other settings...
	connection_key=env.CONNECTION_KEY,
	private_scope=['*']
))
```

其中 `base_url` 也需要设置为使用 HTTPS 协议和域名的服务地址

!!! note
	使用直连内网节点的功能需要 UtilMeta 框架 2.7.5 及以上的版本

配置完成后重启服务你会看到输出中包括 OperationsAPI 的地址

```
UtilMeta OperationsAPI loaded at https://my-private-service.com/api/ops
```

之后我们进入 [UtilMeta 管理平台](https://ops.utilmeta.com)，进入你创建的团队中，点击顶栏中的【+】按钮中的【Connect Local API】连接内网服务

<img src="https://utilmeta.com/assets/image/connect-local-hint.png" href="https://ops.utilmeta.com" target="_blank" width="300"/>

在点击打开的对话框中输入服务的 OperationsAPI 地址（例如 `https://my-private-service.com/api/ops`）

<img src="https://utilmeta.com/assets/image/connect-local-api-form.png" href="https://ops.utilmeta.com" target="_blank" width="500"/>

连接成功后会提示你输入之前设置好的 `connection_key`，输入正确的密钥即可连接并管理内网节点

<img src="https://utilmeta.com/assets/image/set-connection-key-en.png" href="https://ops.utilmeta.com" target="_blank" width="500"/>

!!! note
	勾选保存即可将 `connection_key` 与内网服务地址保存到这个项目团队中，后面再次连接就不需要重复输入了


## 连接现有 Python 项目

UtilMeta 框架的运维管理系统除了可以连接 UtilMeta 框架的服务外，还可以连接现有的 Python 后端项目，目前支持的框架包括

* **Django**：包括 Django REST framework
* **Flask**：包括 APIFlask
* **FastAPI**：包括 Starlette
* **Sanic**

### UtilMeta 项目初始化

在连接任何 Python 项目之前，请先初始化 UtilMeta 设置，方式很简单，就是进入你的项目文件夹中，输入以下命令

```
meta init
```

执行后将会提示你指定当前 Python 项目的 **WSGI/ASGI 应用的引用路径**，比如对于下面的 Django 项目
```
/django_project
	/django_settings
		wsgi.py
		settings.py
		urls.py
	manage.py
```

Django 的 WSGI 应用一般位于 `wsgi.py` 中的 `application` ，当我们在 /django_project 文件夹初始化 UtilMeta 项目时，对应的引用路径就可以输入 `django_settings.wsgi.app`

对于 Flask / FastAPI / Sanic 项目，只需要找到对应的 `Flask()`, `FastAPI()`, `Sanic()` 应用的引用即可，用法和上面一样

执行这个命令实际的效果是在你当前目录创建出一个名为 `meta.ini` 的文件，里面有以下内容

```ini
[utilmeta]
app = django_settings.wsgi.app
```

UtilMeta 框架就是靠这个文件识别 UtilMeta 项目，以及项目的核心应用对象的地址的

### 连接 Django

对于 Django 项目，我们找到包含着 WSGI 应用的 `wsgi.py` (或 ASGI 应用的 `asgi.py`) 文件，在 `application = get_wsgi_application()` 定义后插入 Operations 配置整合代码

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# NEW -----------------------------------
from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
        # or 'postgres' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(application, __name__)
```

我们先声明了 `Operations` 配置，参数如上文介绍的一样，然后调用了配置实例的 `integrate` 方法，第一个参数传入 WSGI / ASGI 应用，第二个参数传入 `__name__`

需要注意的是 `Operations` 配置的 `base_url` 参数需要提供你的 Django 服务的 **基准访问地址**，也就是你的 API 服务中定义的路径都会从这个地址延申，如果是部署在网络上的服务，请设置为能够在网络中访问到的 URL，如果是本地服务，则设置为 `http://127.0.0.1:你的端口号

!!! note
	如果你需要配置 MySQL 或 PostgreSQL 数据库，请记得指定数据库的地址，用户名，密码等信息`

!!! tip
	如果你使用了 **Django REST framework**，UtilMeta 将会自动同步 DRF 生成的 OpenAPI 文档

加入配置代码并重启后，如果你的项目是本地运行，你可以直接在项目启动后的输出中看到连接地址

```
UtilMeta OperationsAPI loaded at [管理接口地址], connect your APIs at [连接地址]
```

你也可以在重启项目后执行如下命令连接本地服务

```
meta connect
```

如果你的服务提供了网络访问，请进入 [UtilMeta 管理平台](https://ops.utilmeta.com)，创建项目团队并按照其中的提示操作进行连接

#### 同步 Django Ninja
如果你正在使用 Django Ninja 框架，由于 Django Ninja 注入 django 应用的方式是通过 `urlpatterns`，UtilMeta 无法直接获取到 Django Ninja 的 `NinjaAPI` 应用来生成 OpenAPI 文档，所以你需要手动在 Operations 配置中指定，例如对于如下的 NinjaAPI

```python
# urls.py --------
from ninja import NinjaAPI

ninja_api = NinjaAPI()

@ninja_api.get("/add")
def add(request, a: int, b: int):
    return {"result": a + b}

urlpatterns = [
    path("api-ninja/", ninja_api.urls),
]
```

我们需要在 wsgi.py 的 Operations 配置中加入解析 NinjaAPI 文档的代码

```python hl_lines="14-16"
import os
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

from utilmeta.ops import Operations
from .urls import ninja_api

Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    openapi=Operations.get_django_ninja_openapi({
        "api-ninja/": ninja_api
    }),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(application, __name__)
```

Operations 配置的 `openapi` 参数用于指定额外的 API 文档，我们这里直接调用 Operations 配置的 `get_django_ninja_openapi` 方法，其中的传入一个字典，字典的键是 NinjaAPI 挂载到 urlpatterns 的路径，比如上面例子中的 `'api-ninja/'`，字典的值就是对应的 `NinjaAPI()` 实例，由于 Django Ninja 可以创建多个 `NinjaAPI()` 实例，你都可以按照这个规则传入到函数中

### 连接 Flask

对于 Flask 项目，我们只需要将 Operations 配置接入 Flask app 即可，如

```python
from flask import Flask

app = Flask(__name__)

# @app.route(...)
# 请将以下代码插入到 Flask 路由的后面，否则会影响 API 文档生成

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3' # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```

!!! tip
	如果你使用了 **APIFlask**，也只需要把  Operations 配置接入 APIFlask 的 app 中，UtilMeta 将会自动同步 APIFlask 生成的 OpenAPI 文档

`Operations` 配置的 `base_url` 参数需要提供你的 Flask 服务的 **基准访问地址**，也就是你的 API 服务中定义的路径都会从这个地址延申，如果是部署在网络上的服务，请设置为能够在网络中访问到的 URL，如果是本地服务，则设置为 `http://127.0.0.1:你的端口号`

!!! note
	如果你需要配置 MySQL 或 PostgreSQL 数据库，请记得指定数据库的地址，用户名，密码等信息

加入配置代码后，如果你的项目是本地运行，可以在重启项目后执行如下命令连接本地服务

```
meta connect
```

如果你的服务提供了网络访问，请进入 [UtilMeta 管理平台](https://ops.utilmeta.com)，创建项目团队并按照其中的提示操作
### 连接 FastAPI

对于 FastAPI 项目，我们只需要将 Operations 配置接入 FastAPI app 即可，如

```python
from fastapi import FastAPI

app = FastAPI()

# @app.route(...)
# app.include_router(...)
# 请将以下代码插入到 FastAPI 路由的后面，否则会影响 API 文档生成

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'  # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```

!!! tip
	UtilMeta 将自动同步 FastAPI 生成的 API 文档

`Operations` 配置的 `base_url` 参数需要提供你的 FastAPI 服务的 **基准访问地址**，也就是你的 API 服务中定义的路径都会从这个地址延申，如果是部署在网络上的服务，请设置为能够在网络中访问到的 URL，如果是本地服务，则设置为 `http://127.0.0.1:你的端口号`

!!! note
	如果你需要配置 MySQL 或 PostgreSQL 数据库，请记得指定数据库的地址，用户名，密码等信息

加入配置代码后，如果你的项目是本地运行，可以在重启项目后执行如下命令连接本地服务

```
meta connect
```

如果你的服务提供了网络访问，请进入 [UtilMeta 管理平台](https://ops.utilmeta.com)，创建项目团队并按照其中的提示操作

### 连接 Sanic

对于 Sanic 项目，我们只需要将 Operations 配置接入 Sanic app 即可，如

```python
from sanic import Sanic

app = Sanic('mysite')

# @app.route(...)
# 请将以下代码插入到 Sanic 路由的后面，否则会影响 API 文档生成

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3' # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```

!!! tip
	UtilMeta 将自动同步 Sanic 的 openapi 扩展生成的 API 文档

`Operations` 配置的 `base_url` 参数需要提供你的 Sanic 服务的 **基准访问地址**，也就是你的 API 服务中定义的路径都会从这个地址延申，如果是部署在网络上的服务，请设置为能够在网络中访问到的 URL，如果是本地服务，则设置为 `http://127.0.0.1:你的端口号`

!!! note
	如果你需要配置 MySQL 或 PostgreSQL 数据库，请记得指定数据库的地址，用户名，密码等信息

加入配置代码后，如果你的项目是本地运行，可以在重启项目后执行如下命令连接本地服务

```
meta connect
```

如果你的服务提供了网络访问，请进入 [UtilMeta 管理平台](https://ops.utilmeta.com)，创建项目团队并按照其中的提示操作

## UtilMeta 管理平台

[UtilMeta 管理平台](https://ops.utilmeta.com) 是一个一站式的 API 服务观测与管理平台，这一节主要介绍它的功能与用法

### 管理平台概览
在 UtilMeta 管理平台中，每个用户都可以创建或加入多个 **项目团队（Team）**，每个团队中可以连接并管理多个 **API 服务 （API Service）**，也可以添加多位成员，为他们赋予不同的管理权限

!!! note
	类似于 Github 的 Organization 和 Repo

在 UtilMeta 平台的项目团队中添加 API 服务有两种方式：

* 使用 UtilMeta 框架或者 UtilMeta 适配的框架开发，可以添加配置代码后一键接入平台
* 其他的 API 服务，可以通过导入或识别 OpenAPI 接口文档进行添加

<img src="https://utilmeta.com/assets/image/connect-service-choose.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>

每个连接到 UtilMeta 平台的 API 服务都支持以下功能

* 可调试的 API 接口文档
* 编写与执行 API 单元测试
* 查看 API 的调用与测试日志
* 为 API 设置拨测监控与报警（即将上线）

使用 UtilMeta 框架（或其他支持的框架）连接到平台的 API 服务称为 **UtilMeta 节点**，UtilMeta 框架的运维管理系统提供的 OperationsAPI 使得 UtilMeta 节点有了服务端的观测和汇报能力，所以 UtilMeta 节点相对普通的 API 服务有着以下的额外功能

* 服务端请求实时日志查询
* 数据管理 CRUD （需要服务端使用支持的 ORM 库，目前支持 django ORM）
* API 真实请求访问统计与分析
* 服务端资源性能与占用实时监控
* 服务端条件报警与通知（即将上线）

!!! tip
	以上的功能是为提供网络访问地址的 UtilMeta 节点提供的，如果你连接的是 **本地 (localhost / 127.0.0.1)** UtilMeta 节点，那么平台只能提供数据，接口，日志，服务监控等基本功能

### API 接口文档

点击左栏 **API** 可以进入平台的接口管理板块

<img src="https://utilmeta.com/assets/image/api-annotation-zh.png" target="_blank" width="800"/>
左侧的 API 列表可以搜索或者使用标签过滤接口，点击接口即可进入对应的接口文档，点击右侧的【Debug】按钮可以进入调试模式，你可以输入参数并发起请求，右侧会自动同步参数对应的 curl, python 和 js 请求代码

如果你的 API 接口包括了鉴权所需的密钥，可以在 UtilMeta 平台对密钥进行集中管理

!!! tip
	对于连接的本地节点和未登录用户，发起请求会从你的浏览器端直接发起，如果你的接口没有开启跨域（CORS）设置，将无法显示调试结果

### Data 数据管理

点击左栏 **Data** 可以进入平台的数据管理板块

<img src="https://utilmeta.com/assets/image/data-annotation-zh.png"  target="_blank" width="800"/>
左侧的模型（数据表）列表可以搜索或者使用标签过滤，点击模型后右侧将显示表结构与查询表数据，你可以在上方的字段查询栏添加多个字段查询，表中的每个字段也支持正反排序

表中的每个数据单元都是可以点击的，左击或右击都会展开选项卡，对于数据过大无法显示完整的数据可以展开，有权限的用户也可以对选中的数据行进行编辑或删除。点击右上角的【+】按钮可以创建新的数据实例

表的下方是模型的表结构文档，会详细展示模型字段的名称，类型，属性（主键，外键，唯一等）和校验规则

你在 Operations 系统配置时可以指定一个 `secret_names` 参数，当表字段名称包含着 `secret_names` 中任何一个名称时，数据查询返回的对应结果将会作隐藏处理（`'******'`），默认值参考上文配置部分

!!! tip
	对于 django ORM 默认会根据模型的 app 名称生成标签 

!!! warning
	数据板块的权限管理很重要，团队管理员可以在 Team 团队板块为其他成员分配权限，请谨慎分配数据的写入和删除权限

### Logs 日志查询

点击左栏 **Logs** 可以进入平台的日志查询板块

<img src="https://utilmeta.com/assets/image/logs-annotation-zh.png"  target="_blank" width="800"/>
左侧是日志的过滤与选项，顶端可以切换日志板块
* **Service Logs**：服务端真实请求日志
* **Test Logs**：在 UtilMeta 平台发起的调试与测试日志

左侧下方的过滤选项包括日志等级，响应状态码，HTTP 方法和 API 接口路径等，还可以根据请求时间或处理时间进行排序

点击单条日志即可展开日志详情，日志会详细记录请求和响应的信息，异常调用栈等数据 

<img src="https://utilmeta.com/assets/image/logs-detail-annotation-zh.png"  target="_blank" width="600"/>

!!! tip
	具体信息的存储与展示规则由 Operations 中的 `log` 参数配置，见上文

### Servers 服务监控

点击左栏 **Servers** 可以进入平台的服务监控板块

<img src="https://utilmeta.com/assets/image/servers-annotation-zh.jpg"  target="_blank" width="800"/>
可以实时监控 API 服务所在的服务器的 CPU，内存占用量，负载压力（Load Avg），文件描述符与网络连接数等

右上角的时间范围选项可以选择数据查询的时间

### 授权与鉴权机制

UtilMeta 管理平台的观测与管理操作授权是基于 OAuth2 协议的 credentials flow 的

UtilMeta 节点提供的服务端管理能力，如数据管理，日志和监控查询等都是通过直接调用节点的 OperationsAPI 实现的，在调用前，UtilMeta 平台的客户端（如浏览器）会先向 UtilMeta 平台请求包含对应权限的 OAuth access token，如果平台校验用户在 API 服务所在的团队中有相应的权限则会授权，否则会拒绝

<img src="https://utilmeta.com/assets/image/permissions-team-example.png"  target="_blank" width="600"/>

!!! tip
	团队管理员可以在 **Team 团队**板块添加或设置成员权限

正常授权后 UtilMeta 管理平台的客户端就会携带 access token 向你的服务端的  OperationsAPI 发起观测或管理请求，OperationsAPI 会对 access token 进行解析与鉴权，并执行合法的请求

!!! note
	除了 OAuth2 的基本流程外，UtilMeta 平台的授权机制还包括实时权限同步，比如当你在 UtilMeta 管理平台撤销了成员的权限后，UtilMeta 平台将会同步给所有的服务节点，将已授权给该用户但未过期的 access token 全部无效化，对应用户之前所生成的权限 access token 会立即无效，这样使得整个分布式的权限系统都是实时反应的

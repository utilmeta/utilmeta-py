# 插件与扩展系统

一个成熟的框架应该提供给开发者自由灵活的扩展机制，UtilMeta 也并不例外，框架中包含了 **插件** 与 **扩展系统** 两种自定义扩展机制，并且内置了很多功能丰富的常用插件与扩展

## UtilMeta 的扩展机制

### UtilMeta 插件

插件是一个轻量的组件，可以提供请求处理，响应处理，错误处理等功能，通过 **装饰器** 的方式注入到 API 类，API 函数或 `Client` 类和请求函数中

```python
from utilmeta.core.request import Request
from utilmeta.core.response import Response
from utilmeta.utils import Error

class MyPlugin(Plugin):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
	
	def process_request(self, request: Request, api=None):
		pass

	def process_response(self, response: Response, api=None):
		pass

	def handle_error(self, error: Error, api=None):
		pass		
```

相较于 django 等框架的中间件 (middleware) 机制，插件的方便之处在于它的作用域可以任意选择，如果你希望一个插件像 django 中间件一样作用于服务的全部请求，只需要将它注入到 UtilMeta 服务的 **根 API** 上即可，你也可以注入到任意的 API 类或 API 函数上从而灵活精准地指定插件作用的范围

插件作用的规则是：同一类的插件对一个目标 **只能作用一次**，

```python
@MyPlugin(param2='value2')
@MyPlugin(param1='value1')
class TargetAPI(api.API):
	pass
```

如果插件按照这种方式注入，只有最靠后注入的（最顶端）`MyPlugin` 插件会起作用

需要读取当前请求的信息：

Response
* request

Error
* request





#### 使用 `@awaitable` 同时支持同步异步 API


### UtilMeta 扩展系统

UtilMeta 的扩展系统将会注入整个 UtilMeta 服务，扩展系统的入口其实就是一个 UtilMeta 配置，

```python
from utilmeta.conf import Config
from utilmeta import UtilMeta


class MyExtensionConfig(Config):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		
    def hook(self, service: UtilMeta):
        pass

    def setup(self, service: UtilMeta):
        # call when the service is setting up
        pass

    def on_startup(self, service: UtilMeta):
        pass

    def on_shutdown(self, service: UtilMeta):
        pass
```


#### 命令行注入

```python
from utilmeta.conf import Config
from utilmeta import UtilMeta


class MyExtensionConfig(Config):
    def hook(self, service: UtilMeta):
        from .cmd import MyCommand
        service.register_command(MyCommand)
```



### 适配中间层扩展

UtilMeta 作为一个元框架，是通过 **适配器中间层** 的机制来兼容支持各自 HTTP 框架与组件的，如果你希望扩展 UtilMeta 支持适配的框架，也可以通过扩展适配中间层进行

* server
* request
* response
* file
* orm
* cli


## 内置插件与扩展

### `orm.Atomic` 插件

### `api.CORS` 插件

### `api.Retry` 插件


### `utilmeta.ops` 扩展系统


## 生态插件与扩展

欢迎广大开发者参与 UtilMeta 生态建设，开发 UtilMeta 插件或扩展系统，这里将会列出社区中常用的 UtilMeta 扩展包与仓库地址



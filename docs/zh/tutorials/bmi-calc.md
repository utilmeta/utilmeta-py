# 简单的 BMI 计算 API

我们的入门教程是编写一个简单的 BMI 计算 API，根据输入的身高，体重信息计算对应的 BMI 数值
## 1. 创建项目

直接使用 `meta setup` 命令创建我们的项目

```
meta setup demo-bmi --ops
```

之后会提示你输入项目的描述，网址等信息，你可以选择跳过，完成后你将会得到如下的文件结构

```
/bmi
    server.py
    meta.ini
```

!!! abstract ""
	`server.py` 是你的开发文件，而 `meta.ini` 是一个让 `meta` 命令行识别项目根目录和元信息的配置文件，命令行中的 `--ops` 参数会自动帮你完成接口连接配置，接下来将可以一键连接查看 API 接口 

## 2. 编写基础的 API 实现

我们打开 `server.py`，可以发现其中已经有了一个名为 `RootAPI` 的类

```python
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

其中你可以看到一个最简单的 UtilMeta API 接口，它使用 `@api.get` 装饰器表示这是一个 GET 方法，装饰器并没有指定路径，所以接口的路径就是函数的名称 `/hello`

我们按照这样的简单方式来编写我们的 BMI 计算接口，如下

```python
class RootAPI(api.API):  
    @api.get  
    def bmi(self, weight: float, height: float):  
         return round(weight / height ** 2, 1)
```

我们在 `bmi` 函数中添加的参数 `weight` 和 `height` 会被默认处理为查询参数，在函数中进行计算并直接返回即可，UtilMeta 将会处理 HTTP 响应的包装和返回

我们可以直接运行这个文件来启动 API 服务
```shell
python server.py
```

当看到如下提示即说明启动成功
```
| UtilMeta v[version] starting service [demo-bmi]
|     version: 0.1.0
|       stage: ● debug
|     backend: django (version) 
|    base url: http://127.0.0.1:8000/api
Running on http://127.0.0.1:8000
Press CTRL+C to quit
```

接着我们可以直接使用浏览器访问 [http://127.0.0.1:8000/api/bmi?weight=70&height=1.85](http://127.0.0.1:8000/api/bmi?weight=70&height=1.85)
来调用 API，可以看到 API 返回了
```json
20.5
```


这个例子足够简单，但它也有一些可以优化的地方，比如

* 没有对请求参数值的大小作校验，如果参数 `height` 是 0 则会发生错误，如果参数是负数也没有意义
* 数字作为结果直接进行了返回，通常的做法应该使用一个 JSON 进行返回

## 3. 优化请求处理与响应

结合上面提到的优化我们来对 API 作一些改进

首先我们使用 `utype.Param` 增加对输入参数校验规则的声明，如

```python
import utype

@api.CORS(allow_origin='*')  
class RootAPI(api.API):
    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)):
        return round(weight / height ** 2, 2)
```

在上面的函数中，我们声明了 `weight` 参数需要大于 0，小于等于 1000，`height` 参数需要大于 0，小于等于 4，如果输入的数据不符合这些规则，则 UtilMeta 会自动处理并返回 `400 BadRequest` 响应

!!! abstract "utype"
	UtilMeta 使用 `utype` 获得数据规则声明与解析的能力，你可以在 [这篇文档](https://utype.io/zh/references/rule/) 中发现更多的规则校验参数和用法


另外对于返回结果，我们可以使用一个 JSON 来返回 BMI 的数值和对应的等级，为了使响应同样可以被整合到 API 文档中，我们可以使用 `utype.Schema` 来定义响应的格式，如
```python
from utilmeta.core import api
import utype

class BMISchema(utype.Schema):
    value: float = utype.Field(round=2)

    @property
    def level(self) -> int:
        for i, l in enumerate([18.5, 25, 30]):
            if self.value < l:
                return i
        return 3

@api.CORS(allow_origin='*')  
class RootAPI(api.API):
    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)
            ) -> BMISchema:
        return BMISchema(value=weight / height ** 2)
```

在 BMISchema 中我们额外声明了一个 `level` 属性，通过对 `value` 的计算得出对应的 BMI 等级，而 `level` 同样会作为字段进行输出，接口所返回的 BMISchema 实例会被 UtilMeta 直接处理成 JSON 格式响应给客户端

当我们重启项目并再次访问 [http://127.0.0.1:8000/api/bmi?weight=70&height=1.85](http://127.0.0.1:8000/api/bmi?weight=70&height=1.85) 时，可以看到如下的返回结果
```json
{"value": 20.45, "level": 1}
```

## 4. 连接 API

UtilMeta 服务开发好后，你可以直接连接 API 并访问到可调试的接口文档，记得我们在创建项目的命令中加入了 `--ops` 参数，它能帮我们自动插入 UtilMeta 的观测管理系统的配置代码，我们可以在 `server.py` 中看到以下配置

```python
from utilmeta.ops.config import Operations

service.use(Operations(
    route='ops',
    database=Database(
        name='demo-bmi_utilmeta_ops',
        engine='sqlite3',
    ),
))
```

当你成功运行 UtilMeta 服务时，你会看到控制台有以下的输出

```
UtilMeta OperationsAPI loaded at http://127.0.0.1:8000/api/ops, connect your APIs at https://ops.utilmeta.com
```

此时你可以直接点击 [这个链接](https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8000/api/ops) 连接并查看你的 API 接口，也可以在你的本地的项目文件夹内运行以下命令

```
meta connect
```

你会看到一个窗口打开并连接到了你刚开发好的 API


<img src="https://utilmeta.com/assets/image/demo-bmi-connect-local.png" href="https://ops.utilmeta.com" target="_blank" width="600"/>

我们点击 API 即可看到我们刚开发的 BMI 计算 API，我们可以点击【Debug】按钮进行调试

<img src="https://utilmeta.com/assets/image/demo-bmi-api-debug.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
我们点击 Logs 可以看到我们刚触发的请求日志，可以点击查看它的详细信息

<img src="https://utilmeta.com/assets/image/demo-bmi-logs.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>

!!! tip
	为了实时请求的性能，日志会在进程后台收集并且定期存储，如果没有立刻看到你可以稍候并刷新，更多的运维管理相关的配置可以参考 [运维与监控管理文档](../../guide/ops)


## 案例源码

本案例的源码可以参考 [github](https://github.com/utilmeta/utilmeta-py/blob/main/examples/bmi_calc/server.py)
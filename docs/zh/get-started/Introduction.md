# UtilMeta - 面向服务端应用的渐进式元框架  

## 核心特性

* **渐进式元框架**：使用一套标准支持 django, flask, fastapi (starlette), sanic, tornado 等主流 Python 框架作为 HTTP 运行时实现（切换实现只需一个参数），支持从以上框架的现有项目使用 UtilMeta 进行渐进式开发，灵活兼容多种技术栈，支持异步接口
* **声明式接口**：高效产出简洁代码，自动根据声明完成请求校验，响应构建与生成 OpenAPI 标准文档
* **极简高效的 ORM**：UtilMeta 实现了一个独创高效的声明式 ORM 标准，支持 django 与 peewee, sqlachemy，
* **高度可扩展与丰富的插件**：内置一系列可灵活接入的鉴权（session/jwt），跨域处理，重试，请求控制，事务等插件

## 安装

```shell
pip install -U utilmeta
```


### Hello World

```python
from utilmeta import UtilMeta
from utilmeta.core import api
import flask

service = UtilMeta(
    __name__,
    name='demo',
    backend=flask,    # or django / fastapi / tornado / sanic
)

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service.mount(RootAPI, route='/api')
app = service.application()     # used in wsgi/asgi server

if __name__ == '__main__':
    service.run()
```

## 用法示例
产出高可读性的简洁代码，能够做到代码即文档，大幅度提高开发效率，并且简单好上手

以下是一个 BMI 计算接口的示例
```python
from utilmeta import UtilMeta  
from utilmeta.core import api  
import flask  
import utype  

service = UtilMeta(  
	__name__,  
	backend=flask,  
	port=8001,  
)  

BMI_LEVELS = [18.5, 25, 30]  

class BMISchema(utype.Schema):  
	value: float = utype.Field(round=2)  

	@property  
	def level(self) -> int:  
		for i, l in enumerate(BMI_LEVELS):  
			if self.value < l:  
				return i  
		return 3  

class RootAPI(api.API):  
	@api.get  
	def bmi(self,  
		weight: float = utype.Param(gt=0, le=1000),  
		height: float = utype.Param(gt=0, le=4)  
	) -> BMISchema:  
		return BMISchema(value=weight / height ** 2)  

service.mount(RootAPI, route='/api')  
app = service.application() # for wsgi/asgi server  
  
if __name__ == '__main__':  
	service.run()
```

GET http://127.0.0.1:8001/api/bmi?weight=70&height=1.85
```json
{"value": 20.45, "level": 1}
```


::: tip
可以尝试把示例中的 backend=flask 替换为 django / fastapi / sanic / tornado (需要先安装并导入)，你会发现接口实现的效果是相同的
:::

有了自动化的接口请求解析和响应生成，你只用声明好你需要的请求参数的类型和规则即可，UtilMeta 框架会自动处理不符合要求的输入并生成 400 响应

::: tip
UtilMeta 框架使用 [utype](https://utype.io/zh/) 解析库完成所有参数的声明与解析
:::

  
基于 Python 标准的类型提示语法提供声明式的 API 编写方式  
  
在这个简短的例子中，你已经获得了  
* 自动化的请求参数解析，生成并执行高效的查询（避免了手写查询可能带来的 N+1 问题），并将结果转化到你声明的类型  
* 自动生成的 API 文档，包括请求参数和响应结果  
* IDE 的类型提示与属性自动补全，使得你可以高效开发并减少 bug  


### ORM

  
::: tip
什么是 N+1 查询问题 ?  
https://stackoverflow.com/questions/97197/what-is-the-n1-selects-problem-in-orm-object-relational-mapping  
  
在上文的例子中，无论你需要返回多少用户，每个用户有多少文章，都只需要执行 2 个查询，但如果你使用了嵌套 for 循环的方式编写查询语句的话，最坏可能产生 （文章总数 + 1）个查询  
当你需要查询的结果的结构更加复杂时，这种情况会更严重，但是交给 UtilMeta 的 ORM 来处理可以让你以最优化的方式执行查询与关系序列化
:::


```python
from utilmeta.core import orm
from utilmeta.core.orm.backends.django import expressions as exp
from django.db import models

class User(models.Model):
    username = models.CharField(max_length=20, unique=True)

class Article(models.Model):
    author = models.ForeignKey(User, related_name="articles", on_delete=models.CASCADE)
    content = models.TextField()

class UserSchema(orm.Schema[User]):
    id: int
    username: str
    articles_num: int = exp.Count('articles')

class ArticleSchema(orm.Schema[Article]):
    id: int
    author: UserSchema
    content: str

>>> ArticleSchema.serialize(Article.objects.filter(author__username='bob'))
[ArticleSchema(id=1, author=UserSchema(id=1, username='bob', articles_num=1), content='my first blog')]
```


### 丰富的插件与强大的可扩展性  
  
UtilMeta 的核心类只承担核心的基本流程，并不强制用法与功能，各种各样的功能都可以通过插件进行注入，UtilMeta 已经内置了一系列丰富的插件，可以通过多种方式进行注入，如  
```python  
  
@api.Atomic(savepoint=True) # db transaction  
@api.Auth(relate=model.author) # authentication: must be the author of target  
def patch(self): pass  
  
@api.post('operation')  
@api.Retry(max_retries=3, timeout=5) # specify retries and timeout  
@api.RateLimit(max_errors=5, max_rps=2) # rate limit  
@api.CORS(allow_origin='*') # cross origin config  
def complex_operation(self):  
	pass  
```  
  
除了内置的插件外，你还可以自行编写插件，或者对现有的插件进行扩展，插件通过订阅核心的事件并施加函数逻辑来提供功能  
  

### 同时兼容同步/异步实现


## 设计哲学  
  
* 声明式：  
* 渐进式：你可以在你现有技术栈的基础上，逐渐引入 UtilMeta 编写适合它的接口与任务，  
* 细粒度：  
* **低侵入，高灵活**：  
* **符合直觉**：设计出来的用法需要给人一种【就应该是这样的】感觉
* 薄框架，厚插件：框架的核心类只承载核心通用的基本流程，提供的关键功能（鉴权，请求控制，参数解析，查询生成，链路追踪，监控报警等）都是通过灵活插拔的插件进行配置和引入的


### FAQ

Q: 使用 UtIlMeta 需要我具备使用其他 Python 开发框架（如 django, flask）的能力吗？
A：并不需要，因为任意的底层框架，
如果你恰好精通其中的某个框架，使用它作为 UtIlMeta 的底层实现可以使你的服务运行
如果你并不清楚选择哪个 HTTP 框架作为依赖，可以默认在同步开发时使用 django，在异步开发时使用 fastapi
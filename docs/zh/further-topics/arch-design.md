# 架构与设计哲学




API 类也是一个和其他 Python Web 框架不太相同的设计，像 Flask, FastAPI, Sanic 这类框架一般都是给出一个全局的装饰器属性，再

```python
from fastapi import FastAPI 

app = FastAPI() 

@app.get("/users/me") 
async def read_user_me(): 
	return {"user_id": "the current user"} 
	
@app.get("/users/{user_id}") 
async def read_user(user_id: str): 
	return {"user_id": user_id}
```


而 API 类其实真正承载信息的是 `self` 这一实例，实例将请求信息通过 `self.request` 完整的承载，能够使用 `self.xxx` 访问 API 类中的插槽属性，并且能够直接调用类内的其他函数而无需显式的传递请求参数，所以在 API 类中，除了编写接口函数之外，也可以编写一些通用的实例函数，可以被多个接口调用

除了开发者在 API 函数中主动调用其他类函数外，API 类中定义的钩子也是非常重要的原因


```python

class UserAPI(API):
	def __init__(self):
		self.data = {}
	
	def login(self):
		pass
		
	@api.before(login)
	def prepare_login(self):
		pass
		
	@api.after(login)
	def process_login(self, r):
		pass	
		
	@api.handle('*')
	def handle_all(self, e):
		print(self.data)
```


区别于 Flask 和 Sanic，UtilMeta 将每个 API 函数都需要指定唯一的 HTTP 方法

首先这样做是基于 API 函数的单一职责理念，通常不同的方法会有着不同的作用，如果需要在一个路径的不同 HTTP 方法中复用相同的逻辑，那么在 UtilMeta 中也可以轻松地放入前处理钩子和后处理钩子中进行处理
还有一个关键点是强制的 HTTP 方法指定使得每一个 API 端点 （endpoint）都可以进行相对于服务的唯一的标识如 `<method>:<path>`，这样对于 API 流量数据的收集，分析与标记都是一个良好的区分标准


思想：框架并不强制某种操作或者限制某种行为，但是通过语言接口和用法的设计能够使得大部分开发者都在框架所建议的思想与行为下编程
* 你可以最省力（代码）的定义出框架所期望的结构
* 你依然能够通过额外的声明与配置定义出任意的结构

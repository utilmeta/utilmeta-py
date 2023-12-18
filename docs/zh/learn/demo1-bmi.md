# Demo - 一个简单的 BMI 计算 API


## 1. 创建一个 UtilMeta 项目




## 2. 编写最基础的 API 实现

```python
from utilmeta import UtilMeta  
from utilmeta.core import api  
import flask  
import utype  

service = UtilMeta(  
	__name__,  
	backend=flask,   # or django/fastapi/sanic/tornado
	port=8001,  
)  

class RootAPI(api.API):  
	@api.get  
	def bmi(self, weight: float, height: float):  
		return round(weight / height ** 2, 1)

service.mount(RootAPI, route='/api')  
app = service.application() # for wsgi/asgi server  

if __name__ == '__main__':  
	service.run()
```


GET http://127.0.0.1:8001/api/bmi?weight=70&height=1.85
```json
20.5
```


这个例子足够简单，但它也有一些可以优化的地方，比如
* 没有对请求参数值的大小作校验，如果参数 `height` 是 0 则会发生错误，如果参数是负数也没有意义
* 数字作为结果直接进行了返回，通常的做法应该使用一个 JSON 进行返回


## 3. 优化请求处理与响应
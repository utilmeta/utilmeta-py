# 如何开发 UtilMeta 插件？


```python
class MyPlugin(Plugin):
	def process_request(self, request, api=None):
		pass

	def process_response(self, response, api=None):
		pass

	def handle_error(self, error, api=None):
		pass
		
```


需要读取当前请求的信息：

Response
* request

Error
* request
### 跨源策略
现代浏览器基本都会使用跨源限制，即限制客户端请求来自当前网站之外的源地址的请求，如用户在 `https://a.com` 上请求了 `https://b.com` 的 API 接口，就是受到浏览器的跨源策略的限制 
然而浏览器也使用了跨源资源共享（CORS）方案能够让浏览器请求其他源的接口与资源，在 Request 组件中，跨源策略通过以下几个参数配置

::: tip 源地址
我们所讨论的源指的是请求中使用 `Origin` 请求头传递的地址，包含着请求 URL 的协议，域名和端口，比如 `https://mysite.com:8080/api/user` 中的源地址就为  `https://mysite.com:8080` 
:::

* `allow_origin`：指定允许的源，可以是一个源地址的字符串，字符串的列表或者 `'*'` 表示允许所有的源的请求，当请求的源地址在允许的源内时，`Access-Control-Allow-Origin` 请求头的值就是当前的源地址，这样浏览器会认为这是一个合法 CORS 请求，如果请求的源地址不在允许的源内时，将会抛出一个 `exc.PermissionDenied` 错误，默认被处理为 403 响应
* `allow_headers`：允许跨源的请求头，将用于生成 `Access-Control-Allow-Headers`  响应头，如果除了声明在请求头参数的请求头外你还需要更多允许的请求头，可以传入一个请求头名称的列表
* `cors_max_age`，跨源的预检请求的缓存时间，用于生成 `Access-Control-Max-Age`  响应头，在这个时间范围内，再次请求已缓存的非简单请求将不需要发送预检请求

我们可以示范一下 CORS 的应用
```python
class RootAPI(API):
	request = Request(
		allow_origin=['http://foo.com', 'http://bar.com'],
		cors_max_age=86400
	)
	
	@api.get
	def hello(self):
		return 'world'
		
	@api.post(request=Request(login=True))
	def operation(self):
		pass
	
	@api.before(operation)
	def check_user_id(self, x_user_id: str):
		if self.request.user_id != x_user_id:
			raise exc.BadRequest('invalid user id')
```
如果这个 API 服务的地址是 `http://mysite.com` ，那么当用户浏览器的地址在 `http://mysite.com` ，`http://foo.com`, `http://bar.com` 中时对  `http://mysite.com` 发起请求，就如
```http
GET /api/hello HTTP/1.1
Host: mysite.com
Origin: http://foo.com
```
那么由于请求的源地址（`Origin`）是服务所允许的源（`allow_origin`），会返回如下响应
```http
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://foo.com
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Content-Type
Access-Control-Max-Age: 86400
```
这时浏览器会将这个请求视为合法的 CORS 请求进行处理

但如果用户位于其他的源站时，如 `http://other.site` ，那么请求就会得到 `403 PermissionDenied` 响应，从而不会被浏览器处理

对于非简单的跨源请求（简单请求的定义参考 CORS 相关的文档），如 POST 请求，在实际请求之前会发送一个 OPTIONS 预检请求，
* `Access-Control-Request-Method`: 请求的方法
* `Access-Control-Request-Headers`: 请求中需要携带的请求头

如例子中，将会先发送
```http
OPTIONS /api/operation HTTP/1.1
Host: mysite.com
Origin: http://foo.com
Access-Control-Request-Method: POST
Access-Control-Request-Headers: Content-Type, X-User-ID
```

UtilMeta 可以根据你的接口方法声明和请求头声明自动地处理 OPTIONS 预检请求，生成符合 CORS 规范的响应，其中包括响应头
* `Access-Control-Allow-Origin`：如果请求的源地址在允许的范围内，将会将这个响应头设为 `Origin` 中的值，表示允许这个跨源请求 
* `Access-Control-Allow-Methods`: 当前路径允许的 HTTP 方法，根据接口方法的声明生成
* `Access-Control-Allow-Headers`: 请求所允许发送的请求头，根据请求头参数的声明生成
* `Access-Control-Max-Age`: 预检请求的最大缓存实际，根据 `cors_max_age` 参数生成

::: tip
如果你想具体了解跨源请求，可以参考 [MDN 跨源资源共享](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/CORS)
:::

## API 插件

* `process_request
* `process_response`
* `handle_error`

API 插件可以施加到某个函数（API 接口）或者整个 API 类中，当施加到 API 类时，会对该 API 类定义的和挂载的所有 API 接口生效

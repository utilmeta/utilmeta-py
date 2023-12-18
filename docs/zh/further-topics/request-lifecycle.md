# 一个请求的生命周期


请求的校验与解析：一个请求在执行到Unit内部的函数逻辑之前，UtilMeta框架会进行一系列的解析和校验工作，

- HTTP方法是否匹配，不匹配则会返回405
- 如果函数声明了path，请求路径是否匹配路径或正则，不匹配会返回404

- 如果函数声明了before钩子，会进行自定义的检测，往往对请求头和cookies等进行检测，拒绝不符合的请求
- 如何是模块函数单元，会结合查询的资源进行权限校验，对不满足权限的会返回403

- 进行请求参数的转化，对于函数中声明的路径参数，查询参数，请全体，请求头等参数进行解析和转化，如果不符合校验，则会拒绝请求，返回400等错误
- 执行Unit会进行请求控制的校验，对请求次数超限，频率超限，以及其他Request组件中声明的规则进行检测，拒绝不符合的请求



对于以上条件都符合的请求，该请求的方法，路径，参数。权限，请求控制，预检测等全部通过，可以安全有效地执行函数中的内容




### 请求的生命周期
一个 HTTP 请求在 UtilMeta 框架中都需要经过哪些处理步骤，直到最后生成响应返回给客户端
这个过程中绝大多数步骤都是在 UtilMeta 框架以及其他底层库中完成的，


**进入框架前发生了什么**？
一个请求在进入服务器之前还可能经过多个代理，网关或负载均衡等，这些不在我们的讨论返回之内，我们仅关注当请求进入到你的服务所在的主机后发生了什么
1. 服务所在的主机在某个端口接到一个 HTTP 请求，
2. 如果处理请求的是 Nginx / Apache 等 Web 服务器，它会查找配置中的路径匹配规则，并分发到对应的文件，对于 UtilMeta (python) 来说，我们关注的是 API 请求，这类请求一般会转发到当前主机上的一个端口或者一个本地 sock 文件
3. WSGI 服务（uWSGI / Gunicorn）等根据配置文件监听一个端口或 socket 文件，当收到下游的请求时，处理并调用配置好的 wsgi application，这个应用就是 UtilMeta 框架（依赖的 django）给出的应用

**在框架中的生命周期**



### 控制请求流程

在调用你的接口处理函数之前，UtilMeta 框架需要根据你的声明和配置作一些处理，来保证调用到你的函数的请求都符合你声明的规则和权限，并且
* **加载用户**：会根据你配置（conf.Auth）的鉴权策略（如 Session / Signature / JWT 等）来解析请求，从请求 Cookie，Session 或请求头中信息加载请求的用户，完成这一步后，你可以通过 `self.request.user_id` 访问到请求的用户 ID
* **请求控制**：会根据你在 Request 组件中配置的请求控制参数对请求进行检测和鉴权，拒绝非法请求
* **参数解析**：会根据你的接口函数声明的参数来解析请求路径，查询参数，请求体和请求头，并将其转化和映射为对应的函数参数
完成了以上这几步没有异常抛出的话，这个请求就是一个正常的合法请求，接下来就是调用你的 API 函数了

**调整请求流程**
由于以上的请求流程是在完成了 API 路由后，找到了对应的 Unit 后再执行的，所以在执行之前，也就是在你编写的处理前（`@api.before`）钩子中，会存在一定的限制
* 在加载用户之前，你在 before 钩子中访问 request.user_id 时，会直接触发用户加载，如果你直接对 user_id 进行赋值，那么之后就不会触发用户加载，而是会使用你赋的这个 ID 作为请求用户 
* 在请求控制应用之前，执行你的 before 钩子中的逻辑的请求可能不符合你的请求控制规则或者权限要求，所以建议不要在 before 钩子中执行需要严格权限的操作，除非你主动进行验证，事实上 before 钩子的另一个作用就是可以在请求处理执行之前对请求进行自定义的预处理，比如改变其中某些参数的值，这样也可能使得一个原本无法通过请求处理的请求变得能够通过，比如自定义的管理员密钥等
* 在参数解析之前，你通过 `self.request.query` 访问到的查询参数没有进行过类型解析和转化，也就是说这个字典的值全部都是字符串类型的，同理请求体和请求头数据也还没有得到解析，所以不要在 before 钩子中直接使用这些数据执行操作，这些数据也都是未转化到 Schema 类的原始数据，所以你访问字典数据的方式只能是用键名称，而不能是属性名称

当然以上的 before 钩子指的都是 API 中的 before 钩子，因为模块的  before 钩子的主要作用之一就是直接对数据作出预处理，所以传入到模块 before 钩子的数据是已经转化到 schema 的，你可以直接访问它的属性


需要额外注意的是，这些加载请求的步骤会对非法的请求**抛出错误**，也就是说当你将处理请求的步骤提前时，非法请求的错误也会同样在你触发相应的加载流程时抛出，这时你

```python
class UserAPI(self):
	@api.post
	def logout(self):
		pass

	@api.handle(logout)
	def handle_logout(self):
		pass

class RootAPI(API):
	user = UserAPI
	
	@api.before(user)
	def check(self):
		if not self.request.user_id:
			raise exc.Unauthorized()

```

在 check 钩子中抛出的错误不会被 UserAPI 中的错误处理钩子所捕获，因为在抛出错误时，调用尚未进行到 UserAPI 之内


API 路由的核心流程简化的伪代码如下
```python
def __call__(self):
	handler, before_hooks, after_hooks, error_hooks = self.__resolve__()
	
	try:  
		for hook in before_hooks:  
			hook(self, **parse_headers())  
			
	    result = handler(self)  
	    
	    for hook in after_hooks:  
	        result = hook(self, result) or result  
	  
	except Exception as e:  
	    error = Error(e)  
	    hook = error.get_hook(error_hooks) 
	     
	    if not hook:  
	        raise error.throw()  
	        
	    result = hook(self, error)
	    
	return self.generate_response(result)
```



## 请求的路由解析

请求路由与方法的声明和解析是 API 类的核心功能

```python
class TestAPI(API):
    # GET:patch
    @api.get("patch")  # http method as route
    def get_patch(self) -> str:
        return self.request.path

    # DELETE:patch
    @api.delete(get_patch)   # same route reference
    def delete_patch(self) -> str:
        return self.request.path

    # DELETE:@file:{0}
    @api.delete("@file:{0}")    # path param (with slash) in route
    def file_alias(self, path: str = Request.PathParam) -> bool:
        return self.media.delete(path=path)

    # GET:doc/{category}/{page}
    @api.get(path="{category}/{page}")   # path
    def doc(self, category: str, page: int = 1) -> Dict[str, int]:
        return {category: page}
        
    # relpath: GET:query
    @api.get  # function name as route
    def query(self, page: int, item: str = Rule(default="default")) -> Tuple[int, str]:
        return page, item
    
    # function name is http method
    # relpath: POST:
    def post(self, data: FormSchema = Request.Body) -> str:
        pass

    # relpath: GET:{path}
    def get(self, path: str = Request.PathParam):
        # fallback 
        pass
```


**非法声明**
```python
class _API(API):    # noqa
    @api.get
    def request(self):
        pass
        
    @api.post
    def get(self):
        pass
        
    @api('route')
    def get(self):
        pass
```


#### 为什么不支持一个函数多种 HTTP 方法

我们可以使用一个 API 类来处理一个路径中多种方法的情况，但为什么框架不支持一个函数声明多种 HTTP 方法呢？
首先在设计上，我们希望 API 接口尽量保持语义化，原子化，这样不仅方便扩展与集成，也方便运维监控和管理，所以我们会按照 **HTTP方法+相对路径** 为每个 API 函数生成一个端点（Endpoint）标识，用于接口请求的监控与分析，如果一个接口函数可以使用多种 HTTP 方法访问

其次，对于多个 HTTP 方法共用一套逻辑的情况，API 也能够方便地处理，并且提供了后续声明细粒度的钩子和调控的扩展能力，如
```python
class HttpBinAPI(API):
    def handle(self):
        form, files = {}, {}
        if self.request.is_form and isinstance(self.request.data, dict):
            for key, val in self.request.data.items():
                if isinstance(val, list):
                    files[key] = [v.read() for v in val]
                else:
                    form[key] = val

        return {
            'url': self.request.url,
            'args': self.request.query,
            'data': self.request.original_body,
            'origin': self.request.ip,
            'json': self.request.data if self.request.is_json else None,
            'form': form,
            'files': files,
            'headers': self.request.headers
        }

    def get(self):
        return self.handle()

    def put(self):
        return self.handle()

    def post(self):
        return self.handle()

    def patch(self):
        return self.handle()

    def delete(self):
        return self.handle()
```

如果你要额外对其中的几个 HTTP 方法应用钩子，你依然可以直接使用钩子语法，但如果使用一个函数包含多种方法的方式，就只能在函数中自行判断和调用了

however，如果你使用了自定义的 HTTP 动词方法，可以使用
```python
class CustomAPI(API):
    @api(method='EXECUTE')
    def exe(self, path: str):
        pass
```

::: tip
目前暂不支持完全动态的 HTTP 动词方法，你需要将支持的动词都进行声明
:::

#### 路径匹配

* 挂载的 API：根据


#### 正则路径

很多时候路径参数需要按照正则规则来匹配，你可以定义一段正则表达式作为路径，

* 将路径声明为一个正则表达式
* 将路径声明为路径参数，然后在函数中声明参数的的具体规则，其中包括了正则表达式（`regex`）

这两种方式的区别是，如果你直接将路径声明为正则，而请求路径没有匹配，最后会抛出 404 错误，但是当你声明了路径参数，请求路径匹配了参数后，没有匹配参数的具体的正则规则，此时会按照参数解析失败处理，抛出 400 BadRequest

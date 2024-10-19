# 声明式 Web 客户端

UtilMeta 框架不仅提供了 API 类用于服务端接口的开发，还提供了一个与 API 类语法相近的 `Client` 类，用于开发对接 API 接口的客户端请求代码

与声明式接口一样，`Client` 类是一个声明式的客户端，只需要将目标接口的请求参数和响应模板声明到函数中，`Client` 类就会自动完成 API 请求的构建和响应的解析

!!! tip
	在 UtilMeta 中 `API` 类和 `Client` 类类似的不仅仅是语法，它们使用的 `Request` 和 `Response` 对象也是同一个类。没错，这样会降低开发者的心智成本，也能方便复用

## `Client` 参数


* `base_url`
* `backend`：可以传入一个请求库，默认是 urllib，目前支持的请求库包括 requests, aiohttp, httpx
* `service`
* `append_slash`
* `default_timeout`
* `base_headers`
* `base_cookies`
* `base_query`
* `proxies`
* `allow_redirects`
* `fail_silently`：若设为 True，当响应数据无法解析为声明的响应模板类时，不抛出错误，而是返回一个通用的 `Response` 类


## 根据 OpenAPI 文档生成 Client 代码
# 版本规划 RoadMap

## 长期功能规划

### WebSocket / SSE

* 支持声明式语法编写 WebSocket / SSE / Server Push 接口
* 支持 WebSocket / SSE 接口的文档生成与调试

### GraphQL

* 支持 `orm` 模块快速构建 GraphQL 查询接口
* 支持 GraphQL 接口的文档生成与调试

### ORM 支持

* **SQLAchemy**
* **Peewee**

### 运行时 backend 支持

* **Bottle.py**
* **Pyramid**

### 运维管理系统

* 服务端自定义或推送报警规则进行实时报警通知
* 支持接入现有的日志与监控数据源（如 ElasticSearch 与 Prometheus）
* 对测试场景服务端能力的完善，如测试库，测试日志，压测处理


## 后续版本规划

### v2.8

**新特性**

* 支持部署所需的 uwsgi 和 gunicorn 配置文件的自动生成 
* 支持服务端自定义或推送报警规则进行实时报警通知

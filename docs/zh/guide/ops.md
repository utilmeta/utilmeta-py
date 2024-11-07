# 运维监控与服务管理



### `base_url`
* 你可以强制给 `Operations` 指定一个 `base_url`，那么服务的 `base_url` 就是这个值，OpenAPI 文档会根据这个 URL 进行调整，但如果这个 `base_url` 比某些 API 的路径还要远，那么那些 API 将无法被管理平台访问到

如果 Operations 指定了 `base_url` 那么 `route` 的相对路径就是这个  `base_url`

ops_api = base_url + route

如果 route 是绝对 URL，则 ops_api = route

### OpenAPI


## 连接方式

### UtilMeta 框架

```python
from utilmeta import UtilMeta
from utilmeta.core import api
import django

class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=django,    # or flask / starlette / tornado / sanic
    api=RootAPI,
    route='/api'
)

import os
from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name=os.path.join(service.project_dir, 'operations_db'),
        engine='sqlite3'
        # or 'postgres' / 'mysql' / 'oracle'
    ),
    base_url='https://blog.mysite.com/api',
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
```

### Django


wsgi.py
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# NEW -----------------------------------
from utilmeta.ops import Operations
from .settings import BASE_DIR
Operations(
    route='ops',
    database=Operations.Database(
        name=os.path.join(BASE_DIR, 'operations_db'),
        engine='sqlite3'
        # or 'postgres' / 'mysql' / 'oracle'
    ),
    base_url='https://blog.mysite.com/api',
).integrate(application, __name__)
```

### Flask


### FastAPI

```python
from fastapi import FastAPI

app = FastAPI()

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    base_url='https://<YOUR DOMAIN>/api',
).integrate(app, __name__)
```

### Sanic


## 平台概念

### API 服务 `Service`


### UtilMeta 节点 `Node`


### 环境 `Environment`


### 服务实例 `Instance`

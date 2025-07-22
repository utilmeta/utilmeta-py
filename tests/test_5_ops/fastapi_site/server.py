from fastapi import FastAPI
import os
import sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(__file__))

app = FastAPI(root_path='/api')

PORT = 9092


@app.get("/items/{item_id}")
async def read_item(item_id) -> dict:
    return {"item_id": item_id}

from utilmeta.ops import Operations
from tests.conftest import get_operations_db
Operations(
    route='v1/ops',
    database=get_operations_db(),
    secure_only=False,
    trusted_hosts=['127.0.0.1'],
    base_url=f'http://127.0.0.1:{PORT}/api',
    eager_migrate=True
).integrate(app, __name__)
# avoid this route override all the following routes


@app.get("/hello")
async def hello_world() -> str:
    return 'world'


if __name__ == '__main__':
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()
    import uvicorn
    uvicorn.run(app, port=PORT)

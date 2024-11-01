from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}

from utilmeta.ops import Operations
import os
Operations(
    route='v1/ops',
    database=Operations.Database(
        name=os.path.join(os.path.dirname(__file__), 'db_ops'),
        engine='sqlite3'
    ),
    secure_only=False,
    trusted_hosts=['127.0.0.1']
).integrate(app, __name__)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app)

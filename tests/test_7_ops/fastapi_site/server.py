from fastapi import FastAPI

app = FastAPI()

PORT = 9092


@app.get("/items/{item_id}")
async def read_item(item_id) -> dict:
    return {"item_id": item_id}

from utilmeta.ops import Operations
Operations(
    route='v1/ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    secure_only=False,
    trusted_hosts=['127.0.0.1'],
    base_url=f'http://127.0.0.1:{PORT}',
    eager=True
).integrate(app, __name__)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=PORT)

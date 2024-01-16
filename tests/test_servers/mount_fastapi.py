from fastapi import FastAPI

fastapi_app = FastAPI()


@fastapi_app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}

from utilmeta import UtilMeta
from utilmeta.core import api, response


class RootAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'error'

    @api.get
    def hello(self):
        return 'Hello, UtilMeta!'


service = UtilMeta(
    __name__,
    backend=fastapi_app,
    api=RootAPI
)

if __name__ == '__main__':
    service.run()

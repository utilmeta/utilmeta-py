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
    name='mount_fastapi',
    backend=fastapi_app,
    api=RootAPI
)

from tests.conftest import make_live_thread
server_thread = make_live_thread(service)

# fixme: Invalid HTTP request received
# def test_fastapi(server_thread):
#     with service.get_client(live=True) as client:
#         r1 = client.get('/items/3')
#         r1.print()
#         assert r1.status == 200
#         assert r1.data == {"item_id": 3}
#
#         r2 = client.get('/hello')
#         assert r2.status == 200
#         assert isinstance(r2.data, dict)
#         assert r2.data.get('data') == 'Hello, UtilMeta!'


if __name__ == '__main__':
    import pprint
    pprint.pprint(
        service.adaptor.generate()
    )
    # service.run()

from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id):
    return {"item_id": item_id}


from utilmeta.core import api, response


class CalcAPI(api.API):
    class response(response.Response):
        result_key = 'data'
        message_key = 'msg'

    @api.get
    def add(self, a: int, b: int) -> int:
        return a + b

    def get(self):
        return self.request.path


CalcAPI.__as__(app, route='/calc')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app)

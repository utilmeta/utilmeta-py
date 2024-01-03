from utilmeta.core import api
from utilmeta.utils import awaitable


class QueryAPI(api.API):
    pass


class OperationsAPI(api.API):
    def post(self):
        pass

    def get(self):
        pass

    @awaitable(get)
    async def get(self):
        pass

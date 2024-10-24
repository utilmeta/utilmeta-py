from utilmeta.core.api.hook import Hook, BeforeHook, AfterHook, ErrorHook
from utilmeta.core.request import Request
from utilmeta import utils


class ClientBeforeHook(BeforeHook):
    target_type = 'client'

    def serve(self, client, /, request: 'Request' = None):
        if not request:
            return
        args, kwargs = self.parse_request(request)
        return self(client, request, *args, **kwargs)

    @utils.awaitable(serve)
    async def serve(self, client, /, request: 'Request' = None):
        if not request:
            return
        args, kwargs = await self.parse_request(request)
        return await self(client, request, *args, **kwargs)


class ClientAfterHook(AfterHook):
    target_type = 'client'


class ClientErrorHook(ErrorHook):
    target_type = 'client'

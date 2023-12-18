from utilmeta.core.api import API
from utilmeta.utils.common import awaitable
from channels.generic.websocket import WebsocketConsumer


class Websocket(API):
    def send(self):
        pass

    @awaitable(send)
    async def send(self):
        pass

    def accept(self):
        pass

    @awaitable(accept)
    async def accept(self):
        pass

    def receive(self):
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

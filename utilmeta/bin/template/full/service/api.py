from utilmeta.core import api

{plugins}  # noqa


class RootAPI(api.API):
    @api.get
    def hello(self):
        return "world"

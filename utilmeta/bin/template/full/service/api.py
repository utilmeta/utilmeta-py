from utilmeta.core import api


class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

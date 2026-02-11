from utilmeta.core import api, request, orm
from .utils import opsRequire, config
from utilmeta.utils import adapt_async


class ActionAPI(api.API):
    @api.post('/{action_name}')
    @opsRequire("action.execute")
    @adapt_async(close_conn=config.db_alias)
    def execute_action(self, action_name: str, data: dict = request.Body):
        pass

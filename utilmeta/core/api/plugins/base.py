from utilmeta.utils import PluginBase, Error, PluginTarget, PluginEvent, exceptions
from utilmeta.core.request import Request
from utilmeta.core.response import Response


process_response = PluginEvent('process_response', streamline_result=True)
process_request = PluginEvent('process_request', streamline_result=True)
handle_error = PluginEvent('handle_error')


class APIPlugin(PluginBase):
    # can be executed multiple time in one request

    def process_request(self, request: Request):
        pass

    def process_response(self, response: Response):
        pass

    def handle_error(self, error: Error):
        pass

    # def inject_endpoints(self, target_class):
    #     pass

    def inject(self, target_class):
        # inject to the endpoints
        from ..base import API
        if isinstance(target_class, type) and issubclass(target_class, API):
            for route in target_class._routes:
                self.inject(route.handler)
        elif isinstance(target_class, PluginTarget):
            # only injected to endpoints
            target_class._plugin(self, setdefault=True)
        return target_class

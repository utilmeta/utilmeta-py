import fastapi
from fastapi import FastAPI
from .starlette import StarletteServerAdaptor


class FastAPIServerAdaptor(StarletteServerAdaptor):
    backend = fastapi
    application_cls = FastAPI
    app: FastAPI

    def generate(self, spec: str = 'openapi'):
        if spec == 'openapi':
            app: FastAPI = self.application()
            app.openapi_schema = None   # clear cache
            return app.openapi()

    @property
    def root_path(self) -> str:
        return str(getattr(self.app, 'root_path', '') or '').strip('/')

    @property
    def version(self) -> str:
        return getattr(self.app, 'version', '')

    # def load_route(self, request):
    #     path = request.path_params.get('path') or request.url.path
    #     root_path = self.root_path
    #     if root_path:
    #
    #     return super().load_route(path)

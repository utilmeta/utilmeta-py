import fastapi
from fastapi import FastAPI
from .starlette import StarletteServerAdaptor


class FastAPIServerAdaptor(StarletteServerAdaptor):
    backend = fastapi
    application_cls = FastAPI

    def generate(self, spec: str = 'openapi'):
        if spec == 'openapi':
            app: FastAPI = self.application()
            return app.openapi()

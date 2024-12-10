from flask import Flask

from .flask import FlaskServerAdaptor
from apiflask import APIFlask
import apiflask


class APIFlaskServerAdaptor(FlaskServerAdaptor):
    backend = apiflask
    application_cls = APIFlask
    app: APIFlask

    def generate(self, spec: str = "openapi"):
        if spec == "openapi":
            app: APIFlask = self.application()
            return app._get_spec("json", force_update=True)

    def add_api(
        self,
        app: APIFlask,
        utilmeta_api_class,
        route: str = "",
        asynchronous: bool = False,
    ):
        f = super().add_api(
            app, utilmeta_api_class, route=route, asynchronous=asynchronous
        )
        # spec = getattr(f, '_spec', None)
        f._spec = {"hide": True}
        return f

    @property
    def version(self) -> str:
        return self.app.version

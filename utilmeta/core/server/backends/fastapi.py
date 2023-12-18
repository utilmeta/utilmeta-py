import fastapi
from fastapi import FastAPI
from .starlette import StarletteServerAdaptor


class FastAPIServerAdaptor(StarletteServerAdaptor):
    backend = fastapi
    application_cls = FastAPI

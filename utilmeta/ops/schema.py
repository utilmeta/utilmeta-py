from utype import Schema, Field


class ServiceData(Schema):
    openapi: dict
    models: dict

    instances: list
    servers: list

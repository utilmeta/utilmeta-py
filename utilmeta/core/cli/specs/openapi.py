"""
Generate client code based on OpenAPI document
"""


class OpenAPIClientGenerator:
    __version__ = '3.1.0'
    FORMATS = ['json', 'yaml']
    PARAMS_IN = ['path', 'query', 'header', 'cookie']

    # None -> dict
    # json -> json string
    # yml -> yml string

    def __init__(self, openapi: dict):
        self.openapi = openapi

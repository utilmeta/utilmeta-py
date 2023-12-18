from utype import register_encoder

try:
    from psycopg2._json import Json     # noqa

    @register_encoder(Json)
    def from_iterable(encoder, data):
        return data.adapted

except (ImportError, ModuleNotFoundError):
    pass

from utype import register_encoder

try:
    from psycopg2._json import Json  # noqa

    @register_encoder(Json)
    def from_psycopg2_json(encoder, data):
        return data.adapted

except (ImportError, ModuleNotFoundError):
    pass


try:
    from psycopg.types.json import Json, Jsonb

    @register_encoder(Json, Jsonb)
    def from_psycopg_json(encoder, data):
        return data.obj

except (ImportError, ModuleNotFoundError):
    pass

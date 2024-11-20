__spec_version__ = '0.3.0'
__website__ = 'https://ops.utilmeta.com'

from .config import Operations


def init_models():
    import django
    if django.VERSION < (3, 1):
        from django.db.models import Field, PositiveIntegerField

        class JSONField(Field):
            def __init__(self, verbose_name=None, name=None, encoder=None, decoder=None, **kwargs):
                from utype.utils.encode import JSONEncoder
                self.encoder = encoder or JSONEncoder
                self.decoder = decoder
                super().__init__(verbose_name, name, **kwargs)

            def get_internal_type(self):
                # act like TextField
                # return 'JSONField'
                return 'TextField'

            def db_type(self, connection):
                return 'text'

            def from_db_value(self, value, expression, connection):
                if value is not None:
                    return self.to_python(value)
                return value

            def to_python(self, value):
                import json
                if value is not None:
                    try:
                        return json.loads(value)
                    except (TypeError, ValueError):
                        return value
                return value

            def get_prep_value(self, value):
                import json
                if value is not None:
                    return json.dumps(value, cls=self.encoder, ensure_ascii=False)
                return value

            def value_to_string(self, obj):
                return self.value_from_object(obj)

            def get_db_prep_value(self, value, connection, prepared=False):
                import json
                if value is not None:
                    return json.dumps(value, cls=self.encoder, ensure_ascii=False)
                return value

        django.db.models.JSONField = JSONField
        django.db.models.PositiveBigIntegerField = PositiveIntegerField


init_models()

import sys
import os
import warnings
import django


def patch_model_fields(service):
    if sys.version_info >= (3, 9) or os.name != "nt":
        if django.VERSION >= (3, 1):
            return

    # sqlite in-compat
    from utilmeta.core.orm import DatabaseConnections

    dbs = service.get_config(DatabaseConnections)
    if dbs:
        has_sqlite = False
        has_not_sqlite = False
        for val in dbs.databases.values():
            if val.is_sqlite:
                has_sqlite = True
            else:
                has_not_sqlite = True
        if not has_sqlite:
            return
        if has_not_sqlite:
            if django.VERSION >= (3, 1):
                warnings.warn(
                    f"You are using mixed database engines with sqlite3 in Windows under Python 3.9, "
                    f"JSONField cannot operate properly"
                )
                return

    from django.db import models
    from utype import JSONEncoder

    class RawJSONField(models.Field):
        def __init__(
            self, verbose_name=None, name=None, encoder=None, decoder=None, **kwargs
        ):
            self.encoder = encoder or JSONEncoder
            self.decoder = decoder
            super().__init__(verbose_name, name, **kwargs)

        def get_internal_type(self):
            # act like TextField
            # return 'JSONField'
            return "TextField"

        def db_type(self, connection):
            return "text"

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

    models.JSONField = RawJSONField
    if django.VERSION < (3, 1):
        from django.db.models import PositiveIntegerField

        models.PositiveBigIntegerField = PositiveIntegerField

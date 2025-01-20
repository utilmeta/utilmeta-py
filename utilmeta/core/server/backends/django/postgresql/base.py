from django.db.backends.postgresql.base import DatabaseWrapper as BaseDatabaseWrapper
from django.db.backends.postgresql.operations import DatabaseOperations
from utype.utils.encode import JSONEncoder
import json


class PostgresDatabaseOperations(DatabaseOperations):
    json_ensure_ascii = False
    json_skipkeys = True

    def adapt_json_value(self, value, encoder):
        if value is None:
            return value
        # compat django >= 4.2
        return json.dumps(
            value,
            cls=JSONEncoder,
            ensure_ascii=self.json_ensure_ascii,
            skipkeys=self.json_skipkeys,
        )


class DatabaseWrapper(BaseDatabaseWrapper):
    ops_class = PostgresDatabaseOperations

from django.db.backends.postgresql.base import DatabaseWrapper as BaseDatabaseWrapper
from django.db.backends.postgresql.operations import DatabaseOperations
import json


class PostgresDatabaseOperations(DatabaseOperations):
    def adapt_json_value(self, value, encoder):
        if value is None:
            return value
        # compat django >= 4.2
        return json.dumps(value)


class DatabaseWrapper(BaseDatabaseWrapper):
    ops_class = PostgresDatabaseOperations

from utilmeta.conf import Config
from utilmeta.core.orm.databases.config import Database, DatabaseConnections
from utype.types import *
from utilmeta.utils import DEFAULT_SECRET_NAMES, url_join, localhost
from typing import Union
from urllib.parse import urlsplit
from utilmeta import UtilMeta


class Operations(Config):
    def __init__(self, route: str,
                 database: Union[str, Database],
                 disabled_scope: List[str] = (),
                 secret_names: List[str] = DEFAULT_SECRET_NAMES,
                 ):
        super().__init__(**locals())

        self.route = route
        self.database = database if isinstance(database, Database) else None
        self.db_alias = database if isinstance(database, str) else '__ops'

        self.disabled_scope = set(disabled_scope)
        self.secret_names = secret_names

    def setup(self, service: UtilMeta):
        dbs_config = service.get_config(DatabaseConnections)
        if dbs_config:
            if self.database:
                dbs_config.databases.setdefault(self.db_alias, self.database)
            else:
                self.database = dbs_config.databases.get(self.db_alias)
                if not self.database:
                    raise ValueError(f'Operations config: database required, got invalid {repr(self.db_alias)}')
        else:
            if not self.database:
                raise ValueError(f'Operations config: database required, got invalid {repr(self.db_alias)}')
            service.use(DatabaseConnections({
                self.db_alias: self.database
            }))

    @property
    def ops_api(self):
        parsed = urlsplit(self.route)
        if parsed.scheme:
            # is url
            return self.route
        try:
            from utilmeta import service
        except ImportError:
            return None
        base_url = service.base_url
        return url_join(base_url, self.route)

    def check_host(self):
        parsed = urlsplit(self.ops_api)
        if localhost(parsed.hostname):
            return False
        return True

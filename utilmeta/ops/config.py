from utilmeta.conf import Config
from utilmeta.core.orm.databases.config import Database
from utype.types import *
from utilmeta.utils import DEFAULT_SECRET_NAMES


class Operations(Config):
    def __init__(self, route: str,
                 database: Database,
                 disabled_scopes: List[str] = (),
                 secret_names: List[str] = DEFAULT_SECRET_NAMES,
                 ):
        super().__init__(**locals())

        self.route = route
        self.database = database

        self.disabled_scopes = disabled_scopes
        self.secret_names = secret_names

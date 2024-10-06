from utype import DataClass
from utype.types import *


class QueryContext(DataClass):
    using: Optional[str] = None
    includes: Optional[dict] = None
    excludes: Optional[dict] = None
    single: bool = False
    recursion_map: Optional[dict] = None
    force_expressions: Optional[dict] = None
    force_raise_error: bool = False
    integrity_error_cls: Optional[Type[Exception]] = None

    # @classmethod
    # def init(cls):
    #     return cls()

    def in_scope(self, aliases: List[str], dependants: List[str] = None):
        if not aliases:
            return False
        if self.includes:
            return bool(set(aliases).union(dependants or []).intersection(self.includes))
        if self.excludes:
            return not set(aliases).intersection(self.excludes)
        return True

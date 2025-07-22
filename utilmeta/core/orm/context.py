from utype import DataClass
from utype.types import *
from utilmeta.utils import merge_dict


class QueryContext(DataClass):
    using: Optional[str] = None
    includes: Optional[dict] = None
    excludes: Optional[dict] = None
    single: bool = False
    recursion_map: Optional[dict] = None
    relation_routes: Optional[List[Tuple[str, type]]] = None
    # reduce the redundant query using [schema_cls] + [PK] identification
    force_expressions: Optional[dict] = None
    force_raise_error: bool = False
    integrity_error_cls: Optional[Type[Exception]] = None
    # distinct: bool = False
    gather_async_fields: Optional[bool] = None
    depth: int = 0

    def __init__(
        self,
        using: Optional[str] = None,
        includes: Optional[dict] = None,
        excludes: Optional[dict] = None,
        single: bool = False,
        recursion_map: Optional[dict] = None,
        relation_routes: Optional[List[Tuple[str, type]]] = None,
        force_expressions: Optional[dict] = None,
        force_raise_error: bool = False,
        integrity_error_cls: Optional[Type[Exception]] = None,
        gather_async_fields: Optional[bool] = None,
        depth: int = 0,
    ):
        super().__init__(locals())

    def in_scope(
        self,
        aliases: List[str],
        dependants: List[str] = None,
        default_included: bool = True
    ):
        if not aliases:
            return False
        if self.includes:
            return bool(
                set(aliases).union(dependants or []).intersection(self.includes)
            )
        if self.excludes:
            return not set(aliases).intersection(self.excludes)
        return default_included

    def merge(self, context: "QueryContext" = None) -> "QueryContext":
        if not isinstance(context, QueryContext):
            return self
        return self.__class__(
            using=self.using or context.using,
            includes=merge_dict(self.includes, context.includes, null=True),
            excludes=merge_dict(self.excludes, context.excludes, null=True),
            single=self.single or context.single,
            recursion_map=merge_dict(
                self.recursion_map, context.recursion_map, null=True
            ),
            force_expressions=merge_dict(
                self.force_expressions, context.force_expressions, null=True
            ),
            force_raise_error=self.force_raise_error or context.force_raise_error,
            integrity_error_cls=self.integrity_error_cls or context.integrity_error_cls,
            gather_async_fields=self.gather_async_fields or context.gather_async_fields,
            depth=self.depth,
            relation_routes=self.relation_routes or context.relation_routes,
        )

    def __and__(self, other):
        return self.merge(other)

from .parser import QueryClassParser
from .fields.filter import ParserFilter
from .fields.order import Order, ParserOrderBy
from .fields.pagination import Page, Limit, Offset
from .fields.scope import Scope
from typing import TYPE_CHECKING
from .context import QueryContext
from utilmeta.utils import multi
from utilmeta.conf import Preference


if TYPE_CHECKING:
    from .backends.base import ModelFieldAdaptor


class BaseQuerysetGenerator:
    def __init__(
        self,
        parser: QueryClassParser,
        values: dict,
        # --- config params
        distinct: bool = None,
        using: str = None,
        **kwargs
    ):
        self.parser = parser
        self.model = parser.model
        self.values = values

        if distinct is None:
            pref = Preference.get()
            distinct = pref.orm_default_query_distinct

        self.distinct = distinct
        self.using = using
        self.kwargs = kwargs

        self.page = None
        self.limit = None
        self.offset = None
        self.includes = None
        self.excludes = None

    def process_data(self):
        for key, value in self.values.items():
            field = self.parser.get_field(key)
            if field:
                self.process_value(field, value)

    def __call__(self, *args, **kwargs):
        return self.get_queryset()

    def get_queryset(self, base=None):
        raise NotImplementedError

    def count(self, base=None) -> int:
        raise NotImplementedError

    # @awaitable(count)
    async def acount(self, base=None) -> int:
        raise NotImplementedError

    def get_context(self, **kwargs):
        kwargs.update(includes=self.includes, excludes=self.excludes, using=self.using)
        return QueryContext(**kwargs)

    @property
    def slice(self) -> slice:
        offset = self.offset
        if offset is None:
            if self.page and self.limit:
                offset = (self.page - 1) * self.limit
        if offset is not None:
            if self.limit:
                if self.page:
                    offset = max(offset, (self.page - 1) * self.limit)
                return slice(offset, offset + self.limit)
            else:
                return slice(offset, None)
        elif self.limit:
            return slice(0, self.limit)
        return slice(0, None)

    def process_filter(self, field: ParserFilter, value):
        raise NotImplementedError

    def process_order(
        self, order: Order, field: "ModelFieldAdaptor", name: str, flag: int = 1
    ):
        raise NotImplementedError

    def process_value(self, field, value):
        if isinstance(field, ParserFilter) and field.filterable:
            self.process_filter(field, value=value)
        elif isinstance(field, ParserOrderBy):
            if not multi(value):
                value = [value]
            for o in value:
                if o in field.orders:
                    order, f, flag = field.orders[o]
                    self.process_order(
                        order, field=f, flag=flag, name=str(o).lstrip(field.desc_prefix)
                    )
        elif isinstance(field.field, Page):
            self.page = value
        elif isinstance(field.field, Offset):
            self.offset = value
        elif isinstance(field.field, Limit):
            self.limit = value
        elif isinstance(field.field, Scope):
            if field.field.excluded:
                self.excludes = Scope.get_scope_value(value)
            else:
                self.includes = Scope.get_scope_value(value)

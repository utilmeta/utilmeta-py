from .parser import SchemaClassParser
from .fields.field import ParserQueryField
from .context import QueryContext
from typing import List, Any, Dict
from utilmeta.utils import awaitable
from utype import unprovided


class BaseQueryCompiler:
    def __init__(self, parser: SchemaClassParser, queryset, context: QueryContext = None):
        self.parser = parser
        self.model = parser.model
        self.queryset = queryset
        self.context = context or QueryContext()
        self.recursive_map: Dict[Any, Dict[Any, dict]] = self.context.recursion_map or {}
        self.pk_list = []
        self.pk_map = {}
        # self.recursive_pk_list = []
        self.recursively = False
        self.values: List[dict] = []

    @property
    def ident(self):
        return self.parser.obj

    def get_related_context(self, field: ParserQueryField,
                            force_expressions: dict = None,
                            force_raise_error: bool = False):
        includes = excludes = None
        if self.context.includes:
            inter = set(self.context.includes).intersection(field.all_aliases)
            includes = self.context.includes.get(inter.pop()) if inter else None
        if self.context.excludes:
            inter = set(self.context.excludes).intersection(field.all_aliases)
            excludes = self.context.excludes.get(inter.pop()) if inter else None
        return QueryContext(
            using=self.context.using,
            # single=field.related_single,
            single=False,       # not make it single, related context is always about multiple
            includes=includes,
            excludes=excludes,
            recursive_map=self.recursive_map,
            force_expressions=force_expressions,
            force_raise_error=force_raise_error or self.context.force_raise_error
        )

    def _resolve_recursion(self):
        recursion_map = self.recursive_map
        # recursion map is isolated among fields
        if recursion_map and self.ident in recursion_map:
            recursive_pks = recursion_map.get(self.ident)
            recursive_pks.update(self.pk_map)
            # across = recursive_pks.intersection(self.pk_list)
            # if across:
            #     warnings.warn(f'{self}: execute query detect recursive ({across}), these objects '
            #                   f'will not recursively included in the result')
            #     self.recursive_pk_list = [pk for pk in self.pk_list if pk not in across]
            #     if not self.pk_list:
            #         # directly return
            #         return []
            # update the reset pk list
            # recursive_pks.update(self.pk_list)
        elif self.recursively:
            recursion_map = recursion_map or {}
            recursion_map[self.ident] = dict(self.pk_map)
        self.recursive_map = recursion_map

    def base_queryset(self):
        return self.model.get_queryset()

    def process_query_field(self, field: ParserQueryField):
        if field.related_schema:
            self.recursively = True

    def process_fields(self):
        for name, field in self.parser.fields.items():
            if not isinstance(field, ParserQueryField):
                continue
            if not field.readable:
                continue
            if not self.context.in_scope(field.all_aliases, dependants=field.dependants):
                continue
            self.process_query_field(field)

    def get_values(self) -> List[dict]:
        raise NotImplementedError

    @awaitable(get_values)
    async def get_values(self) -> List[dict]:
        raise NotImplementedError

    def process_data(self, data: dict):
        if not isinstance(data, dict):
            return {}
        if not isinstance(data, self.parser.obj):
            data = self.parser(data)
        result = {}
        for key, val in data.items():
            field = self.parser.get_field(key)
            if not isinstance(field, ParserQueryField):
                continue
            if not field.writable and not field.primary_key:
                continue
            name = field.model_field.column_name
            # fk will be fk_id in this case
            if not isinstance(name, str):
                continue
            value = self.process_value(field, val)
            if not unprovided(value):
                result[name] = value
        return result

    def process_value(self, field: ParserQueryField, value):
        return value

    def commit_data(self, data):
        raise NotImplementedError

    @awaitable(commit_data)
    async def commit_data(self, data):
        raise NotImplementedError

    def save_data(self, data, must_create: bool = False, must_update: bool = False):
        raise NotImplementedError

    @awaitable(save_data)
    async def save_data(self, data, must_create: bool = False, must_update: bool = False):
        raise NotImplementedError

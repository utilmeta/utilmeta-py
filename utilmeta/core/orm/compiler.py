from .parser import SchemaClassParser
from .fields.field import ParserQueryField
from .context import QueryContext
from typing import List, Any, Dict, Tuple, Type, Union, TYPE_CHECKING
from utilmeta.utils import awaitable
from utype import unprovided

if TYPE_CHECKING:
    from .backends.base import ModelAdaptor


class TransactionWrapper:
    def __init__(self, model: 'ModelAdaptor', transaction: Union[str, bool] = False, errors_map: dict = None):
        # self.enabled = bool(transaction)
        db_alias = None
        if isinstance(transaction, str):
            db_alias = transaction
        elif transaction:
            # get the default db
            db_alias = model.default_db_alias
        # if not db_alias:
        #     self.enabled = False
        self.db_alias = db_alias

        from .plugins.atomic import AtomicPlugin
        self.atomic = AtomicPlugin(db_alias) if db_alias else None
        self.errors_map = errors_map or {}

    def handle_error(self, e: Exception):
        for errors, target in self.errors_map.items():
            if isinstance(e, errors):
                raise target(e) from e
        raise e.__class__(str(e)) from e

    def __enter__(self):
        if self.atomic:
            return self.atomic.__enter__()
        return self

    async def __aenter__(self):
        if self.atomic:
            return await self.atomic.__aenter__()
        return self

    # def __await__(self):
    #     if self.atomic:
    #         return self.atomic.__await__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.atomic:
            try:
                return self.atomic.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                # try:
                #     if not exc_type:
                #         return self.atomic.__exit__(e.__class__, e, e.__traceback__)
                # finally:
                self.handle_error(e)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.atomic:
            try:
                return await self.atomic.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                # try:
                #     if not exc_type:
                #         # SQLite error will be raised on COMMIT statement inside transaction
                #         # so when the COMMIT failed (in the __exit__ block)
                #         # we should rollback with exceptions passed in
                #         return await self.atomic.__aexit__(e.__class__, e, e.__traceback__)
                # finally:
                self.handle_error(e)

    # def rollback(self):
    #     if self.atomic:
    #         return self.atomic.rollback()
    #
    # def commit(self):
    #     if self.atomic:
    #         return self.atomic.commit()


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

    def get_integrity_error(self, e: Exception) -> Exception:
        if self.context.integrity_error_cls:
            return self.context.integrity_error_cls(e)
        return e

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
            force_raise_error=force_raise_error or self.context.force_raise_error,
            integrity_error_cls=self.context.integrity_error_cls,
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

    def process_data(self, data: dict, with_relations: bool = False) -> Tuple[dict, dict, dict]:
        if not isinstance(data, dict):
            return {}, {}, {}
        if not isinstance(data, self.parser.obj):
            data = self.parser(data)

        result = {}
        relation_keys = {}
        relation_objs = {}

        for key, val in data.items():
            field = self.parser.get_field(key)
            if not isinstance(field, ParserQueryField):
                continue
            if not field.writable and not field.primary_key:
                # RELATIONS FIELD HERE
                if with_relations:
                    if field.relation_update_enabled:
                        if field.related_schema:
                            relation_objs[key] = (field, val)
                        else:
                            name = field.model_field.name
                            if not name:
                                continue
                            relation_keys[name] = (field, val)
                continue
            name = field.model_field.column_name
            # fk will be fk_id in this case
            if not isinstance(name, str):
                continue
            value = self.process_value(field, val)
            if not unprovided(value):
                result[name] = value

        return result, relation_keys, relation_objs

    def process_value(self, field: ParserQueryField, value):
        return value

    def commit_data(self, data):
        raise NotImplementedError

    @awaitable(commit_data)
    async def commit_data(self, data):
        raise NotImplementedError

    def save_data(self,
                  data,
                  must_create: bool = False,
                  must_update: bool = False,
                  ignore_bulk_errors: bool = False,
                  ignore_relation_errors: bool = False,
                  with_relations: bool = None,
                  transaction: bool = False,
                  ):
        raise NotImplementedError

    @awaitable(save_data)
    async def save_data(self,
                        data,
                        must_create: bool = False,
                        must_update: bool = False,
                        ignore_bulk_errors: bool = False,
                        ignore_relation_errors: bool = False,
                        with_relations: bool = None,
                        transaction: bool = False,
                        ):
        raise NotImplementedError

    def get_integrity_errors(self, asynchronous: bool = False) -> Tuple[Type[Exception], ...]:
        return ()

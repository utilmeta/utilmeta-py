import warnings

import utype
from utype import Field
from utype.parser.field import ParserField
from utype.parser.cls import ClassParser
from utype.parser.rule import LogicalType
from utype.types import *
from utilmeta.utils import class_func

if TYPE_CHECKING:
    from ..backends.base import ModelAdaptor
    from ..schema import Schema


class ParserQueryField(ParserField):
    def __init__(
        self,
        model: 'ModelAdaptor' = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._kwargs = kwargs
        from ..backends.base import ModelAdaptor, ModelFieldAdaptor

        self.model = model
        self.model_field: Optional[ModelFieldAdaptor] = None
        self.related_model: Optional[ModelAdaptor] = None
        self.related_schema: Optional[Type['Schema']] = None
        self.related_single = None
        self.isolated = self.field.isolated if isinstance(self.field, QueryField) else False
        self.fail_silently = self.field.fail_silently if isinstance(self.field, QueryField) else False
        self.many_included = False
        self.queryset = None
        self.primary_key = False
        self.func = None
        self.func_multi = False

    def reconstruct(self, model: 'ModelAdaptor'):
        return self.__class__(model, **self._kwargs)

    def get_query_schema(self):
        parser = None
        schema = None

        from ..schema import Schema
        from ..parser import SchemaClassParser

        if isinstance(self.type, type) and issubclass(self.type, Rule):
            # try to find List[schema]
            if isinstance(self.type.__origin__, LogicalType) and self.type.__origin__.combinator:
                for arg in self.type.__origin__.args:
                    cls_parser = ClassParser.resolve_parser(arg)
                    if cls_parser:
                        # for optional
                        parser = cls_parser
                        schema = arg
                        self.related_single = True
                        break
            else:
                if self.type.__origin__ and issubclass(self.type.__origin__, list) and self.type.__args__:
                    # we only accept list, not tuple/set
                    arg = self.type.__args__[0]
                    cls_parser = ClassParser.resolve_parser(arg)
                    if cls_parser:
                        parser = cls_parser
                        schema = arg
                        self.related_single = False
        else:
            # try to find Optional[schema]
            for origin in self.input_origins:
                cls_parser = ClassParser.resolve_parser(origin)
                if cls_parser:
                    parser = cls_parser
                    self.related_single = True
                    break

        if parser:
            if isinstance(parser, SchemaClassParser):
                if parser.model:
                    if self.model_field and self.related_model:
                        # if parser.model and self.model_field:
                        # check model if not queryset
                        if self.related_model.is_sub_model(parser.model) \
                                or parser.model.is_sub_model(self.related_model):
                            schema = schema or parser.obj
                        else:
                            raise TypeError(f'orm.Field({repr(self.name)}): '
                                            f'Invalid related model: {self.related_model.model},'
                                            f' sub model of {parser.model.model} expected')
                    else:
                        schema = schema or parser.obj
                        # 1. func field
                        # 2. common field (or array field) with not constraint relation

            if not schema:
                if not self.related_model:
                    # treat as a common field (like JSONField)
                    # with inner schema
                    return
                    # raise TypeError(f'orm.Field({repr(self.name)})) no model '
                    #                 f'specified for related schema: {parser.obj}')

                class schema(parser.obj, Schema[self.related_model]): pass
            else:
                if not issubclass(schema, Schema):
                    # common schema, not related schema
                    return

            self.related_schema = schema
            self.isolated = True

    @classmethod
    def process_annotate_meta(cls, m, model: 'ModelAdaptor' = None, **kwargs):
        from ..backends.base import ModelAdaptor
        if isinstance(model, ModelAdaptor):
            if model.field_adaptor_cls.qualify(m) or \
                    model.check_related_queryset(m):
                return QueryField(m)
        return super().process_annotate_meta(m, **kwargs)

    @classmethod
    def get_field(cls, annotation: Any, default, model: 'ModelAdaptor' = None, **kwargs):
        from ..backends.base import ModelAdaptor
        if isinstance(model, ModelAdaptor):
            if model.field_adaptor_cls.qualify(default) or \
                    model.check_related_queryset(default):
                return QueryField(default)
        return super().get_field(annotation, default, **kwargs)

    def setup(self, options: utype.Options):
        super().setup(options)

        from ..backends.base import ModelAdaptor
        if not isinstance(self.model, ModelAdaptor):
            return

        self.get_query_schema()

        if class_func(self.field_name):
            from utype.parser.func import FunctionParser
            func = FunctionParser.apply_for(self.field_name)
            # fixme: ugly approach, getting the awaitable async function
            async_func = getattr(func.obj, '_asyncfunc', None)
            sync_func = getattr(func.obj, '_syncfunc', None)
            if async_func and sync_func:
                from utilmeta.utils import awaitable
                if isinstance(self.field_name, classmethod):
                    sync_func = classmethod(sync_func)
                    async_func = classmethod(async_func)
                sync_wrapper = FunctionParser.apply_for(sync_func).wrap(
                    ignore_methods=True,
                    parse_params=True,
                    parse_result=True
                )
                async_wrapper = FunctionParser.apply_for(async_func).wrap(
                    ignore_methods=True,
                    parse_params=True,
                    parse_result=True
                )
                self.func = awaitable(sync_wrapper)(async_wrapper)
            else:
                self.func = func.wrap(
                    ignore_methods=True,
                    parse_params=True,
                    parse_result=True
                )
            self.func_multi = bool(func.pos_var)

            if not self.mode:
                self.mode = 'r'
            return

        if self.model.check_related_queryset(self.field_name):
            self.queryset = self.field_name
            if not self.mode:
                self.mode = 'r'
            self.related_model = self.model.get_model(self.queryset)
            if not self.related_model:
                raise ValueError(f'No model detected in queryset: {self.queryset}')
            if self.related_single is False:
                warnings.warn(f'{self.model} schema field: {repr(self.name)} is a multi-relation with a subquery, '
                              f'you need to make sure that only 1 row of the query is returned, '
                              f'otherwise use query function instead')
            self.isolated = True
            # force isolated for queryset query (even without schema)
            return

        self.model_field = self.model.get_field(self.field_name, allow_addon=True, silently=True)
        if self.model_field:
            self.primary_key = self.model_field and self.model_field.is_pk \
                               and self.model.is_sub_model(self.model_field.field_model)
            # use is sub model, because pk might be its base model

            if self.primary_key and self.model_field.is_auto:
                self.required = False

            if not self.model_field.is_writable or self.model.cross_models(self.field_name):
                # read only
                if not self.mode and not self.primary_key:
                    self.mode = 'r'
                    # do not set primary key field to mode='r'
                    # otherwise pk will not be settable in other mode
            else:
                if self.model_field.is_auto and not self.primary_key:
                    # like auto_now
                    if not self.mode:
                        self.mode = 'rw'
                    if not self.no_input:
                        self.no_input = 'w'

            # this is too far...
            # maybe user wants to assign after initialization
            # if not self.model_field.is_optional:
            #     if not self.required:
            #         # required when creating
            #         self.required = 'a'

            self.related_model = self.model_field.related_model

            self.many_included = self.model.include_many_relates(self.field_name)
            if self.many_included:
                # 1. many included fields will be force isolated
                # if not self.model_field.is_exp:
                # expression need to be isolated, otherwise multiple many included query will blow the query
                self.isolated = True

            elif not self.model_field.is_concrete:
                self.isolated = True

            if self.related_schema:
                # even for fk schema
                # is not writable by default
                # if self.related_model or self.many_included:
                if not self.mode:
                    self.mode = 'r'
                # else:
                #     self.isolated = False
                # 1. for a common field (say, JSONField) with related schema, we does not say mode to 'r'
                # 2. for serializing array field (pk_values) using related schema, isolated should be True
            else:
                # if user has provided a related schema
                # we do no need to merge the field rule
                rule = self.model_field.rule
                self.type = rule.merge_type(self.type)
                # merge declared type and model field type

        else:
            if isinstance(self.field, QueryField) and self.field.field:
                raise ValueError(f'orm.Field({repr(self.field.field)}) not exists in model: {self.model}')
            # will not be queried (input of 'r' mode)
            if not self.no_input:
                self.no_input = 'r'
            if not self.mode:
                self.mode = 'r'

    @property
    def readable(self):
        if self.func:
            return True
        if self.queryset is not None:
            return True
        if not self.model_field:
            return False
        return not self.always_no_input(utype.Options(mode='r'))

    @property
    def writable(self):
        if not self.model_field:
            return False
        return self.model_field.is_writable

    @property
    def included(self):
        if not self.model_field:
            return False
        if not self.isolated:
            return True
        # relate schema does not matter here
        if not self.model_field.is_concrete:
            # fixme: async backend may not fetch pk along with one-to-rel
            return False
        return not self.many_included and bool(self.related_schema)

    @property
    def expression(self):
        if self.model_field and self.model_field.is_exp:
            return self.model_field.field
        return None

    @property
    def field_name(self):
        if isinstance(self.field, QueryField):
            # do not use [or] / [bool] to validate such field
            # because that might be a queryset
            if self.field.field is None:
                return self.attname
            return self.field.field
        return self.attname

    @property
    def schema_annotations(self):
        data = dict(self.field.schema_annotations or {})
        if self.model_field:
            data.update(field=self.model_field.query_name)
        if self.related_model:
            data.update(related_model=self.related_model.ident)
        return data


class QueryField(Field):
    parser_field_cls = ParserQueryField

    def __init__(self, field=None, *,
                 fail_silently: bool = None,
                 auth: dict = None,
                 # filter=None,
                 # order_by: Union[str, List[str], Callable] = None,
                 # limit: Union[int, Callable] = None,
                 # distinct: bool = None,
                 isolated: bool = None,
                 **kwargs
                 # if module enabled result control (page / rows / limit / offset) and such params is provided
                 # this config is automatically turn to True to prevent result control the entire queryset
                 ):
        super().__init__(**kwargs)
        self.field = field
        self.fail_silently = fail_silently
        self.isolated = isolated
        # self.filter = filter
        # self.order_by = order_by
        # self.limit = limit
        # self.distinct = distinct
        self.auth = auth

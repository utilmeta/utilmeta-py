import utype
from typing import TypeVar

from utype.parser.field import ParserField

from utilmeta.core import request as req
from .parser import SchemaClassParser, QueryClassParser
from utilmeta.core.orm import exceptions
from utilmeta.utils.exceptions import BadRequest
from .context import QueryContext
from .fields.field import ParserQueryField
from utype.types import ForwardRef, Type, List, Union, Callable


T = TypeVar("T")

__caches__: dict = {}


class Schema(utype.Schema):
    __serialize_options__ = utype.Options(
        mode="r",
        addition=True,
        ignore_required=True,
        ignore_constraints=True  # skip constraints validation when querying from db
        # no_default=True,
        # no default, but default can be calculated when attr is called
    )
    __integrity_error_cls__ = BadRequest
    __attribute_error_cls__ = BadRequest
    __parser_cls__ = SchemaClassParser
    __parser__: SchemaClassParser
    __field__ = req.Body
    __model__ = None

    def __class_getitem__(cls: T, item) -> T:
        k = (cls, item)
        if k in __caches__:
            return __caches__[k]
        attrs = {"__qualname__": cls.__qualname__, "__module__": cls.__module__}

        options = None
        annotations = {}
        if isinstance(item, str):
            options = utype.Options(mode=item)
            attrs.update(__options__=options)
        elif isinstance(item, utype.Options):
            options = item
            attrs.update(__options__=item)
        else:
            attrs.update(__model__=item)

        if options:
            fields: dict = cls.__parser__.fields
            for name in fields:
                field = fields[name]
                if isinstance(field, ParserQueryField):
                    if field.override_required(options):
                        attrs[field.attname] = field.field
                        annotations[field.attname] = field.type
        if annotations:
            attrs.update(__annotations__=annotations)

        new_cls = utype.LogicalMeta(cls.__parser__.name, (cls,), attrs)

        __caches__[k] = new_cls
        return new_cls

    def __field_getter__(self, field: ParserField, getter: Callable = None):
        try:
            return super().__field_getter__(field, getter)
        except AttributeError as e:
            if self.__attribute_error_cls__:
                raise self.__attribute_error_cls__(str(e)) from e
            raise

    @property
    @utype.Field(no_output=True)
    def pk(self):
        return self.__parser__.get_pk(self)

    @pk.setter
    @utype.Field(no_input=True)
    def pk(self, val):
        _set = False
        for name in self.__parser__.pk_names:
            self[name] = val
            # if field is in other mode or use no_input settings
            # we should make a fallback
            if name in self:
                _set = True
        if not _set:
            self.__dict__["pk"] = val

    def get_instance(self, fresh: bool = True, using: str = None):
        if fresh:
            if self.pk is None:
                raise exceptions.MissingPrimaryKey("pk is missing for query instance")
            return self.__parser__.model.query(using=using, pk=self.pk).get_instance()
        return self.__parser__.get_instance(self)

    async def aget_instance(self, fresh: bool = True, using: str = None):
        if fresh:
            if self.pk is None:
                raise exceptions.MissingPrimaryKey("pk is missing for query instance")
            return await self.__parser__.model.query(
                using=using, pk=self.pk
            ).aget_instance()
        return self.__parser__.get_instance(self)

    @classmethod
    def _get_compiler(
        cls, queryset, context=None, single: bool = False, using: str = None
    ):
        if isinstance(queryset, Query):
            generator = queryset.__parser__.get_generator(queryset, using=using)
            qs = generator.get_queryset()
            # get context after queryset generation
            context = generator.get_context(single=single).merge(context)
        else:
            qs = queryset
            context = context or QueryContext(using=using)
        if cls.__integrity_error_cls__:
            context.integrity_error_cls = cls.__integrity_error_cls__
        return cls.__parser__.get_compiler(qs, context=context)

    @classmethod
    def _get_relational_update_cls(cls, field: str, mode: Union[str, utype.Options]):
        # class RoleSchema(orm.Schema[Member]):
        #     id: int
        #     member_id: int
        #     name: str
        #     description: str
        #
        # class MemberSchema(orm.Schema[Member]):
        #     id: int
        #     project_id: int
        #     user: UserSchema
        #     created_time: datetime
        #     roles: List[RoleSchema] = orm.Field(mode='rwa') ---- field: member_id
        #
        # class ProjectSchema(orm.Schema[Project]):
        #     id: int
        #     name: str
        #     owner: UserSchema
        #     owner_id: int = orm.Field(no_input='aw')
        #     members: List[MemberSchema] = orm.Field(mode='rwa') ---- field: project_id

        options = mode if isinstance(mode, utype.Options) else utype.Options(mode=mode)
        mode = mode.mode if isinstance(mode, utype.Options) else str(mode)
        origin_cls = getattr(cls, '__origin_cls__', cls)

        k = (origin_cls, str(options), field)

        if k in __caches__:
            return __caches__[k]

        suffix = f"_RELATIONAL_UPDATE_{field}"
        attrs = {
            "__qualname__": cls.__qualname__ + suffix,
            "__module__": cls.__module__,
            "__options__": options
        }

        model_field = cls.__parser__.model.get_field(field)
        if not model_field:
            raise ValueError(
                f"Invalid relation remote_field: {repr(field)}, not exists"
            )
        if not model_field.is_fk:
            raise ValueError(
                f"Invalid relation remote_field: {repr(field)}, must be ForeignKey"
            )

        relational_fields = []
        annotations = {}

        for name, parser_field in cls.__parser__.fields.items():
            if isinstance(parser_field, ParserQueryField):
                if (
                    parser_field.model_field
                    and parser_field.model_field.name == model_field.name
                ):
                    if name == "pk":
                        continue
                    attrs[parser_field.attname] = parser_field.field_cls(
                        no_input=mode,
                        mode=mode,
                        alias=name if name != parser_field.attname else None,
                        alias_from=parser_field.field.alias_from
                    )
                    if not parser_field.no_output:
                        relational_fields.append(parser_field.attname)

                elif parser_field.relation_setup_required(options):
                    # just copy the base field to trigger the relational setup
                    attrs[parser_field.attname] = parser_field.field

                    if not hasattr(cls.__parser__, 'annotations'):
                        # compat utype < 0.6.5
                        # will be deprecated in the future
                        annotations[parser_field.attname] = cls.__annotations__.get(
                            parser_field.attname, parser_field.type)

        if not relational_fields:
            attrs[field] = cls.__parser_cls__.parser_field_cls.field_cls(
                no_input=mode, mode=mode, no_output=False
            )
            relational_fields = [field]

        attrs.update(
            __relational_fields__=relational_fields,
            __origin_cls__=origin_cls
        )
        if annotations:
            attrs.update(__annotations__=annotations)

        name = cls.__parser__.name + suffix
        forward = ForwardRef(name)
        # do not name as cls.__qualname__
        __caches__.setdefault(k, forward)
        # avoid infinite recursive generate like typing.Self
        new_cls = utype.LogicalMeta(name, (cls,), attrs)
        forward.__forward_evaluated__ = True
        forward.__forward_value__ = new_cls
        __caches__[k] = new_cls

        parser: SchemaClassParser = getattr(new_cls, '__parser__')
        # parser.resolve_forward_refs(ignore_errors=False)
        for name, parser_field in parser.fields.items():
            if isinstance(parser_field, ParserQueryField):
                if isinstance(parser_field.related_schema, ForwardRef):
                    # resolve forward refs
                    parser_field.resolve_forward_refs()

        return new_cls

    @classmethod
    def serialize(cls: Type[T], queryset, context=None) -> List[T]:
        # todo: add auto_distinct
        cls: Type[Schema]
        values = []
        compiler = cls._get_compiler(queryset, context=context)
        for val in compiler.get_values():
            values.append(cls.__from__(val, compiler.serialize_options))
        return values

    @classmethod
    async def aserialize(cls: Type[T], queryset, context=None) -> List[T]:
        cls: Type[Schema]
        values = []
        compiler = cls._get_compiler(queryset, context=context)
        for val in await compiler.get_values():
            values.append(cls.__from__(val, compiler.serialize_options))
        return values

    @classmethod
    def init(cls: Type[T], queryset, context=None) -> T:
        # initialize this schema with the given queryset (first element)
        # raise error if queryset is empty
        cls: Type[Schema]
        compiler = cls._get_compiler(queryset, context=context, single=True)
        values = compiler.get_values()
        if not values:
            raise exceptions.EmptyQueryset(f"Empty queryset")
        return cls.__from__(values[0], compiler.serialize_options)

    @classmethod
    # @awaitable(init)
    async def ainit(cls: Type[T], queryset, context=None) -> T:
        # initialize this schema with the given queryset (first element)
        # raise error if queryset is empty
        cls: Type[Schema]
        compiler = cls._get_compiler(queryset, context=context, single=True)
        values = await compiler.get_values()
        if not values:
            raise exceptions.EmptyQueryset(f"Empty queryset")
        return cls.__from__(values[0], compiler.serialize_options)

    def commit(self, queryset: T) -> T:  # -> queryset
        # commit the data in the schema to the queryset (update)
        # id is ignored here
        compiler = self._get_compiler(queryset)
        return compiler.commit_data(self)

    # @awaitable(commit)
    async def acommit(self, queryset: T) -> T:  # -> queryset
        # commit the data in the schema to the queryset (update)
        # id is ignored here
        compiler = self._get_compiler(queryset)
        return await compiler.commit_data(self)

    def save(
        self: T,
        must_create: bool = None,
        must_update: bool = None,
        with_relations: bool = None,
        ignore_relation_errors: Union[
            bool, Type[Exception], List[Type[Exception]]
        ] = False,
        transaction: Union[bool, str] = False,
        using: str = None,
    ) -> T:  # -> queryset
        # no id: create
        # id: create -(integrityError)-> update
        if must_update and must_create:
            raise ValueError(
                f"{__class__.__name__}.save(): must_create and must_update cannot both be True"
            )
        if must_create is None:
            if must_update:
                must_create = False
            elif self.__options__.mode == "a" and not self.pk:
                must_create = True
        # if with_relations is None:
        #     with_relations = True
        # if must_update is None:
        #     if self.__options__.mode == 'w':
        #         must_update = True
        self: Schema
        compiler = self._get_compiler(None, using=using)
        self.pk = compiler.save_data(
            self,
            must_create=must_create,
            must_update=must_update,
            with_relations=with_relations,
            ignore_relation_errors=ignore_relation_errors,
            transaction=transaction,
        )
        return self

    # @awaitable(save)
    async def asave(
        self: T,
        must_create: bool = None,
        must_update: bool = None,
        with_relations: bool = None,
        ignore_relation_errors: Union[
            bool, Type[Exception], List[Type[Exception]]
        ] = False,
        transaction: Union[bool, str] = False,
        using: str = None,
    ) -> T:  # -> queryset
        # no id: create
        # id: create -(integrityError)-> update
        if must_update and must_create:
            raise ValueError(
                f"{__class__.__name__}.asave(): must_create and must_update cannot both be True"
            )
        if must_create is None:
            if must_update:
                must_create = False
            elif self.__options__.mode == "a" and not self.pk:
                must_create = True
        # if with_relations is None:
        #     with_relations = True
        # if must_update is None:
        #     if self.__options__.mode == 'w':
        #         must_update = True
        self: Schema
        compiler = self._get_compiler(None, using=using)
        self.pk = await compiler.save_data(
            self,
            must_create=must_create,
            must_update=must_update,
            with_relations=with_relations,
            ignore_relation_errors=ignore_relation_errors,
            transaction=transaction,
        )
        return self

    @classmethod
    def bulk_save(
        cls: Type[T],
        data: List[T],
        must_create: bool = False,
        must_update: bool = False,
        with_relations: bool = None,
        ignore_errors: Union[bool, Type[Exception], List[Type[Exception]]] = False,
        ignore_relation_errors: Union[
            bool, Type[Exception], List[Type[Exception]]
        ] = False,
        transaction: Union[bool, str] = False,
        using: str = None,
    ) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls._get_compiler(None, using=using)
        if not isinstance(data, list):
            raise TypeError(f"Invalid data: {data}, must be list")
        # 1. transform data list to schema instance list
        values = [val if isinstance(val, cls) else cls.__from__(val) for val in data]
        # 2. bulk create
        for pk, val in zip(
            compiler.save_data(
                values,
                must_update=must_update,
                must_create=must_create,
                with_relations=with_relations,
                ignore_bulk_errors=ignore_errors,
                ignore_relation_errors=ignore_relation_errors,
                transaction=transaction,
            ),
            values,
        ):
            if pk:
                val.pk = pk
        return values

    @classmethod
    async def abulk_save(
        cls: Type[T],
        data: List[T],
        must_create: bool = False,
        must_update: bool = False,
        with_relations: bool = None,
        ignore_errors: Union[bool, Type[Exception], List[Type[Exception]]] = False,
        ignore_relation_errors: Union[
            bool, Type[Exception], List[Type[Exception]]
        ] = False,
        transaction: Union[bool, str] = False,
        using: str = None,
    ) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls._get_compiler(None, using=using)
        if not isinstance(data, list):
            raise TypeError(f"Invalid data: {data}, must be list")
        # 1. transform data list to schema instance list
        values = [val if isinstance(val, cls) else cls.__from__(val) for val in data]
        for pk, val in zip(
            await compiler.save_data(
                values,
                must_update=must_update,
                must_create=must_create,
                with_relations=with_relations,
                ignore_bulk_errors=ignore_errors,
                ignore_relation_errors=ignore_relation_errors,
                transaction=transaction,
            ),
            values,
        ):
            if pk:
                val.pk = pk
        return values


class Query(utype.Schema):
    __parser_cls__ = QueryClassParser
    __parser__: QueryClassParser
    __field__ = req.Query
    __model__ = None
    __distinct__ = None

    # ----
    # consider this schema instance might be setattr/delattr after initialization
    # so generated queryset in __post_init__ is not a good way

    def __class_getitem__(cls, item):
        class _class(cls):
            __model__ = item

        return _class

    def get_generator(self, using: str = None):
        return self.__parser__.get_generator(
            self, using=using, distinct=self.__distinct__
        )

    def get_queryset(self, base=None, using: str = None):
        if not self.__parser__.model:
            raise NotImplementedError
        return self.get_generator(using=using).get_queryset(base)

    def count(self, base=None, using: str = None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return self.get_generator(using=using).count(base)

    async def acount(self, base=None, using: str = None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return await self.get_generator(using=using).acount(base)

    def get_context(self, using: str = None):
        return self.get_generator(using=using).get_context()

    def __call__(self, base=None, using: str = None):
        return self.get_queryset(base, using=using)

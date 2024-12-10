import utype
from typing import TypeVar, Type, List, Union
from utilmeta.core import request as req
from .parser import SchemaClassParser, QueryClassParser
from utilmeta.core.orm import exceptions
from utilmeta.utils.exceptions import BadRequest
from utilmeta.conf import Preference
from .context import QueryContext
from .fields.field import ParserQueryField


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
    __parser_cls__ = SchemaClassParser
    __parser__: SchemaClassParser
    __field__ = req.Body
    __model__ = None

    def __class_getitem__(cls: T, item) -> T:
        global __caches__
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

    def get_instance(self, fresh: bool = True):
        if fresh:
            if self.pk is None:
                raise exceptions.MissingPrimaryKey("pk is missing for query instance")
            return self.__parser__.model.get_instance(pk=self.pk)
        return self.__parser__.get_instance(self)

    async def aget_instance(self, fresh: bool = True):
        if fresh:
            if self.pk is None:
                raise exceptions.MissingPrimaryKey("pk is missing for query instance")
            return await self.__parser__.model.aget_instance(pk=self.pk)
        return self.__parser__.get_instance(self)

    @classmethod
    def _get_compiler(cls, queryset, context=None, single: bool = False):
        if isinstance(queryset, Query):
            generator = queryset.__parser__.get_generator(queryset)
            qs = generator.get_queryset()
            # get context after queryset generation
            context = context or generator.get_context(single=single)
        else:
            qs = queryset
            context = context or QueryContext()
        if cls.__integrity_error_cls__:
            context.integrity_error_cls = cls.__integrity_error_cls__
        return cls.__parser__.get_compiler(qs, context=context)

    @classmethod
    def _get_relational_update_cls(cls, field: str, mode: str):
        # class MemberSchema(orm.Schema[Member]):
        #     id: int
        #     project_id: int
        #     user: UserSchema
        #     roles: list
        #     created_time: datetime
        #
        # class ProjectSchema(orm.Schema[Project]):
        #     id: int
        #     name: str
        #     owner: UserSchema
        #     owner_id: int = orm.Field(no_input='aw')
        #     members: List[MemberSchema] = orm.Field(mode='rwa') ---- field: project_id

        global __caches__
        k = (cls, mode, field)
        if k in __caches__:
            return __caches__[k]

        suffix = f"_RELATIONAL_UPDATE_{field}"
        attrs = {
            "__qualname__": cls.__qualname__ + suffix,
            "__module__": cls.__module__,
        }
        if isinstance(mode, str):
            attrs.update(__options__=utype.Options(mode=mode))
        elif isinstance(mode, utype.Options):
            attrs.update(__options__=mode)

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
        for name, parser_field in cls.__parser__.fields.items():
            parser_field: SchemaClassParser.parser_field_cls
            if (
                parser_field.model_field
                and parser_field.model_field.name == model_field.name
            ):
                if name == "pk":
                    continue
                attrs[parser_field.attname] = parser_field.field_cls(
                    no_input=mode, mode=mode
                )
                if not parser_field.no_output:
                    relational_fields.append(parser_field.attname)
        if not relational_fields:
            attrs[field] = cls.__parser_cls__.parser_field_cls.field_cls(
                no_input=mode, mode=mode, no_output=False
            )
            relational_fields = [field]

        attrs.update(
            __relational_fields__=relational_fields,
            # __relational_field__=field
        )
        new_cls = utype.LogicalMeta(cls.__parser__.name + suffix, (cls,), attrs)
        __caches__[k] = new_cls
        return new_cls

    @classmethod
    def serialize(cls: Type[T], queryset, context=None) -> List[T]:
        # todo: add auto_distinct
        cls: Type[Schema]
        values = []
        for val in cls._get_compiler(queryset, context=context).get_values():
            values.append(cls.__from__(val, cls.__serialize_options__))
        return values

    @classmethod
    async def aserialize(cls: Type[T], queryset, context=None) -> List[T]:
        cls: Type[Schema]
        values = []
        for val in await cls._get_compiler(queryset, context=context).get_values():
            values.append(cls.__from__(val, cls.__serialize_options__))
        return values

    @classmethod
    def init(cls: Type[T], queryset, context=None) -> T:
        # initialize this schema with the given queryset (first element)
        # raise error if queryset is empty
        cls: Type[Schema]
        values = cls._get_compiler(queryset, context=context, single=True).get_values()
        if not values:
            raise exceptions.EmptyQueryset(f"Empty queryset")
        return cls.__from__(values[0], cls.__serialize_options__)

    @classmethod
    # @awaitable(init)
    async def ainit(cls: Type[T], queryset, context=None) -> T:
        # initialize this schema with the given queryset (first element)
        # raise error if queryset is empty
        cls: Type[Schema]
        values = await cls._get_compiler(
            queryset, context=context, single=True
        ).get_values()
        if not values:
            raise exceptions.EmptyQueryset(f"Empty queryset")
        return cls.__from__(values[0], cls.__serialize_options__)

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
        compiler = self._get_compiler(None)
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
        compiler = self._get_compiler(None)
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
    ) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls._get_compiler(None)
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
    ) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls._get_compiler(None)
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

    def get_generator(self):
        return self.__parser__.get_generator(self, distinct=self.__distinct__)

    def get_queryset(self, base=None):
        if not self.__parser__.model:
            raise NotImplementedError
        return self.get_generator().get_queryset(base)

    def count(self, base=None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return self.get_generator().count(base)

    async def acount(self, base=None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return await self.get_generator().acount(base)

    def get_context(self):
        return self.get_generator().get_context()

    def __call__(self, base=None):
        return self.get_queryset(base)

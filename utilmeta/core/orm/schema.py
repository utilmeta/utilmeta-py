import utype
from typing import TypeVar, Type, List
from utilmeta.core import request as req
from .parser import SchemaClassParser, QueryClassParser
# from .generator import BaseQuerysetGenerator
# from .backends.base import ModelAdaptor
from . import exceptions

T = TypeVar('T')

# class ModLogicalMeta(utype.LogicalMeta):
#     def __mod__(cls: T, other) -> T:
#         if isinstance(other, str):
#             other = utype.Options(mode=other)
#         elif not isinstance(other, utype.Options):
#             raise exceptions.InvalidMode(f'Invalid % for orm {cls}:
#             {other}, must be a mod string or Options instance')
#
#         class _cls(cls):
#             __name__ = cls.__name__
#             __qualname__ = cls.__qualname__
#             __module__ = cls.__module__
#             __options__ = other
#
#         # _cls.__name__ = cls.__name__
#         # _cls.__module__ = cls.__module__
#         return _cls

__caches__: dict = {}


class Schema(utype.Schema):
    __serialize_options__ = utype.Options(
        mode='r',
        addition=True,
        ignore_required=True,
        # no_default=True,
        # no default, but default can be calculated when attr is called
    )
    __parser_cls__ = SchemaClassParser
    __parser__: SchemaClassParser
    __field__ = req.Json
    __model__ = None

    def __class_getitem__(cls: T, item) -> T:
        attrs = {
            '__qualname__': cls.__qualname__,
            '__module__': cls.__module__
        }
        global __caches__
        k = (cls, item)
        if k in __caches__:
            return __caches__[k]
        if isinstance(item, str):
            attrs.update(__options__=utype.Options(mode=item))
        elif isinstance(item, utype.Options):
            attrs.update(__options__=item)
        else:
            attrs.update(__model__=item)
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
            self.__dict__['pk'] = val

    def get_instance(self):
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
        return cls.__parser__.get_compiler(qs, context=context)

    @classmethod
    def serialize(cls: Type[T], queryset, context=None) -> List[T]:
        cls: Type[Schema]
        values = []
        for val in cls._get_compiler(queryset, context=context).get_values():
            values.append(cls.__from__(val, cls.__serialize_options__))
        return values

    @classmethod
    # @awaitable(serialize)
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
            raise exceptions.EmptyQueryset(f'Empty queryset')
        return cls.__from__(values[0], cls.__serialize_options__)

    @classmethod
    # @awaitable(init)
    async def ainit(cls: Type[T], queryset, context=None) -> T:
        # initialize this schema with the given queryset (first element)
        # raise error if queryset is empty
        cls: Type[Schema]
        values = await cls._get_compiler(queryset, context=context, single=True).get_values()
        if not values:
            raise exceptions.EmptyQueryset(f'Empty queryset')
        return cls.__from__(values[0], cls.__serialize_options__)

    # def __init__(self, queryset=None, **kwargs):
    #     if queryset is not None:
    #         super().__init__(self.init(queryset))
    #     else:
    #         super().__init__(**kwargs)

    def commit(self, queryset: T) -> T:   # -> queryset
        # commit the data in the schema to the queryset (update)
        # id is ignored here
        compiler = self.__parser__.get_compiler(queryset)
        return compiler.commit_data(self)

    # @awaitable(commit)
    async def acommit(self, queryset: T) -> T:     # -> queryset
        # commit the data in the schema to the queryset (update)
        # id is ignored here
        compiler = self.__parser__.get_compiler(queryset)
        return await compiler.commit_data(self)

    def save(self: T, must_create: bool = False, must_update: bool = False) -> T:  # -> queryset
        # no id: create
        # id: create -(integrityError)-> update
        self: Schema
        compiler = self.__parser__.get_compiler(None)
        self.pk = compiler.save_data(
            self,
            must_create=must_create,
            must_update=must_update
        )
        return self

    # @awaitable(save)
    async def asave(self: T, must_create: bool = False, must_update: bool = False) -> T:    # -> queryset
        # no id: create
        # id: create -(integrityError)-> update
        self: Schema
        compiler = self.__parser__.get_compiler(None)
        self.pk = await compiler.save_data(
            self,
            must_create=must_create,
            must_update=must_update
        )
        return self

    @classmethod
    def bulk_save(cls: Type[T], data: List[T]) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls.__parser__.get_compiler(None)
        if not isinstance(data, list):
            raise TypeError(f'Invalid data: {data}, must be list')
        # 1. transform data list to schema instance list
        values = [val if isinstance(val, cls) else cls.__from__(val) for val in data]
        # 2. bulk create
        for pk, val in zip(compiler.save_data(values), values):
            val.pk = pk
        return values

    @classmethod
    async def abulk_save(cls: Type[T], data: List[T]) -> List[T]:
        # the queryset is contained in the data,
        # data with id will be updated (try, and create after not exists)
        # data without id will be created
        compiler = cls.__parser__.get_compiler(None)
        if not isinstance(data, list):
            raise TypeError(f'Invalid data: {data}, must be list')
        # 1. transform data list to schema instance list
        values = [val if isinstance(val, cls) else cls.__from__(val) for val in data]
        for pk, val in zip(await compiler.save_data(values), values):
            val.pk = pk
        return values


class Query(utype.Schema):
    __parser_cls__ = QueryClassParser
    __parser__: QueryClassParser
    __field__ = req.Query
    __model__ = None

    # ----
    # consider this schema instance might be setattr/delattr after initialization
    # so generated queryset in __post_init__ is not a good way

    def __class_getitem__(cls, item):
        class _class(cls):
            __model__ = item
        return _class

    def get_queryset(self, base=None):
        if not self.__parser__.model:
            raise NotImplementedError
        return self.__parser__.get_generator(self).get_queryset(base)

    def count(self, base=None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return self.__parser__.get_generator(self).count(base)

    async def acount(self, base=None) -> int:
        if not self.__parser__.model:
            raise NotImplementedError
        return await self.__parser__.get_generator(self).acount(base)

    def get_context(self):
        return self.__parser__.get_generator(self).get_context()

    def __call__(self, base=None):
        return self.get_queryset(base)

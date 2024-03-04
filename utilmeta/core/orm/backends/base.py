from utilmeta.utils import awaitable
from utilmeta.utils.adaptor import BaseAdaptor
from typing import Tuple, Optional, List, Callable, Type
from utype import Rule
from ..generator import BaseQuerysetGenerator
from ..compiler import BaseQueryCompiler


class ModelFieldAdaptor(BaseAdaptor):
    @classmethod
    def reconstruct(cls, adaptor: 'BaseAdaptor'):
        pass

    __backends_route__ = 'backends'
    model_adaptor_cls = None

    # hold a model field or expression
    def __init__(self, field, addon: str = None, model: 'ModelAdaptor' = None, lookup_name: str = None):
        self.field = field
        self.addon = addon
        self.lookup_name = lookup_name
        self._model = model

    @property
    def related_model(self) -> Optional['ModelAdaptor']:
        raise NotImplementedError

    @property
    def remote_field(self) -> Optional['ModelFieldAdaptor']:
        raise NotImplementedError

    # @property
    # def remote_is_pk(self) -> Optional['ModelFieldAdaptor']:
    #     return self.remote_field and self.remote_field.is_pk

    @property
    def reverse_lookup(self) -> Tuple[str, str]:
        return self.model.get_reverse_lookup(self.lookup_name)

    @property
    def target_field(self) -> Optional['ModelFieldAdaptor']:
        raise NotImplementedError

    @property
    def model(self):
        return self._model

    @property
    def field_model(self):
        raise NotImplementedError

    @property
    def rule(self) -> Type[Rule]:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def query_name(self) -> str:
        raise NotImplementedError

    def check_query(self):
        raise NotImplementedError

    @property
    def column_name(self) -> str:
        raise NotImplementedError

    @property
    def to_field(self) -> str:
        raise NotImplementedError

    @property
    def relate_name(self) -> str:
        raise NotImplementedError

    def get_supported_operators(self):
        pass

    @property
    def is_nullable(self):
        raise NotImplementedError

    @property
    def is_optional(self):
        raise NotImplementedError

    @property
    def is_auto(self):
        raise NotImplementedError

    @property
    def is_writable(self):
        raise NotImplementedError

    @property
    def is_unique(self):
        raise NotImplementedError

    @property
    def is_db_index(self):
        raise NotImplementedError

    @property
    def is_exp(self):
        raise NotImplementedError

    @property
    def is_pk(self):
        raise NotImplementedError

    @property
    def is_fk(self):
        raise NotImplementedError

    @property
    def is_concrete(self):
        raise NotImplementedError

    @property
    def is_m2m(self):
        raise NotImplementedError

    @property
    def is_m2(self):
        raise NotImplementedError

    @property
    def is_2m(self):
        raise NotImplementedError

    @property
    def is_o2(self):
        raise NotImplementedError

    @property
    def is_2o(self):
        raise NotImplementedError

    @property
    def is_many(self):
        return self.is_2m or self.is_m2

    @property
    def is_combined(self):
        raise NotImplementedError

    @classmethod
    def get_exp_field(cls, exp) -> Optional[str]:
        raise NotImplementedError

    @classmethod
    def iter_combined_expression(cls, exp):
        raise NotImplementedError


class ModelAdaptor(BaseAdaptor):
    field_adaptor_cls = ModelFieldAdaptor
    generator_cls = BaseQuerysetGenerator
    compiler_cls = BaseQueryCompiler
    model_cls = None
    queryset_cls = None

    __backends_names__ = ['django', 'peewee', 'sqlalchemy']

    @classmethod
    def reconstruct(cls, adaptor: 'BaseAdaptor'):
        pass

    def __init__(self, model):
        if not self.qualify(model):
            raise TypeError(f'{self.__class__}: Invalid model: {model}')
        self.model = model

    @property
    def ident(self):
        return f'{self.model.__module__}.{self.model.__name__}'

    @property
    def pk_field(self) -> field_adaptor_cls:
        raise NotImplementedError

    def update(self, data: dict, q=None, **filters):
        raise NotImplementedError

    @awaitable(update)
    async def update(self, data: dict, q=None, **filters):
        raise NotImplementedError

    def create(self, d=None, **data):
        raise NotImplementedError

    @awaitable(create)
    async def create(self, d=None, **data):
        raise NotImplementedError

    def delete(self, q=None, **filters):
        raise NotImplementedError

    async def adelete(self, q=None, **filters):
        raise NotImplementedError

    # def update_queryset(self, queryset, data: dict):
    #     raise NotImplementedError
    #
    # def serialize_queryset(self, queryset):
    #     raise NotImplementedError

    def get_queryset(self, q=None, **filters):
        # for django it's like model.objects.all()
        raise NotImplementedError

    def get_instance(self, q=None, **filters):
        raise NotImplementedError

    def init_instance(self, pk=None, **data):
        raise NotImplementedError

    # @awaitable(get_instance)
    async def aget_instance(self, q=None, **filters):
        raise NotImplementedError

    def check_related_queryset(self, qs):
        raise NotImplementedError

    def get_model(self, qs) -> 'ModelAdaptor':
        raise NotImplementedError

    @property
    def abstract(self) -> bool:
        """
        Do not corresponding to a concrete table
        """
        raise NotImplementedError

    @property
    def table_name(self) -> str:
        raise NotImplementedError

    def get_parents(self) -> list:
        raise NotImplementedError

    def cross_models(self, field):
        raise NotImplementedError

    def get_field(self, name: str, validator: Callable = None,
                  silently: bool = False,
                  allow_addon: bool = False) -> Optional[field_adaptor_cls]:
        """
        Get name from a field references
        """
        raise NotImplementedError

    def get_backward(self, field: str) -> str:
        raise NotImplementedError

    def get_reverse_lookup(self, lookup: str) -> Tuple[str, Optional[str]]:
        raise NotImplementedError

    def get_last_many_relates(self, lookup: str):
        raise NotImplementedError

    def get_fields(self, many=False, no_inherit=False) -> List[ModelFieldAdaptor]:
        raise NotImplementedError

    def get_related_adaptor(self, field):
        return self.__class__(field.related_model) if field.related_model else None

    def gen_lookup_keys(self, field: str, keys, strict: bool = True, excludes: List[str] = None) -> list:
        raise NotImplementedError

    def gen_lookup_filter(self, field, q, excludes: List[str] = None):
        raise NotImplementedError

    def include_many_relates(self, field: str):
        raise NotImplementedError

    def resolve_output_field(self, expr):
        raise NotImplementedError

    def check_expressions(self, expr):
        pass

    def check_query(self, q):
        pass

    def check_order(self, f):
        pass

    def is_sub_model(self, model):
        raise NotImplementedError

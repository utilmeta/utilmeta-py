from utilmeta.utils import multi
from ..base import ModelFieldAdaptor
from typing import Union, Optional, Type, TYPE_CHECKING
from django.db import models
from django.db.models.fields.reverse_related import ForeignObjectRel
from django.db.models.query_utils import DeferredAttribute
from django.core import exceptions
from . import constant
from . import expressions as exp
from utype import Rule, Lax
from utype import types
from functools import cached_property
import warnings

if TYPE_CHECKING:
    from .model import DjangoModelAdaptor


def one_to(field):
    return isinstance(field, (models.OneToOneField, models.ForeignKey, models.OneToOneRel))


def many_to(field):
    if isinstance(field, models.OneToOneRel):
        # OneToOneRel is subclass of ManyToOneRel
        return False
    return isinstance(field, (models.ManyToManyField, models.ManyToManyRel, models.ManyToOneRel))


def to_many(field):
    return isinstance(field, (models.ManyToManyField, models.ManyToManyRel, models.ForeignKey))


def to_one(field):
    return isinstance(field, (models.OneToOneField, models.OneToOneRel, models.ManyToOneRel))


class DjangoModelFieldAdaptor(ModelFieldAdaptor):
    field: Union[models.Field, ForeignObjectRel, exp.BaseExpression, exp.Combinable]
    model: 'DjangoModelAdaptor'

    def __init__(self, field, addon: str = None, model=None, lookup_name: str = None):
        if isinstance(field, DeferredAttribute):
            field = field.field
            if not lookup_name:
                lookup_name = getattr(field, 'field_name', getattr(field, 'name', None))

        if not self.qualify(field):
            raise TypeError(f'Invalid field: {field}')

        super().__init__(field, addon, model, lookup_name)
        self.validate_addon()

    @property
    def multi_relations(self):
        return self.lookup_name and '__' in self.lookup_name

    def validate_addon(self):
        if not self.addon:
            return
        if not isinstance(self.addon, str):
            raise TypeError(f'Invalid addon: {repr(self.addon)}, must be str')
        if self.is_concrete:
            _t = self.field.get_internal_type()
            addons = constant.ADDON_FIELD_LOOKUPS.get(_t, [])
            if self.addon not in addons:
                warnings.warn(f'Invalid addon: {repr(self.addon)} for field: {self.field},'
                              f' only {addons} are supported')
        else:
            raise TypeError(f'Not concrete field: {self.field} cannot have addon: {repr(self.addon)}')

    @property
    def title(self) -> Optional[str]:
        name = self.field.verbose_name
        if name != self.field.name:
            return name
        return None

    @property
    def description(self) -> Optional[str]:
        return self.field.help_text or None

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, (models.Field, ForeignObjectRel, exp.BaseExpression, exp.Combinable))

    @property
    def field_model(self):
        if self.is_exp:
            return None
        return getattr(self.field, 'model', None)

    @property
    def target_field(self) -> Optional['ModelFieldAdaptor']:
        target_field = getattr(self.field, 'target_field', None)
        if target_field:
            return self.__class__(target_field, model=self.model)
        return None

    @property
    def remote_field(self) -> Optional['ModelFieldAdaptor']:
        remote_field = getattr(self.field, 'remote_field', None)
        if remote_field and self.field.related_model:
            return self.__class__(remote_field, model=self.field.related_model)
        return None

    @property
    def related_model(self):
        if self.is_exp:
            return None
        rel = getattr(self.field, 'related_model')
        if rel:
            if rel == 'self':
                return self
            from .model import DjangoModelAdaptor
            return DjangoModelAdaptor(rel)
        return None

    @property
    def is_nullable(self):
        if not self.is_concrete:
            return True
        return getattr(self.field, 'null', False)

    @property
    def is_optional(self):
        if not self.is_concrete:
            return True
        return self.field.default != models.NOT_PROVIDED or self.is_auto

    @property
    def is_writable(self):
        if not self.is_concrete:
            return False
        if self.field == self.model.meta.auto_field:
            return False
        param = self.params
        auto_now_add = param.get('auto_now_add')
        auto_created = param.get('auto_created')
        if auto_now_add or auto_created:
            return False
        return True

    @property
    def is_unique(self):
        if not self.is_concrete:
            return False
        return self.field.unique

    @property
    def is_db_index(self):
        if not self.is_concrete:
            return False
        return self.field.db_index

    @property
    def is_auto(self):
        if not self.is_concrete:
            return False
        param = self.params
        auto_now_add = param.get('auto_now_add')
        auto_now = param.get('auto_now')
        auto_created = param.get('auto_created')
        if auto_now_add or auto_now or auto_created:
            return True
        return self.field == self.model.meta.auto_field

    @classmethod
    def _get_type(cls, field: models.Field) -> Optional[type]:
        if not isinstance(field, models.Field):
            return None
        _t = field.get_internal_type()
        for fields, t in constant.FIELDS_TYPE.items():
            if _t in fields:
                return t
        return None

    @classmethod
    def _get_params(cls, field: models.Field) -> dict:
        if not isinstance(field, models.Field):
            return {}
        return field.deconstruct()[3] or {}

    @property
    def type(self) -> type:
        return self._get_type(self.field)

    @property
    def params(self) -> dict:
        return self._get_params(self.field)

    @cached_property
    def rule(self) -> Type[Rule]:
        _type = None
        _args = []
        field = self.field

        if self.is_o2:
            mod = self.related_model
            if mod:
                _type = mod.pk_field.rule

        elif self.is_concrete:
            _type = self._get_type(self.field)

        elif self.is_exp:
            if isinstance(self.field, exp.Count):
                # shortcut for Count: do not set le limit
                return types.NaturalInt
            field = self.model.resolve_output_field(self.field)
            _type = self._get_type(field)

        elif self.is_many:
            _type = list
            target_field = self.target_field
            if target_field:
                _args = [target_field.rule]

        params = self._get_params(field)
        kwargs = {}

        if params.get('max_length'):
            kwargs['max_length'] = params['max_length']
        if params.get('min_length'):
            kwargs['min_length'] = params['min_length']
        if 'max_value' in params:
            kwargs['le'] = params['max_value']
        if 'min_value' in params:
            kwargs['ge'] = params['min_value']

        if isinstance(field, models.DecimalField):
            kwargs['max_length'] = field.max_digits
            kwargs['decimal_places'] = Lax(field.decimal_places)
        # for the reason that IntegerField is the base class of All integer fields
        # so the isinstance determine will be the last to include
        elif isinstance(field, models.IntegerField):
            if isinstance(field, models.PositiveSmallIntegerField):
                kwargs['ge'] = 0
                kwargs['le'] = constant.SM
            elif isinstance(field, models.AutoField):
                kwargs['ge'] = 1
                kwargs['le'] = constant.MD
            elif isinstance(field, models.BigAutoField):
                kwargs['ge'] = 1
                kwargs['le'] = constant.LG
            elif isinstance(field, models.BigIntegerField):
                kwargs['ge'] = -constant.LG
                kwargs['le'] = constant.LG
            elif isinstance(field, models.PositiveBigIntegerField):
                kwargs['ge'] = 0
                kwargs['le'] = constant.LG
            elif isinstance(field, models.PositiveIntegerField):
                kwargs['ge'] = 0
                kwargs['le'] = constant.MD
            elif isinstance(field, models.SmallIntegerField):
                kwargs['ge'] = -constant.SM
                kwargs['le'] = constant.SM
            else:
                kwargs['ge'] = -constant.MD
                kwargs['le'] = constant.MD

        return Rule.annotate(_type, *_args, constraints=kwargs)

    @property
    def name(self) -> Optional[str]:
        if self.is_exp:
            return None
        if hasattr(self.field, 'name'):
            return self.field.name
        if hasattr(self.field, 'field_name'):
            # toOneRel
            return self.field.field_name
        return None

    @property
    def query_name(self) -> Optional[str]:
        if self.is_exp:
            return None
        return self.lookup_name
        # name = self.name
        # if not name:
        #     return None
        # if not self.addon:
        #     return name
        # return f'{name}__{self.addon}'

    def check_query(self):
        qn = self.query_name
        if not qn:
            return
        try:
            if '__' not in qn:
                self.model.get_queryset(**{qn + '__isnull': False})
            else:
                try:
                    self.model.get_queryset(**{qn: None})
                except ValueError:
                    self.model.get_queryset(**{qn: ''})
        except exceptions.FieldError as e:
            raise exceptions.FieldError(f'Invalid query name: {repr(qn)} for {self.model.model}: {e}')
        except ValueError as e:
            print(f'failed to check query field: {repr(qn)} for {self.model.model}', e)
            pass

    @property
    def column_name(self) -> Optional[str]:
        if isinstance(self.field, models.Field):
            return self.field.column
        return None

    @property
    def to_field(self) -> Optional[str]:
        if self.is_fk:
            try:
                return self.field.to_fields[0]
            except IndexError:
                pass
        return None

    @property
    def relate_name(self) -> Optional[str]:
        if self.is_fk:
            return self.field.remote_field.get_cache_name()
        return None

    def get_supported_operators(self):
        pass

    @property
    def is_exp(self):
        return isinstance(self.field, (exp.BaseExpression, exp.Combinable))

    @property
    def is_combined(self):
        return isinstance(self.field, exp.CombinedExpression)

    @property
    def is_rel(self):
        return isinstance(self.field, ForeignObjectRel)

    @property
    def is_pk(self):
        return isinstance(self.field, models.Field) and self.field.primary_key

    @property
    def is_fk(self):
        return isinstance(self.field, models.ForeignKey)

    @property
    def is_concrete(self):
        if self.is_exp:
            return False
        return getattr(self.field, 'concrete', False)

    @property
    def is_m2m(self):
        return isinstance(self.field, (models.ManyToManyField, models.ManyToManyRel))

    @property
    def is_m2(self):
        return many_to(self.field)

    @property
    def is_2m(self):
        return to_many(self.field)

    @property
    def is_o2(self):
        return one_to(self.field)

    @property
    def is_2o(self):
        return to_one(self.field)

    @classmethod
    def get_exp_field(cls, expr) -> Optional[str]:
        if isinstance(expr, str):
            return expr
        if isinstance(expr, exp.CombinedExpression):
            return None
        if isinstance(expr, exp.F):
            return expr.name
        if not isinstance(expr, exp.BaseExpression):
            return None
        try:
            name = expr.deconstruct()[1][0]  # noqa
            if isinstance(name, exp.BaseExpression):  # maybe F
                return cls.get_exp_field(name)  # noqa
            if not isinstance(name, str):
                return None
            return name
        except (ValueError, IndexError, AttributeError):
            return None

    @classmethod
    def iter_combined_expression(cls, expr):
        if isinstance(expr, exp.CombinedExpression):
            exps = expr.deconstruct()[1]
            if multi(exps):
                for e in exps:
                    for i in cls.iter_combined_expression(e):
                        yield i
        elif isinstance(exp, (exp.BaseExpression, exp.Combinable)):
            yield exp
        return

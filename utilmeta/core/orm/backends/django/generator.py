from . import expressions as exp
from ..base import ModelFieldAdaptor
from utilmeta.core.orm.fields.filter import ParserFilter
from utilmeta.core.orm.fields.order import Order
from django.db import models
from django.db.models import Q
from utilmeta.utils import multi
from utilmeta.utils.error import Error
import warnings
from utilmeta.core.orm.generator import BaseQuerysetGenerator


class DjangoQuerysetGenerator(BaseQuerysetGenerator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.annotates = {}
        self.q = Q()
        self.orders = []

    def _get_unsliced_qs(self, base=None):
        self.process_data()
        if base is None:
            qs: models.QuerySet = self.model.get_queryset()
        else:
            if isinstance(base, models.QuerySet):
                if not issubclass(base.model, self.model.model):
                    raise TypeError(f'Invalid queryset: {base}')
                qs = base
            else:
                raise TypeError(f'Invalid queryset: {base}')
        if self.annotates:
            qs = qs.annotate(**self.annotates)
        if self.q:
            qs = qs.filter(self.q)
        if self.distinct and not qs.query.distinct and \
                not qs.query.combinator and \
                not qs.query.is_sliced:
            qs = qs.distinct()
        return qs

    def get_queryset(self, base=None) -> models.QuerySet:
        qs = self._get_unsliced_qs(base)
        if self.orders:
            qs = qs.order_by(*self.orders)
        if self.slice and not qs.query.is_sliced:
            qs = qs[self.slice]
        return qs

    def count(self, base=None) -> int:
        qs = self._get_unsliced_qs(base)
        return qs.count()

    # @awaitable(count)
    async def acount(self, base=None) -> int:
        qs = self._get_unsliced_qs(base)
        return await qs.acount()

    def process_filter(self, field: ParserFilter, value):
        if field.model_field and field.model_field.is_exp:
            self._add_annotate(field.attname or field.name, field.model_field.field)

        if field.query:
            q = field.query
            if callable(field.query):
                try:
                    q = field.query(value)
                except Exception as e:
                    prepend = f'{self.__class__}: apply filter: [{repr(field.name)}].order failed with error: '
                    if not field.fail_silently:
                        raise Error(e).throw(prepend=prepend)
                    warnings.warn(f'{prepend}{e}')
            if not isinstance(q, exp.Q):
                raise TypeError(f'Invalid query expression: {q}')
        else:
            q = Q(**{field.query_name: value})

        self.q &= q

        if field.order:
            order = field.order
            if callable(field.order):
                try:
                    order = field.order(value)
                except Exception as e:
                    prepend = f'{self.__class__}: apply filter: [{repr(field.name)}].order failed with error: '
                    if not field.fail_silently:
                        raise Error(e).throw(prepend=prepend)
                    warnings.warn(f'{prepend}{e}')
            if not multi(order):
                order = [order]
            self.orders.extend(order)

    def process_order(self, order: Order, field: ModelFieldAdaptor, name: str, flag: int = 1):
        if field.is_exp:
            self._add_annotate(name, field.field)
        name = field.query_name or name
        desc = flag < 0
        if order.nulls_first or order.nulls_last:
            f = exp.F(name)
            if desc:
                f = f.desc
            else:
                f = f.asc
            if order.nulls_first:
                f = f(nulls_first=True)
            else:
                f = f(nulls_last=True)
            order_field = f
        else:
            order_field = ('-' if desc else '') + name
        self.orders.append(order_field)

    def _add_annotate(self, key, expression: exp.BaseExpression, distinct_count: bool = True):
        if not isinstance(expression, (exp.BaseExpression, exp.Combinable)):
            raise TypeError(f'Invalid expression: {expression}')
        if distinct_count and isinstance(expression, exp.Count):
            expression.distinct = True
        if isinstance(expression, exp.Sum):
            expression = exp.Subquery(models.QuerySet(model=self.model.model).filter(
                pk=exp.OuterRef('pk')).annotate(v=expression).values('v'))
        self.annotates.setdefault(key, expression)

from django.db.models.aggregates import *
from django.db.models.functions import *
from django.db.models.expressions import (
    F,
    Q,
    Subquery,
    OuterRef,
    ResolvedOuterRef,
    Value,
    ValueRange,
    Case,
    When,
    Col,
    Window,
    Ref,
    RawSQL,
    Func,
    BaseExpression,
    RowRange,
    OrderBy,
    Exists,
    WindowFrame,
    Star,
    Expression,
    Combinable,
    CombinedExpression,
)

from django import VERSION

if VERSION[0] < 3:
    # compat
    from django.db.models.expressions import BaseExpression
    from django.db.models.functions.mixins import NumericOutputFieldMixin

    def _get_output_field(self, _original=BaseExpression._resolve_output_field):  # noqa
        try:
            return _original(self)  # noqa
        except AttributeError:
            from django.db.models.fields import FloatField

            return FloatField()

    BaseExpression._resolve_output_field = _get_output_field  # patch
    NumericOutputFieldMixin._resolve_output_field = _get_output_field


class SubqueryCount(Subquery):
    template = "(SELECT count(*) FROM (%(subquery)s) _count)"
    from django.db import models

    output_field = models.PositiveIntegerField()

    def __init__(self, queryset: models.QuerySet, output_field=None, **extra):
        if not queryset.query.select:
            queryset = queryset.values("pk")
        super().__init__(queryset, output_field=output_field, **extra)


class SubquerySum(Subquery):
    template = '(SELECT sum(_sum."%(column)s") FROM (%(subquery)s) _sum)'

    def __init__(self, queryset, column, output_field=None, **extra):
        if output_field is None:
            output_field = queryset.model._meta.get_field(column)
        super().__init__(queryset, output_field, column=column, **extra)

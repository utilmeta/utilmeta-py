from peewee import Model, ModelSelect, Expression, fn
from typing import Type
from ..base import ModelAdaptor, QuerysetAdaptor, QueryExpressionAdaptor, ModelFieldAdaptor


class PeeweeModelFieldAdaptor(ModelFieldAdaptor):
    pass


class PeeweeQuerysetAdaptor(QuerysetAdaptor):
    # model_adaptor_cls = PeeweeModelAdaptor
    queryset: ModelSelect

    @classmethod
    def qualify(cls, impl):
        return isinstance(impl, ModelSelect)

    @property
    def model(self):
        return self.queryset.model

    @property
    def base_queryset(self):
        return self.model.select()


class PeeweeQueryExpressionAdaptor(QueryExpressionAdaptor):
    obj: Expression

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, Expression)


class PeeweeModelAdaptor(ModelAdaptor):
    model: Type[Model]

    queryset_adaptor_cls = PeeweeQuerysetAdaptor
    query_expression_adaptor_cls = PeeweeQueryExpressionAdaptor

    @classmethod
    def qualify(cls, impl):
        return issubclass(impl, Model)

    def get_queryset(self):
        return self.model.select()


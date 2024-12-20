from peewee import Model, ModelSelect, Database
from typing import Type
from ..base import (
    ModelAdaptor,
    ModelQueryAdaptor,
    ModelFieldAdaptor,
)


class PeeweeModelFieldAdaptor(ModelFieldAdaptor):
    pass


class PeeweeQuerysetAdaptor(ModelQueryAdaptor):
    queryset_cls = ModelSelect
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

    @property
    def database(self) -> Database:
        raise NotImplementedError

    def exists(self) -> bool:
        return self.queryset.exists(self.database)

    def count(self) -> int:
        return self.queryset.count(self.database)


class PeeweeModelAdaptor(ModelAdaptor):
    model: Type[Model]
    field_adaptor_cls = PeeweeModelFieldAdaptor
    query_adaptor_cls = PeeweeQuerysetAdaptor

    @classmethod
    def qualify(cls, impl):
        return issubclass(impl, Model)

    def get_queryset(self, query=None, pk=None, using: str = None):
        return self.model.select()

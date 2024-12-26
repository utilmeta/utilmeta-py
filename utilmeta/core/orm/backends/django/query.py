from ..base import ModelQueryAdaptor
from django.db.models import QuerySet
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .model import DjangoModelAdaptor


class DjangoModelQueryAdaptor(ModelQueryAdaptor):
    queryset_cls = QuerySet
    queryset: QuerySet
    model: "DjangoModelAdaptor"

    @classmethod
    def qualify(cls, obj):
        return isinstance(obj, QuerySet)

    @property
    def using(self):
        return self.queryset.db

    def filter(self, *args, **kwargs) -> "DjangoModelQueryAdaptor":
        return self.__class__(self.queryset.filter(*args, **kwargs), model=self.model)

    def count(self) -> int:
        return self.queryset.count()

    async def acount(self) -> int:
        return await self.queryset.acount()

    def exists(self) -> int:
        return self.queryset.exists()

    async def aexists(self) -> int:
        return await self.queryset.aexists()

    def update(self, d=None, **data):
        return self.queryset.update(**self.get_kwargs(d, **data))

    async def aupdate(self, d=None, **data):
        return await self.queryset.aupdate(**self.get_kwargs(d, **data))

    def create(self, d=None, **data):
        return self.queryset.create(**self.get_kwargs(d, **data))

    async def acreate(self, d=None, **data):
        return await self.queryset.acreate(**self.get_kwargs(d, **data))

    def bulk_create(self, data: list, **kwargs):
        objs = self.queryset.bulk_create(data, **kwargs)
        return self.model.get_queryset([obj.pk for obj in objs], using=self.using)

    async def abulk_create(self, data: list, **kwargs):
        objs = await self.queryset.abulk_create(data, **kwargs)
        return self.model.get_queryset([obj.pk for obj in objs], using=self.using)

    def bulk_update(self, data: list, fields: list, using: str = None):
        return self.queryset.bulk_update(data, fields=fields)

    async def abulk_update(self, data: list, fields: list, using: str = None):
        return await self.queryset.abulk_update(data, fields=fields)

    def delete(self):
        num, *_ = self.queryset.delete()
        return num

    async def adelete(self):
        num, *_ = await self.queryset.adelete()
        return num

    def values(self, *fields, **kwargs) -> List[dict]:
        return list(self.queryset.values(*fields, **kwargs))

    async def avalues(self, *fields, **kwargs) -> List[dict]:
        return [val async for val in self.queryset.values(*fields)]

    def get_instance(self):
        return self.queryset.first()

    async def aget_instance(self):
        return await self.queryset.afirst()

    # ------------------------------------------------------------------------------------

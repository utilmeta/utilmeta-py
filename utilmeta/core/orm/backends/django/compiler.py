import inspect

from utilmeta.core.orm.compiler import BaseQueryCompiler
from ...fields.field import ParserQueryField
from . import expressions as exp
from .constant import PK, ID, SEG
from django.db import models
from utilmeta.utils import awaitable, Error, multi, pop
from typing import List
from .queryset import AwaitableQuerySet
import asyncio
import warnings
from datetime import timedelta
from utilmeta.core.orm import exceptions
from enum import Enum


class DjangoQueryCompiler(BaseQueryCompiler):
    queryset: models.QuerySet

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_queryset()
        self.pk_fields = set()
        self.fields = []
        self.expressions = dict(self.context.force_expressions or {})
        self.isolated_fields = {}

    def _get_pk(self, value, robust: bool = False):
        if robust:
            if isinstance(value, models.Model):
                return getattr(value, 'pk', None)
        else:
            if isinstance(value, self.model.model):
                return getattr(value, 'pk', None)
        from utilmeta.core.orm.schema import Schema
        if isinstance(value, Schema):
            return value.pk
        if isinstance(value, dict):
            for field in self.parser.pk_names:
                if field in value:
                    return value[field]
            return None
        return value

    def init_queryset(self):
        if self.queryset is None:
            self.queryset = self.model.get_queryset().none()
        elif not isinstance(self.queryset, models.QuerySet):
            if multi(self.queryset):
                pks = []
                for val in self.queryset:
                    pk = self._get_pk(val)
                    if pk is not None:
                        pks.append(pk)
                if not pks:
                    self.queryset = self.model.get_queryset().none()
                else:
                    self.queryset = self.model.get_queryset(pk__in=pks)
            else:
                pk = self._get_pk(self.queryset)
                if pk is not None:
                    self.queryset = self.model.get_queryset(pk=pk)
                else:
                    self.queryset = self.model.get_queryset().none()

        if self.context.using:
            self.queryset = self.queryset.using(self.context.using)
        if self.context.single:
            if not self.queryset.query.is_sliced:
                self.queryset = self.queryset[:1]

    def set_values(self, values: List[dict]):
        if not values:
            return
        elif not isinstance(values, list):
            values = [values]
        result = []
        # deduplicate
        pk_list = []
        pk_map = {}
        for val in values:
            val: dict
            pk = val[PK]
            if pk is None:
                continue
            if pk in pk_list:
                continue
            pk_list.append(pk)
            pk_map[pk] = val
            result.append(val)
        self.pk_list = pk_list
        self.pk_map = pk_map
        self.values: List[dict] = result

    def clear_pks(self):
        for val in self.values:
            if PK not in self.pk_fields:
                pk = pop(val, PK)
            else:
                pk = val[PK]
            for f in self.pk_fields:
                val.setdefault(f, pk)

    def get_values(self):
        if self.queryset.query.is_empty():
            return []
        self.process_fields()
        values = list(self.queryset.values(PK, *self.fields, **self.expressions))
        self.set_values(values)
        if not self.values:
            return []
        self._resolve_recursion()
        for field in self.isolated_fields.values():
            try:
                self.query_isolated_field(field)
            except Exception as e:
                self.handle_isolated_field(field, e)
        self.clear_pks()
        return self.values

    @awaitable(get_values)
    async def get_values(self):
        if self.queryset.query.is_empty():
            return []
        self.process_fields()
        values_qs = self.queryset.values(PK, *self.fields, **self.expressions)
        if isinstance(self.queryset, AwaitableQuerySet):
            values = await values_qs.result(one=self.context.single)
        else:
            values = [val async for val in values_qs]

        self.set_values(values)

        if not self.values:
            return []

        self._resolve_recursion()

        async def query_isolated(f):
            try:
                await self.query_isolated_field(f)
            except Exception as e:
                self.handle_isolated_field(f, e)

        tasks = []
        if self.pk_list:
            for key, field in self.isolated_fields.items():
                tasks.append(asyncio.create_task(query_isolated(field), name=key))

        if tasks:
            try:
                await asyncio.gather(*tasks)
                # use await here to expect throw the exception to terminate the whole query
            except Exception:
                for t in tasks:
                    t.cancel()
                # if error raised here, it's because the force_raise_error flag or field.fail_silently=False
                # either of which we will directly cancel the unfinished tasks and raise the error
                raise

        self.clear_pks()
        return self.values

    def handle_isolated_field(self, field: ParserQueryField, e: Exception):
        prepend = f'{self.parser.name}[{self.parser.model.model}] ' \
                  f'serialize isolated field: [{repr(field.name)}] failed with error: '
        if not field.fail_silently or self.context.force_raise_error:
            raise Error(e).throw(prepend=prepend)
        warnings.warn(f'{prepend}{e}')

    def process_expression(self, expression):
        if isinstance(expression, exp.Sum) and self.queryset.query.is_sliced:
            # use subquery to avoid wrong value when sum multiple aggregates
            expression = exp.Subquery(self.base_queryset().filter(
                pk=exp.OuterRef('pk')).annotate(v=expression).values('v'))
            # once a queryset is sliced, query it's many-related data may return wrong values
            # for example, qs[:2] should return [{"id": 1, "many": [1, 2, 3]}, {...}], but the slice of main queryset
            # is affected on the join queries, so it only return [{"id": 1, "many": [1, 2]}, {...}]
            # as the max num of many-to relations is less than the slice is has taken
            # the annotations will also be affected, if Count("many") on that query, the correct will be 3
            # but the sliced will return 2 instead
            # so when a queryset is sliced and the fields contains many-field or annotates
            # make the queryset unsliced and only contains the pks in the sliced query (which is identical)
        return expression

    @classmethod
    def get_query_name(cls, field: ParserQueryField):
        name = field.field_name
        if not isinstance(name, str):
            return None
        return name.replace('.', '__')

    def process_query_field(self, field: ParserQueryField):
        if field.primary_key:
            self.pk_fields.add(field.name)
            return

        if field.isolated:
            # even for expression
            # because isolated expression does not need to process
            # for queryset field there is no model_field, so we'll not check that
            self.isolated_fields.setdefault(field.name, field)
            if field.related_schema:
                self.recursively = True
        elif field.expression:
            self.expressions.setdefault(field.name, self.process_expression(field.expression))
            return

        if field.included:
            # including the isolated fk schema, we need to query the exact fk
            query_name = self.get_query_name(field)
            if query_name:
                if query_name == field.name:
                    self.fields.append(query_name)
                else:
                    self.expressions.setdefault(field.name, exp.F(query_name))

    def query_isolated_field(self, field: ParserQueryField):
        """
        - field_config.queryset
            - queryset has values
                use that
            - field_config.related_schema
                use that
            - PK
        - field_config.queryset.is_sliced
            need to execute for every item
        """
        # use many model in case of many_field__common_field
        # if relate result is limited, query needs to fill one-by-one
        pk_list = self.pk_list
        if not pk_list:
            return
        pk_map = {}
        key = field.name
        current_qs: models.QuerySet = self.model.get_queryset(pk__in=pk_list)
        related_qs: models.QuerySet = field.queryset
        # - current_qs.filter(pk__in=self.pk_list).values(related_field, PK)   [no related_qs provided]
        # - current_qs.filter(pk__in=self.pk_list).values(related_field=exp.Subquery(related_qs), PK)
        #   - related_schema.serialize(related_qs)   [related_schema provided]

        if field.expression:
            pk_map = {val[PK]: val[key] for val in current_qs.values(PK, **{key: field.expression})}
        elif related_qs is None:
            # directly query relation without filter/order
            # in this way,
            if field.included:
                # o2 / fk
                for val in self.values:
                    fk = val.get(key)
                    if fk is not None:
                        pk_map.setdefault(val[PK], fk)
            else:
                if field.func:
                    if field.func_multi:
                        pk_map = self.normalize_pk_map(
                            field.func(*self.pk_list, __class__=self.parser.obj)
                        )
                        # normalize pks from user input
                    else:
                        for pk in self.pk_list:
                            pk_map[str(pk)] = self.normalize_pk_list(
                                field.func(pk, __class__=self.parser.obj)
                            )

                    # normalize user input
                else:
                    # many related field / common values
                    # like author__followers / author__followers__join_date
                    # we need to serialize its value first
                    if field.model_field.remote_field and field.model_field.remote_field.is_pk:
                        pk_map = {str(pk): pk for pk in pk_list}
                    else:
                        _args = []
                        _kw = {}
                        qn = self.get_query_name(field)
                        if qn == key:
                            _args = (key,)
                        else:
                            _kw = {key: exp.F(qn)}
                        for val in current_qs.values(PK, *_args, **_kw):
                            rel = val[key]
                            if rel is not None:
                                pk_map.setdefault(val[PK], []).append(rel)
        else:
            if not related_qs.query.select:
                # 1. queryset has no values
                # 2. this is a related schema query, we should override the values to PK
                related_qs = related_qs.values(PK)
                # sometimes user may use an intermediate table to query the target table
                # so the final values might not be the exact 'pk'
                # we do not override if user has already selected

            for val in current_qs.values(PK, **{key: exp.Subquery(related_qs)}):
                rel = val[key]
                if rel is not None:
                    pk_map.setdefault(val[PK], []).append(rel)

            # if related_qs.query.is_sliced:
            #     # because this slice should be per-item, so we need to calculate
            #     for pk in pk_list:
            #         for val in self.model.get_queryset(pk=pk).values(**{key: exp.Subquery(related_qs)}):
            #             rel = val[key]
            #             if rel is not None:
            #                 pk_map.setdefault(pk, []).append(rel)
            # else:
            #     # relate_name: List[xx] = orm.Field(Mod.objects.filter(reverse=OuterRef('pk')).values('name'))
            #     for val in current_qs.values(PK, **{key: exp.Subquery(related_qs)}):
            #         rel = val[key]
            #         if rel is not None:
            #             pk_map.setdefault(val[PK], []).append(rel)

        # convert pk_map to str key
        pk_map = {str(k): v for k, v in pk_map.items()}

        if field.related_schema:
            related_pks = set()
            for val in pk_map.values():
                if isinstance(val, list):
                    related_pks.update(val)
                elif val is not None:
                    try:
                        related_pks.add(val)
                    except TypeError:
                        # like un-hashable data
                        continue

            result_map = dict(self.recursive_map.get(field.related_schema) or {})
            # try to use cached shared recursive map before query
            related_pks = related_pks.difference(result_map)

            if related_pks:
                # other than shared cache, it's the pks that has not been queried by this round
                for inst in field.related_schema.serialize(
                    # field.related_model.get_queryset(pk__in=list(related_pks))
                    # if field.related_model else
                    list(related_pks),  # for func without related model
                    context=self.get_related_context(
                        field, force_expressions={SEG + PK: exp.F('pk')}
                    )
                ):
                    pk = pop(inst, SEG + PK) or inst.get(PK) or inst.get(ID)
                    # try to get pk value
                    if pk is None:
                        continue
                    result_map[pk] = inst

            # insert values
            for val in self.values:
                rel = pk_map.get(str(val[PK]))
                if rel is None:
                    val[key] = [] if field.related_single is False else None
                    # set to a deterministic value instead of its original query value
                    # otherwise schema parsing maybe failed
                    continue
                if isinstance(rel, list):
                    rel_values = []
                    for r in rel:
                        res = result_map.get(r)
                        if res is not None:
                            rel_values.append(res)
                    if field.related_single:
                        rel_values = rel_values[0] if rel_values else None
                    val[key] = rel_values
                else:
                    res = result_map.get(rel)
                    if res is not None:
                        # not setdefault
                        # because fk value is already set here
                        val[key] = res
                    else:
                        # set None, in case the raw fk value might fail the parsing
                        # this condition is rare when the serialized fk values is not in the result
                        val[key] = None
        else:
            # common value / expression value is all user need
            for val in self.values:
                rel = pk_map.get(str(val[PK]))
                if rel is None and field.related_single is False:
                    rel = []
                val.setdefault(key, rel)  # even for None value

    def normalize_pk_list(self, value):
        if isinstance(value, models.QuerySet):
            value = list(value.values_list('pk', flat=True))
        if not multi(value):
            value = [value]
        lst = []
        for v in value:
            pk = self._get_pk(v, robust=True)
            if pk is None:
                continue
            lst.append(pk)
        return lst

    @awaitable(normalize_pk_list)
    async def normalize_pk_list(self, value):
        if isinstance(value, models.QuerySet):
            value = [pk async for pk in value.values_list('pk', flat=True)]
        if not multi(value):
            value = [value]
        lst = []
        for v in value:
            pk = self._get_pk(v, robust=True)
            if pk is None:
                continue
            lst.append(pk)
        return lst

    def normalize_pk_map(self, pk_map: dict):
        if not isinstance(pk_map, dict):
            raise TypeError(f'Invalid pk map: {pk_map}, must be a dict')
        result = {}
        for k, value in pk_map.items():
            lst = self.normalize_pk_list(value)
            if lst:
                result[str(k)] = lst
        return result

    @awaitable(normalize_pk_map)
    async def normalize_pk_map(self, pk_map: dict):
        if not isinstance(pk_map, dict):
            raise TypeError(f'Invalid pk map: {pk_map}, must be a dict')
        result = {}
        for k, value in pk_map.items():
            lst = await self.normalize_pk_list(value)
            if lst:
                result[str(k)] = lst
        return result

    @awaitable(query_isolated_field)
    async def query_isolated_field(self, field: ParserQueryField):
        """
        - field_config.queryset
            - queryset has values
                use thatcd 00
            - field_config.related_schema
                use that
            - PK
        - field_config.queryset.is_sliced
            need to execute for every item
        """
        # use many model in case of many_field__common_field
        # if relate result is limited, query needs to fill one-by-one
        pk_list = self.pk_list
        if not pk_list:
            return
        pk_map = {}
        key = field.name
        current_qs: models.QuerySet = self.model.get_queryset(pk__in=pk_list)
        related_qs: models.QuerySet = field.queryset
        # - current_qs.filter(pk__in=self.pk_list).values(related_field, PK)   [no related_qs provided]
        # - current_qs.filter(pk__in=self.pk_list).values(related_field=exp.Subquery(related_qs), PK)
        #   - related_schema.serialize(related_qs)   [related_schema provided]

        if field.expression:
            pk_map = {val[PK]: val[key] async for val in current_qs.values(PK, **{key: field.expression})}
        elif related_qs is None:
            # directly query relation without filter/order
            # in this way,
            if field.included:
                for val in self.values:
                    fk = val.get(key)
                    if fk is not None:
                        pk_map.setdefault(val[PK], fk)
            else:
                # many related field / common values
                # like author__followers / author__followers__join_date
                # we need to serialize its value first
                if field.func:
                    if field.func_multi:
                        pk_map = field.func(*self.pk_list, __class__=self.parser.obj)
                        if inspect.isawaitable(pk_map):
                            pk_map = await pk_map
                        pk_map = await self.normalize_pk_map(pk_map)
                        # normalize pks from user input
                    else:
                        for pk in self.pk_list:
                            rel_qs = field.func(pk, __class__=self.parser.obj)
                            if inspect.isawaitable(rel_qs):
                                rel_qs = await rel_qs
                            pk_map[str(pk)] = await self.normalize_pk_list(rel_qs)

                else:
                    if field.model_field.is_2o:
                        # fixme: also no many-relates included in the reverse relations
                        # many to one
                        if field.model_field.remote_field and field.model_field.remote_field.is_pk:
                            pk_map = {str(pk): pk for pk in pk_list}
                        else:
                            f, c = field.model_field.reverse_lookup
                            m = field.model_field.related_model
                            # use reverse query due to the unfixed issue on the async backend
                            if m and f:
                                async for val in m.get_queryset(
                                        **{f + '__in': pk_list}).values(c or PK, __target=exp.F(f)):
                                    rel = val['__target']
                                    if rel is not None:
                                        pk_map.setdefault(rel, []).append(val[c or PK])
                    else:
                        _args = []
                        _kw = {}
                        qn = self.get_query_name(field)
                        if qn == key:
                            _args = (key,)
                        else:
                            _kw = {key: exp.F(qn)}
                        async for val in current_qs.values(PK, *_args, **_kw):
                            rel = val[key]
                            if rel is not None:
                                pk_map.setdefault(val[PK], []).append(rel)
        else:
            if not related_qs.query.select:
                # 1. queryset has no values
                # 2. this is a related schema query, we should override the values to PK
                related_qs = related_qs.values(PK)

            async for val in current_qs.values(PK, **{key: exp.Subquery(related_qs)}):
                rel = val[key]
                if rel is not None:
                    pk_map.setdefault(val[PK], []).append(rel)

            # if related_qs.query.is_sliced:
            #     # because this slice should be per-item, so we need to calculate
            #     if related_qs.query.high_mark == related_qs.query.low_mark + 1:
            #         # high mark not None, and the result limit is 1
            #         async for val in current_qs.values(PK, **{key: exp.Subquery(related_qs)}):
            #             rel = val[key]
            #             if rel is not None:
            #                 pk_map.setdefault(val[PK], []).append(rel)
            #     else:
            #         for pk in pk_list:
            #             async for val in related_qs.filter():
            #                 pass
            #
            #             async for val in self.model.get_queryset(pk=pk).values(**{key: exp.Subquery(related_qs)}):
            #                 rel = val[key]
            #                 if rel is not None:
            #                     pk_map.setdefault(pk, []).append(rel)
            # else:
            #     # relate_name: List[xx] = orm.Field(Mod.objects.filter(reverse=OuterRef('pk')).values('name'))
            #     async for val in current_qs.values(PK, **{key: exp.Subquery(related_qs)}):
            #         rel = val[key]
            #         if rel is not None:
            #             pk_map.setdefault(val[PK], []).append(rel)

        pk_map = {str(k): v for k, v in pk_map.items()}

        if field.related_schema:
            related_pks = set()
            for val in pk_map.values():
                if isinstance(val, list):
                    related_pks.update(val)
                elif val is not None:
                    try:
                        related_pks.add(val)
                    except TypeError:
                        # like un-hashable data
                        continue

            result_map = dict(self.recursive_map.get(field.related_schema) or {})
            # try to use cached shared recursive map before query
            related_pks = related_pks.difference(result_map)

            if related_pks:
                for inst in await field.related_schema.aserialize(
                    # field.related_model.get_queryset(pk__in=list(related_pks))
                    # if field.related_model else
                    list(related_pks),
                    # for func without related model,
                    # or the related schema model is not exactly the related model (maybe sub model)
                    context=self.get_related_context(
                        field, force_expressions={SEG + PK: exp.F('pk')}
                    )
                ):
                    pk = pop(inst, SEG + PK) or inst.get(PK) or inst.get(ID)
                    # try to get pk value
                    if pk is None:
                        continue
                    result_map[pk] = inst
            # insert values
            for val in self.values:
                rel = pk_map.get(str(val[PK]))
                if rel is None:
                    val[key] = [] if field.related_single is False else None
                    # set to a deterministic value instead of its original query value
                    # otherwise schema parsing maybe failed
                    continue
                elif isinstance(rel, list):
                    rel_values = []
                    for r in rel:
                        res = result_map.get(r)
                        if res is not None:
                            rel_values.append(res)
                    if field.related_single:
                        rel_values = rel_values[0] if rel_values else None
                    val[key] = rel_values
                else:
                    res = result_map.get(rel)
                    if res is not None:
                        # not setdefault
                        # because fk value is already set here
                        val[key] = res
                    else:
                        # set None, in case the raw fk value might fail the parsing
                        # this condition is rare when the serialized fk values is not in the result
                        val[key] = None
        else:
            # common value / expression value is all user need
            for val in self.values:
                rel = pk_map.get(str(val[PK]))
                if rel is None and field.related_single is False:
                    rel = []
                val.setdefault(key, rel)  # even for None value

    def process_value(self, field: ParserQueryField, value):
        if not field.model_field:
            return value
        if isinstance(field.model_field, models.DurationField) and isinstance(value, (int, float)):
            return timedelta(seconds=value)
        elif multi(value):
            # convert tuple/set to list
            return list(value)
        elif isinstance(value, Enum):
            return value.value
        return value

    def commit_data(self, data: dict):
        data = self.process_data(data)
        for p in {PK, ID, *self.parser.pk_names}:
            pk = pop(data, p)
            if pk is not None:
                self.queryset = self.queryset.filter(pk=pk)
        if data:
            self.queryset.update(**data)
        return self.queryset

    @awaitable(commit_data)
    async def commit_data(self, data: dict):
        data = self.process_data(data)
        for p in {PK, ID, *self.parser.pk_names}:
            pk = pop(data, p)
            if pk is not None:
                self.queryset = self.queryset.filter(pk=pk)
        if data:
            await self.queryset.update(**data)
        return self.queryset

    def save_data(self, data, must_create: bool = False, must_update: bool = False):
        if multi(data):
            # TODO: implement bulk create/update
            pk_list = []
            for val in data:
                pk = self.save_data(val)
                if pk is not None:
                    pk_list.append(pk)
            return pk_list
        else:
            from utilmeta.core.orm.schema import Schema
            pk = None
            if isinstance(data, Schema):
                pk = data.pk
            elif isinstance(data, dict):
                for p in {PK, ID, *self.parser.pk_names}:
                    pk = data.get(p)
                    if pk is not None:
                        break
            data = self.process_data(data)
            if pk is None:
                # create
                if must_update:
                    raise exceptions.MissingPrimaryKey
                obj = self.model.create(data)
                pk = obj.pk
            else:
                # attempt to update
                # then create if no rows was updated
                if must_create:
                    rows = 0
                else:
                    rows = self.model.update(data, pk=pk)
                if not rows:
                    if must_update:
                        raise exceptions.UpdateFailed
                    obj = self.model.create(data)
                    pk = obj.pk
            return pk

    @awaitable(save_data)
    async def save_data(self, data, must_create: bool = False, must_update: bool = False):
        if multi(data):
            # TODO: implement bulk create/update
            pk_list = []
            for val in data:
                pk = await self.save_data(val, must_create=must_create, must_update=must_update)
                if pk is not None:
                    pk_list.append(pk)
            return pk_list
        else:
            from utilmeta.core.orm.schema import Schema
            pk = None
            if isinstance(data, Schema):
                pk = data.pk
            elif isinstance(data, dict):
                for p in {PK, ID, *self.parser.pk_names}:
                    pk = data.get(p)
                    if pk is not None:
                        break

            data = self.process_data(data)
            if pk is None:
                if must_update:
                    raise exceptions.MissingPrimaryKey
                # create
                obj = await self.model.create(data)
                pk = obj.pk
            else:
                # attempt to update
                # then create if no rows was updated
                if not must_create:
                    exists = await self.model.get_queryset(pk=pk).aexists()
                    if exists:
                        await self.model.update(data, pk=pk)
                    else:
                        if must_update:
                            raise exceptions.UpdateFailed
                        must_create = True
                if must_create:
                    obj = await self.model.create(data)
                    pk = obj.pk
            return pk

import inspect
from django.db.models import QuerySet, Manager, Model, sql, AutoField
from django.db.models.options import Options
from django.db.models.query import (
    ValuesListIterable,
    NamedValuesListIterable,
    FlatValuesListIterable,
    ModelIterable,
)
from django.core import exceptions
from django.utils.functional import partition
from utilmeta.utils import awaitable
from .expressions import Count, Case, When, Cast, Col
from utilmeta.core.orm import exceptions
from .deletion import AwaitableCollector
from typing import Optional, Tuple
from django.db.models import sql
from django.core.exceptions import EmptyResultSet
from django.db.models.sql.compiler import SQLUpdateCompiler, SQLCompiler
from ...databases import DatabaseConnections
from .expressions import Ref, Value
import django
from datetime import date, time, timedelta, datetime
from asgiref.sync import sync_to_async

try:
    from django.db.models.utils import resolve_callables
except ImportError:

    def resolve_callables(mapping):
        for k, v in mapping.items():
            yield k, v() if callable(v) else v


# def get_connection_Feature(conn, feature_name: str):
#     try:
#         return getattr(conn.features, feature_name)
#     except exceptions.SynchronousOnlyOperation:
#         attrs = {}
#
#         @omit
#         def getter():
#             attrs[feature_name] = getattr(conn.features, feature_name)
#
#         getter()
#         return attrs.get(feature_name)


class DummyContent:
    def __enter__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def clear_query_ordering(query, force=False):
    if django.VERSION < (4, 0):
        query.clear_ordering(force_empty=force)
    else:
        query.clear_ordering(force=force)


class AwaitableSQLUpdateCompiler(SQLUpdateCompiler):
    connections_cls = DatabaseConnections

    def pre_sql_setup(self):
        # do nothing
        pass

    async def async_pre_sql_setup(self):
        """
        If the update depends on results from other tables, munge the "where"
        conditions to match the format required for (portable) SQL updates.

        If multiple updates are required, pull out the id values to update at
        this point so that they don't change as a result of the progressive
        updates.
        """
        refcounts_before = self.query.alias_refcount.copy()
        # Ensure base table is in the query
        self.query.get_initial_alias()
        count = self.query.count_active_tables()
        if not self.query.related_updates and count == 1:
            return
        query = self.query.chain(klass=sql.Query)
        query.select_related = False
        clear_query_ordering(query, True)
        # query.clear_ordering(force=True)
        query.extra = {}
        query.select = []
        meta = query.get_meta()
        fields = [meta.pk.name]
        related_ids_names = []
        for related in self.query.related_updates:
            if all(
                path.join_field.primary_key for path in meta.get_path_to_parent(related)
            ):
                # If a primary key chain exists to the targeted related update,
                # then the meta.pk value can be used for it.
                related_ids_names.append((related, meta.pk.column))
            else:
                # This branch will only be reached when updating a field of an
                # ancestor that is not part of the primary key chain of a MTI
                # tree.
                related_ids_names.append((related, related._meta.pk.columm))
                fields.append(related._meta.pk.name)
        query.add_fields(fields)
        # ------------------
        SQLCompiler.pre_sql_setup(self)
        # not super()

        must_pre_select = (
            count > 1 and not self.connection.features.update_can_self_select
        )

        # Now we adjust the current query: reset the where clause and get rid
        # of all the tables we don't need (since they're in the sub-select).

        if django.VERSION >= (4, 0):
            self.query.clear_where()
        else:
            from django.db.models.sql.where import WhereNode

            self.query.where = WhereNode()

        if self.query.related_updates or must_pre_select:
            # Either we're using the idents in multiple update queries (so
            # don't want them to change), or the db backend doesn't support
            # selecting from the updating table (e.g. MySQL).
            idents = []
            import collections

            related_ids = collections.defaultdict(list)
            compiler = query.get_compiler(self.using)
            q, params = compiler.as_sql()
            db = self.connections_cls.get(self.using)

            for obj in await db.fetchall(q, params):
                idents.append(obj[meta.pk.column])
                for parent, name in related_ids_names:
                    related_ids[parent].append(obj[name])

            # for rows in query.get_compiler(self.using).execute_sql(MULTI):
            #     idents.extend(r[0] for r in rows)
            #     for parent, index in related_ids_index:
            #         related_ids[parent].extend(r[index] for r in rows)

            filters = ("pk__in", idents)
            if django.VERSION >= (4, 0):
                self.query.add_filter(*filters)
            else:
                self.query.add_filter(filters)

            if django.VERSION < (3, 2):
                self.query.related_ids = idents
            else:
                self.query.related_ids = related_ids
        else:
            # The fast path. Filters and updates in one query.
            filters = ("pk__in", query)
            if django.VERSION >= (4, 0):
                self.query.add_filter(*filters)
            else:
                self.query.add_filter(filters)
        self.query.reset_refcounts(refcounts_before)

    async def async_execute_sql(self, case_update: bool = False):
        """
        Execute the specified update. Return the number of rows affected by
        the primary update query. The "primary update query" is the first
        non-empty query that is executed. Row counts for any subsequent,
        related queries are not available.
        """
        await self.async_pre_sql_setup()
        q, params = self.as_sql()
        if case_update:
            params = [self._parse_update_param(p) for p in params]
        db = self.connections_cls.get(self.using)
        if q:
            await db.fetchone(q, params)
        from django.db import connections

        for query in self.query.get_related_updates():
            compiler = self.__class__(
                query, connection=connections[self.using], using=self.using
            )
            await compiler.async_execute_sql(case_update)

    @classmethod
    def _parse_update_param(cls, param):
        if isinstance(param, (datetime, date, time)):
            return str(param)
        elif isinstance(param, timedelta):
            return param.total_seconds()
        elif isinstance(param, (list, tuple, set)):
            return "{%s}" % ",".join([str(p) for p in param])
        return param


class AwaitableQuery(sql.Query):
    connections_cls = DatabaseConnections

    # adapt backend
    if django.VERSION < (4, 2):
        if django.VERSION < (3, 2):

            def exists(self, using, limit=True):
                q = self.clone()
                if not q.distinct:
                    if q.group_by is True:
                        q.add_fields(
                            (f.attname for f in self.model._meta.concrete_fields), False
                        )
                        # Disable GROUP BY aliases to avoid orphaning references to the
                        # SELECT clause which is about to be cleared.
                        q.set_group_by(allow_aliases=False)
                    q.clear_select_clause()
                q.clear_ordering(True)
                q.set_limits(high=1)
                compiler = q.get_compiler(using=using)
                compiler.query.add_extra({"a": 1}, None, None, None, None, None)
                compiler.query.set_extra_mask(["a"])
                return compiler.query

        else:

            def exists(self, using, limit=True):
                q = super().exists(using, limit=limit)
                q.add_annotation(Value("1"), "a")  # use str instead of int
                return q

        def get_aggregation_query(self, added_aggregate_names, using=None):
            """
            Return the dictionary with the values of the existing aggregations.
            """
            # ---------------------------------------
            # COPIED DIRECTLY FROM DJANGO 4.1.5
            existing_annotations = [
                annotation
                for alias, annotation in self.annotations.items()
                if alias not in added_aggregate_names
            ]
            # Decide if we need to use a subquery.
            #
            # Existing annotations would cause incorrect results as get_aggregation()
            # must produce just one result and thus must not use GROUP BY. But we
            # aren't smart enough to remove the existing annotations from the
            # query, so those would force us to use GROUP BY.
            #
            # If the query has limit or distinct, or uses set operations, then
            # those operations must be done in a subquery so that the query
            # aggregates on the limit and/or distinct results instead of applying
            # the distinct and limit after the aggregation.
            if (
                isinstance(self.group_by, tuple)
                or self.is_sliced
                or existing_annotations
                or self.distinct
                or self.combinator
            ):
                from django.db.models.sql.subqueries import AggregateQuery

                inner_query = self.clone()
                inner_query.subquery = True
                if django.VERSION < (3, 2):
                    outer_query = AggregateQuery(self.model)
                else:
                    outer_query = AggregateQuery(self.model, inner_query)
                inner_query.select_for_update = False
                inner_query.select_related = False
                inner_query.set_annotation_mask(self.annotation_select)
                # Queries with distinct_fields need ordering and when a limit is
                # applied we must take the slice from the ordered query. Otherwise
                # no need for ordering.
                clear_query_ordering(inner_query, False)
                # inner_query.clear_ordering(force=False)
                if not inner_query.distinct:
                    # If the inner query uses default select and it has some
                    # aggregate annotations, then we must make sure the inner
                    # query is grouped by the main model's primary key. However,
                    # clearing the select clause can alter results if distinct is
                    # used.
                    has_existing_aggregate_annotations = any(
                        annotation
                        for annotation in existing_annotations
                        if getattr(annotation, "contains_aggregate", True)
                    )
                    if inner_query.default_cols and has_existing_aggregate_annotations:
                        inner_query.group_by = (
                            self.model._meta.pk.get_col(
                                inner_query.get_initial_alias()
                            ),
                        )
                    inner_query.default_cols = False

                relabels = {t: "subquery" for t in inner_query.alias_map}
                relabels[None] = "subquery"
                # Remove any aggregates marked for reduction from the subquery
                # and move them to the outer AggregateQuery.
                col_cnt = 0
                for alias, expression in list(inner_query.annotation_select.items()):
                    annotation_select_mask = inner_query.annotation_select_mask
                    if expression.is_summary:
                        expression, col_cnt = inner_query.rewrite_cols(
                            expression, col_cnt
                        )
                        outer_query.annotations[alias] = expression.relabeled_clone(
                            relabels
                        )
                        del inner_query.annotations[alias]
                        annotation_select_mask.remove(alias)
                    # Make sure the annotation_select wont use cached results.
                    inner_query.set_annotation_mask(inner_query.annotation_select_mask)
                if (
                    inner_query.select == ()
                    and not inner_query.default_cols
                    and not inner_query.annotation_select_mask
                ):
                    # In case of Model.objects[0:3].count(), there would be no
                    # field selected in the inner query, yet we must use a subquery.
                    # So, make sure at least one field is selected.
                    inner_query.select = (
                        self.model._meta.pk.get_col(inner_query.get_initial_alias()),
                    )

                if django.VERSION < (3, 2):
                    try:
                        outer_query.add_subquery(inner_query, using)
                    except EmptyResultSet:
                        return {alias: None for alias in outer_query.annotation_select}
            else:
                outer_query = self
                self.select = ()
                self.default_cols = False
                self.extra = {}
            clear_query_ordering(outer_query, True)
            # outer_query.clear_ordering(force=True)
            outer_query.clear_limits()
            outer_query.select_for_update = False
            outer_query.select_related = False
            return outer_query

    else:

        def exists(self, limit=True):
            q = super().exists(limit=limit)
            q.add_annotation(Value("1"), "a")  # use str instead of int
            return q

        def get_aggregation_query(self, aggregate_exprs, using=None):
            """
            Return the dictionary with the values of the existing aggregations.
            """
            # ---------------------------------------
            # COPIED DIRECTLY FROM DJANGO 4.2
            aggregates = {}
            for alias, aggregate_expr in aggregate_exprs.items():
                self.check_alias(alias)
                aggregate = aggregate_expr.resolve_expression(
                    self, allow_joins=True, reuse=None, summarize=True
                )
                if not aggregate.contains_aggregate:
                    raise TypeError("%s is not an aggregate expression" % alias)
                aggregates[alias] = aggregate
            # Existing usage of aggregation can be determined by the presence of
            # selected aggregates but also by filters against aliased aggregates.
            _, having, qualify = self.where.split_having_qualify()
            has_existing_aggregation = (
                any(
                    getattr(annotation, "contains_aggregate", True)
                    for annotation in self.annotations.values()
                )
                or having
            )
            # Decide if we need to use a subquery.
            #
            # Existing aggregations would cause incorrect results as
            # get_aggregation() must produce just one result and thus must not use
            # GROUP BY.
            #
            # If the query has limit or distinct, or uses set operations, then
            # those operations must be done in a subquery so that the query
            # aggregates on the limit and/or distinct results instead of applying
            # the distinct and limit after the aggregation.
            if (
                isinstance(self.group_by, tuple)
                or self.is_sliced
                or has_existing_aggregation
                or qualify
                or self.distinct
                or self.combinator
            ):
                from django.db.models.sql.subqueries import AggregateQuery

                inner_query = self.clone()
                inner_query.subquery = True
                outer_query = AggregateQuery(self.model, inner_query)
                inner_query.select_for_update = False
                inner_query.select_related = False
                inner_query.set_annotation_mask(self.annotation_select)
                # Queries with distinct_fields need ordering and when a limit is
                # applied we must take the slice from the ordered query. Otherwise
                # no need for ordering.
                clear_query_ordering(inner_query, False)
                # inner_query.clear_ordering(force=False)
                if not inner_query.distinct:
                    # If the inner query uses default select and it has some
                    # aggregate annotations, then we must make sure the inner
                    # query is grouped by the main model's primary key. However,
                    # clearing the select clause can alter results if distinct is
                    # used.
                    if inner_query.default_cols and has_existing_aggregation:
                        inner_query.group_by = (
                            self.model._meta.pk.get_col(
                                inner_query.get_initial_alias()
                            ),
                        )
                    inner_query.default_cols = False
                    if not qualify:
                        # Mask existing annotations that are not referenced by
                        # aggregates to be pushed to the outer query unless
                        # filtering against window functions is involved as it
                        # requires complex realising.
                        annotation_mask = set()
                        for aggregate in aggregates.values():
                            annotation_mask |= aggregate.get_refs()
                        inner_query.set_annotation_mask(annotation_mask)

                # Add aggregates to the outer AggregateQuery. This requires making
                # sure all columns referenced by the aggregates are selected in the
                # inner query. It is achieved by retrieving all column references
                # by the aggregates, explicitly selecting them in the inner query,
                # and making sure the aggregates are repointed to them.
                col_refs = {}
                for alias, aggregate in aggregates.items():
                    replacements = {}
                    for col in self._gen_cols([aggregate], resolve_refs=False):
                        if not (col_ref := col_refs.get(col)):
                            index = len(col_refs) + 1
                            col_alias = f"__col{index}"
                            col_ref = Ref(col_alias, col)
                            col_refs[col] = col_ref
                            inner_query.annotations[col_alias] = col
                            inner_query.append_annotation_mask([col_alias])
                        replacements[col] = col_ref
                    outer_query.annotations[alias] = aggregate.replace_expressions(
                        replacements
                    )
                if (
                    inner_query.select == ()
                    and not inner_query.default_cols
                    and not inner_query.annotation_select_mask
                ):
                    # In case of Model.objects[0:3].count(), there would be no
                    # field selected in the inner query, yet we must use a subquery.
                    # So, make sure at least one field is selected.
                    inner_query.select = (
                        self.model._meta.pk.get_col(inner_query.get_initial_alias()),
                    )
            else:
                outer_query = self
                self.select = ()
                self.default_cols = False
                self.extra = {}
                if self.annotations:
                    # Inline reference to existing annotations and mask them as
                    # they are unnecessary given only the summarized aggregations
                    # are requested.
                    replacements = {
                        Ref(alias, annotation): annotation
                        for alias, annotation in self.annotations.items()
                    }
                    self.annotations = {
                        alias: aggregate.replace_expressions(replacements)
                        for alias, aggregate in aggregates.items()
                    }
                else:
                    self.annotations = aggregates
                self.set_annotation_mask(aggregates)

            # empty_set_result = [
            #     expression.empty_result_set_value
            #     for expression in outer_query.annotation_select.values()
            # ]
            # elide_empty = not any(result is NotImplemented for result in empty_set_result)
            clear_query_ordering(outer_query, True)
            # outer_query.clear_ordering(force=True)
            outer_query.clear_limits()
            outer_query.select_for_update = False
            outer_query.select_related = False
            return outer_query

    # @awaitable(get_aggregation)
    async def aget_aggregation(self, using, added_aggregate_names):
        if not added_aggregate_names:
            return {}
        outer_query = self.get_aggregation_query(added_aggregate_names, using=using)
        # empty_set_result = [
        #     expression.empty_result_set_value
        #     for expression in outer_query.annotation_select.values()
        # ]
        # if django.VERSION > (4, 0):
        #     elide_empty = not any(result is NotImplemented for result in empty_set_result)
        #     compiler = outer_query.get_compiler(using, elide_empty=elide_empty)
        # else:
        #     compiler = outer_query.get_compiler(using)
        db = self.connections_cls.get(using)
        q, params = outer_query.get_compiler(using).as_sql()
        result = await db.fetchone(q, params)
        return result
        # if result is None:
        #     result = empty_set_result
        # converters = compiler.get_converters(outer_query.annotation_select.values())
        # result = next(compiler.apply_converters((result,), converters))
        # return dict(zip(outer_query.annotation_select, result))


class AwaitableQuerySet(QuerySet):
    connections_cls = DatabaseConnections
    query_cls = AwaitableQuery
    query: query_cls
    collector_cls = AwaitableCollector

    def __init__(self, model, query=None, using=None, hints=None):
        super().__init__(
            model, query=query or self.query_cls(model), using=using, hints=hints
        )

    @property
    def database(self):
        return self.connections_cls.get(self.db)

    @property
    def support_pure_async(self):
        return self.database.support_pure_async

    def __aiter__(self):
        if not self.support_pure_async:
            try:
                return super().__aiter__()
            except AttributeError:
                # compat django 3.0
                async def generator():
                    await sync_to_async(self._fetch_all)()
                    for item in self._result_cache:
                        yield item

                return generator()

        async def generator():
            for item in await self.result():
                if self._iterable_class == ModelIterable:
                    yield self.fill_model_instance(item)
                # elif self._iterable_class == ValuesListIterable:
                #     yield tuple(item.values())
                # elif self._iterable_class == FlatValuesListIterable:
                #     v = tuple(item.values())
                #     if v:
                #         yield v[0]
                # elif self._iterable_class == NamedValuesListIterable:
                #     from collections import namedtuple
                #     yield namedtuple(self.model.__name__, field_names=list(item))(*item.values())
                else:
                    yield item

        return generator()

    def as_sql(self) -> Tuple[str, tuple]:
        return self.compiler.as_sql()

    @property
    def compiler(self):
        return self.query.get_compiler(self.db)

    def _convert_raw_values(self, values, query):
        names = [
            *query.extra_select,
            *query.values_select,
            *query.annotation_select,
        ]
        if not names:
            return values
        columns = {}
        for i, col in enumerate(query.select):
            # there might be multiple alias over one field, like fk and fk_id
            columns.setdefault(col.target.column, []).append(i)
        result = []
        for item in values:
            res = {}
            for name, value in item.items():
                indexes = columns.get(name)
                if indexes:
                    for index in indexes:
                        col: Col = query.select[index]
                        name = names[index]
                        for cvt in col.field.get_db_converters(self.conn):
                            value = cvt(value, col, self.conn)
                        res[name] = value
                else:
                    res[name] = value
            result.append(res)

        if issubclass(
            self._iterable_class, (ValuesListIterable, FlatValuesListIterable)
        ):
            list_result = []
            if self._iterable_class == NamedValuesListIterable:
                from collections import namedtuple

                t = namedtuple("Row", names)
                for item in result:
                    list_result.append(t(**item))
            else:
                for item in result:
                    value = []
                    for name in names:
                        value.append(item.get(name))
                    list_result.append(tuple(value))
            if self._iterable_class == FlatValuesListIterable:
                return tuple(v[0] for v in list_result)
            return tuple(list_result)

        return result

    def object(self, *args, **kwargs) -> Optional[dict]:
        return self.values(*args, **kwargs).result(one=True)

    @awaitable(object)
    async def object(self, *args, **kwargs) -> Optional[dict]:
        return await self.values(*args, **kwargs).result(one=True)

    def fill_model_instance(self, values: dict):
        obj_values = {}
        for field in self.meta.concrete_fields:
            val = values.get(field.name, values.get(field.column, Ellipsis))
            if val is Ellipsis:
                continue
            obj_values[field.column] = val
        pk = values.get("id", values.get("pk"))
        if pk is not None:
            obj_values.setdefault("pk", pk)
        obj = self.model(**obj_values)
        if getattr(obj, "id", None) is None:
            setattr(obj, "id", obj.pk)
        return obj

    def instance(self, *args, **kwargs) -> Optional[Model]:
        values = self.object(*args, **kwargs)
        if not values:
            return None
        return self.fill_model_instance(values)

    @awaitable(instance)
    async def instance(self, *args, **kwargs) -> Optional[Model]:
        values = await self.object(*args, **kwargs)
        if not values:
            return None
        return self.fill_model_instance(values)

    async def afirst(self):
        if not self.support_pure_async:
            return await sync_to_async(self.first)()
        return await (self if self.ordered else self.order_by("pk"))[:1].instance()

    async def alast(self):
        if not self.support_pure_async:
            return await sync_to_async(self.last)()
        return await (self.reverse() if self.ordered else self.order_by("pk"))[
            :1
        ].instance()

    def result(self, one: bool = False):
        result = list(self)
        if one:
            if result:
                return result[0]
            return None
        return result

    @awaitable(result)
    async def result(self, one: bool = False):
        # usage:
        # result = await model.objects.values(*fields, *exps).result()
        compiler = self.compiler
        try:
            q, params = compiler.as_sql()
        except exceptions.EmptyResultSet:
            return None if one else []
        db = self.database
        if one:
            val = await db.fetchone(q, params)
            if val is None:
                return None
            values = [val]
        else:
            values = await db.fetchall(q, params)
        # use the same query compiler to parse the result
        # because query compiler will setup query and attrs
        query = self.query
        if not query.select:
            # if no select values, result cannot be converted properly
            query = self._chain().values().query
        values = list(self._convert_raw_values(values, query=query))
        if one:
            return values[0]
        return values

    @property
    def meta(self) -> Options:
        return getattr(self.model, "_meta")

    async def acreate(self, **kwargs):
        if not self.support_pure_async:
            # compat django 3, not using super().acreate
            return await sync_to_async(self.create)(**kwargs)
        obj: Model = self.model(**kwargs)
        if self.meta.parents:
            db = self.database
            async with db.async_transaction(savepoint=False):
                await self._insert_obj_parents(obj)
                return await self._insert_obj(obj, raw=True)
        else:
            return await self._insert_obj(obj)

    async def _insert_obj_parents(self, obj: Model, cls=None):
        """Save all the parents of cls using values from self."""
        cls = cls or obj.__class__
        if getattr(cls, "_meta").proxy:
            cls = getattr(cls, "_meta").concrete_model
        meta = cls._meta

        for parent, field in meta.parents.items():
            # Make sure the link fields are synced between parent and self.
            parent_meta: Options = getattr(parent, "_meta")
            if (
                field
                and getattr(obj, parent_meta.pk.attname) is None
                and getattr(obj, field.attname) is not None
            ):
                setattr(obj, parent_meta.pk.attname, getattr(obj, field.attname))

            if parent_meta.parents:
                # recursively
                await self._insert_obj_parents(obj, cls=parent)

            await self._insert_obj(obj, cls=parent)

            if field:
                setattr(obj, field.attname, obj._get_pk_val(parent_meta))
                # Since we didn't have an instance of the parent handy set
                # attname directly, bypassing the descriptor. Invalidate
                # the related object cache, in case it's been accidentally
                # populated. A fresh instance will be re-built from the
                # database if necessary.
                if field.is_cached(obj):
                    field.delete_cached_value(obj)

    async def save_obj(self, obj: Model):
        if not self.support_pure_async:
            return await sync_to_async(obj.save_base)(raw=True, using=self.db)
        return await self._insert_obj(obj, raw=True)

    async def _insert_obj(self, obj: Model, cls=None, raw: bool = False):
        cls = cls or obj.__class__
        if getattr(cls, "_meta").proxy:
            cls = getattr(cls, "_meta").concrete_model
        meta: Options = cls._meta

        pk_val = getattr(obj, meta.pk.attname)
        fields = meta.local_concrete_fields
        returning_fields = meta.db_returning_fields

        if pk_val is None:
            pk_val = meta.pk.get_pk_value_on_save(obj)
            if inspect.isawaitable(pk_val):
                pk_val = await pk_val

            setattr(obj, meta.pk.attname, pk_val)

        if pk_val is None:
            # if pk val is still None after get_pk_value_on_save, then prepare the auto field
            fields = [f for f in fields if f is not meta.auto_field]

        results = await self._async_insert(
            [obj], fields=fields, cls=cls, returning_fields=returning_fields, raw=raw
        )
        if results:
            obj_value = results[0]
            for field, value in zip(returning_fields, obj_value):
                setattr(obj, field.attname, value)
        self._result_cache = None
        return obj

    async def _async_batched_insert(
        self,
        objs,
        fields,
        batch_size,
        on_conflict=None,
        update_fields=None,
        unique_fields=None,
    ):
        """
        Helper method for bulk_create() to insert objs one batch at a time.
        """
        connection = self.conn
        ops = connection.ops
        max_batch_size = max(ops.bulk_batch_size(fields, objs), 1)
        batch_size = min(batch_size, max_batch_size) if batch_size else max_batch_size
        inserted_rows = []
        bulk_return = connection.features.can_return_rows_from_bulk_insert
        for item in [objs[i : i + batch_size] for i in range(0, len(objs), batch_size)]:
            if bulk_return and on_conflict is None:
                inserted_rows.extend(
                    await self._async_insert(
                        item,
                        fields=fields,
                        using=self.db,
                        returning_fields=self.model._meta.db_returning_fields,
                    )
                )
            else:
                await self._async_insert(
                    item,
                    fields=fields,
                    using=self.db,
                    on_conflict=on_conflict,
                    update_fields=update_fields,
                    unique_fields=unique_fields,
                )
        return inserted_rows

    async def _async_insert(
        self,
        objs,
        fields,
        cls=None,
        returning_fields=None,
        raw=False,
        using=None,
        on_conflict=None,
        update_fields=None,
        unique_fields=None,
        ignore_conflicts=False,  # compat django 3
    ):
        self._for_write = True
        if using is None:
            using = self.db

        cls = cls or self.model
        if getattr(cls, "_meta").proxy:
            cls = getattr(cls, "_meta").concrete_model

        if django.VERSION > (4, 1):
            query = sql.InsertQuery(
                cls,
                on_conflict=on_conflict,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )
        else:
            query = sql.InsertQuery(cls, ignore_conflicts=ignore_conflicts)

        query.insert_values(fields, objs, raw=raw)
        db = self.connections_cls.get(using)
        compiler = query.get_compiler(using)
        conn = self.conn
        can_return = conn.features.can_return_columns_from_insert
        if can_return:
            if not returning_fields and self.meta.parents and db.is_sqlite:
                returning_fields = [self.meta.pk]
                # inherit models does not have returning_fields
                # which will make cursor.description = None for sqlite backend in encode/databases
                # causing errors, so we use [self.meta.pk] as default fallback
            compiler.returning_fields = returning_fields
        else:
            returning_fields = [self.meta.pk]

        values = []
        for q, params in compiler.as_sql():
            if can_return:
                rows = await db.fetchall(q, params)
            else:
                rows = [{self.meta.pk.column: await db.execute(q, params)}]
            for val in rows:
                val: dict
                tuple_values = []
                field_values = list(val.values())
                for i, f in enumerate(returning_fields):
                    name = f.column
                    if name in val:
                        field_value = val[name]
                    else:
                        # maybe the values is not correlated like sqlite async
                        try:
                            field_value = field_values[i]
                        except IndexError:
                            field_value = None
                    tuple_values.append(field_value)
                values.append(tuple(tuple_values))
        return values

    async def abulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
        no_transaction: bool = False,
    ):
        """
        Internal django implementation of bulk_create is too complicate to split into async code
        and since it's async, we can do a async joined task to create all objects
        """
        if not self.support_pure_async:
            return await sync_to_async(self.bulk_create)(
                objs,
                batch_size=batch_size,
                ignore_conflicts=ignore_conflicts,
                update_conflicts=update_conflicts,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )
        if not objs:
            return objs
        has_parent = None
        for parent in self.model._meta.get_parent_list():
            if parent._meta.concrete_model is not self.model._meta.concrete_model:
                has_parent = True

        if has_parent:
            # tasks = []
            # import asyncio
            for obj in objs:
                await self._insert_obj(obj)
            # try:
            #     await asyncio.gather(*tasks, return_exceptions=ignore_conflicts)
            #     # use await here to expect throw the exception to terminate the whole query
            # except Exception:
            #     for t in tasks:
            #         t.cancel()
            #     # if error raised here, it's because the force_raise_error flag or field.fail_silently=False
            #     # either of which we will directly cancel the unfinished tasks and raise the error
            #     raise
            return objs

        opts = self.model._meta
        if unique_fields:
            # Primary key is allowed in unique_fields.
            unique_fields = [
                self.model._meta.get_field(opts.pk.name if name == "pk" else name)
                for name in unique_fields
            ]
        if update_fields:
            update_fields = [self.model._meta.get_field(name) for name in update_fields]
        on_conflict = self._check_bulk_create_options(
            ignore_conflicts,
            update_conflicts,
            update_fields,
            unique_fields,
        )
        self._for_write = True
        fields = opts.concrete_fields
        objs = list(objs)
        self._prepare_for_bulk_create(objs)
        db = self.database

        async with (
            DummyContent() if no_transaction else db.async_transaction(savepoint=False)
        ):
            objs_with_pk, objs_without_pk = partition(lambda o: o.pk is None, objs)
            if objs_with_pk:
                returned_columns = await self._async_batched_insert(
                    objs_with_pk,
                    fields=fields,
                    batch_size=batch_size,
                    on_conflict=on_conflict,
                    update_fields=update_fields,
                    unique_fields=unique_fields,
                )

                for obj_with_pk, results in zip(objs_with_pk, returned_columns):
                    for result, field in zip(results, opts.db_returning_fields):
                        if field != opts.pk:
                            setattr(obj_with_pk, field.attname, result)

                for obj_with_pk in objs_with_pk:
                    obj_with_pk._state.adding = False
                    obj_with_pk._state.db = self.db

            if objs_without_pk:
                fields = [f for f in fields if not isinstance(f, AutoField)]
                returned_columns = await self._async_batched_insert(
                    objs_without_pk,
                    fields=fields,
                    batch_size=batch_size,
                    on_conflict=on_conflict,
                    update_fields=update_fields,
                    unique_fields=unique_fields,
                )
                connection = self.conn
                if (
                    connection.features.can_return_rows_from_bulk_insert
                    and on_conflict is None
                ):
                    assert len(returned_columns) == len(objs_without_pk)
                for obj_without_pk, results in zip(objs_without_pk, returned_columns):
                    for result, field in zip(results, opts.db_returning_fields):
                        setattr(obj_without_pk, field.attname, result)
                    obj_without_pk._state.adding = False
                    obj_without_pk._state.db = self.db

        return objs

    # @awaitable(count)
    async def acount(self) -> int:
        if not self.support_pure_async:
            return await sync_to_async(self.count)()
        query = self.query.clone()
        # query.clear_select_clause()
        # query.clear_select_fields()
        # query.clear_ordering()
        if django.VERSION < (4, 2):
            query.add_annotation(Count("*"), alias="__count", is_summary=True)
            r = await query.aget_aggregation(self.db, ["__count"]) or {}
        else:
            r = await query.aget_aggregation(self.db, {"__count": Count("*")}) or {}
        number = r.get("__count") or r.get("count") or r.get("COUNT(*)")
        if number is None and r:
            number = list(r.values())[0]
        # weird, don't know why now
        return number or 0

    async def aaggregate(self, *args, **kwargs):
        if not self.support_pure_async:
            return await sync_to_async(self.aggregate)(*args, **kwargs)
        # --------------------------------------------
        # COPIED DIRECTLY FROM DJANGO 4.1.5
        """
        Return a dictionary containing the calculations (aggregation)
        over the current queryset.

        If args is present the expression is passed as a kwarg using
        the Aggregate object's default alias.
        """
        if self.query.distinct_fields:
            raise NotImplementedError("aggregate() + distinct(fields) not implemented.")
        self._validate_values_are_expressions(
            (*args, *kwargs.values()), method_name="aggregate"
        )
        for arg in args:
            # The default_alias property raises TypeError if default_alias
            # can't be set automatically or AttributeError if it isn't an
            # attribute.
            try:
                arg.default_alias
            except (AttributeError, TypeError):
                raise TypeError("Complex aggregates require an alias")
            kwargs[arg.default_alias] = arg

        query = self.query.chain()
        if django.VERSION < (4, 2):
            for (alias, aggregate_expr) in kwargs.items():
                query.add_annotation(aggregate_expr, alias, is_summary=True)
                annotation = query.annotations[alias]
                if not annotation.contains_aggregate:
                    raise TypeError("%s is not an aggregate expression" % alias)
                for expr in annotation.get_source_expressions():
                    if (
                        expr.contains_aggregate
                        and isinstance(expr, Ref)
                        and expr.refs in kwargs
                    ):
                        name = expr.refs
                        raise exceptions.FieldError(
                            "Cannot compute %s('%s'): '%s' is an aggregate"
                            % (annotation.name, name, name)
                        )
        return await query.aget_aggregation(self.db, kwargs)

    async def aexists(self) -> bool:
        if not self.support_pure_async:
            return await sync_to_async(self.count)()
        query = self.query.exists(self.db)
        db = self.database
        try:
            q, params = query.get_compiler(self.db).as_sql()
        except exceptions.EmptyResultSet:
            return False
        # if django.VERSION > (4, 1):
        #     if params:
        #         params = (str(params[0]), *params[1:])
        return bool(await db.fetchone(q, params))

    async def aupdate(self, **kwargs):
        if not self.support_pure_async:
            return await sync_to_async(self.update)(**kwargs)
        # ---------------
        # LOGIC COPIED FROM DJANGO 4.1.5
        self._not_support_combined_queries("update")
        if self.query.is_sliced:
            raise TypeError("Cannot update a query once a slice has been taken.")
        self._for_write = True
        query = self.query.chain(sql.UpdateQuery)
        query.add_update_values(kwargs)
        # Inline annotations in order_by(), if possible.
        new_order_by = []
        for col in query.order_by:
            if annotation := query.annotations.get(col):
                if getattr(annotation, "contains_aggregate", False):
                    raise exceptions.FieldError(
                        f"Cannot update when ordering by an aggregate: {annotation}"
                    )
                new_order_by.append(annotation)
            else:
                new_order_by.append(col)
        query.order_by = tuple(new_order_by)
        query.annotations = {}
        # ----------------
        compiler = AwaitableSQLUpdateCompiler(query, self.conn, self.db)
        await compiler.async_execute_sql(
            # FIXME: this workaround is quite ugly
            case_update=any(isinstance(val, (Cast, Case)) for val in kwargs.values())
            # FIXME: ugly behaviour, for some reason that encode async db
            # got problem with datetime values, when querying / update, it needs to receive native datetime
            # but in bulk_update, it requires str, ...
        )
        self._result_cache = None
        # return rows

    async def aget_or_create(self, defaults=None, **kwargs):
        if not self.support_pure_async:
            return await sync_to_async(self.get_or_create)(defaults, **kwargs)
        # return await self.aget_or_create(defaults, **kwargs)
        self._for_write = True
        try:
            return await self.aget(**kwargs), False
        except self.model.DoesNotExist:
            params = self._extract_model_params(defaults, **kwargs)
            # Try to create an object using passed params.
            db = self.database
            try:
                async with db.async_transaction():
                    params = dict(resolve_callables(params))
                    return await self.acreate(**params), True
            except db.get_adaptor(True).get_integrity_errors():
                try:
                    return await self.aget(**kwargs), False
                except self.model.DoesNotExist:
                    pass
                raise

    @property
    def conn(self):
        from django.db import connections

        return connections[self.db]

    async def aget(self, *args, **kwargs):
        """
        Perform the query and return a single object matching the given
        keyword arguments.
        """
        if not self.support_pure_async:
            return await sync_to_async(self.get)(*args, **kwargs)
        if self.query.combinator and (args or kwargs):
            raise exceptions.NotSupportedError(
                "Calling QuerySet.get(...) with filters after %s() is not "
                "supported." % self.query.combinator
            )
        clone = self._chain() if self.query.combinator else self.filter(*args, **kwargs)
        if self.query.can_filter() and not self.query.distinct_fields:
            clone = clone.order_by()
        if (
            not clone.query.select_for_update
            or self.conn.features.supports_select_for_update_with_limit
        ):
            limit = 2
            clone.query.set_limits(high=limit)
        db = self.database
        compiler = clone.query.get_compiler(self.db)
        try:
            q, params = compiler.as_sql()
        except exceptions.EmptyResultSet:
            return None
        result = await db.fetchall(q, params)
        if not result:
            raise self.model.DoesNotExist(
                "%s matching query does not exist." % self.model._meta.object_name
            )
        if len(result) > 1:
            raise self.model.MultipleObjectsReturned("get() returned more than one")
        result = list(self._convert_raw_values(result, query=clone.values().query))
        obj_kwargs = result[0]
        return self.model(**obj_kwargs)

    async def aupdate_or_create(self, defaults=None, **kwargs):
        if not self.support_pure_async:
            return await sync_to_async(self.update_or_create)(defaults, **kwargs)
        # return await self.aupdate_or_create(defaults, **kwargs)
        defaults = defaults or {}
        self._for_write = True
        db = self.database
        async with db.async_transaction():
            # Lock the row so that a concurrent update is blocked until
            # update_or_create() has performed its save.
            # obj, created = await self.select_for_update().aget_or_create(defaults, **kwargs)
            obj, created = await self.aget_or_create(defaults, **kwargs)
            # fixme: SELECT FOR UPDATE IN ASYNC CONTEXT
            if created:
                return obj, created
            if obj.pk:
                params = dict(resolve_callables(defaults))
                await self.__class__(self.model).filter(pk=obj.pk).aupdate(**params)
        return obj, False

    async def abulk_update(
        self, objs, fields, batch_size=None, no_transaction: bool = False
    ):
        if not self.support_pure_async:
            return await sync_to_async(self.bulk_update)(
                objs, fields, batch_size=batch_size
            )
        if batch_size is not None and batch_size < 0:
            raise ValueError("Batch size must be a positive integer.")
        if not fields:
            raise ValueError("Field names must be given to bulk_update().")
        objs = tuple(objs)
        if any(obj.pk is None for obj in objs):
            raise ValueError("All bulk_update() objects must have a primary key set.")
        fields = [self.model._meta.get_field(name) for name in fields]
        if any(not f.concrete or f.many_to_many for f in fields):
            raise ValueError("bulk_update() can only be used with concrete fields.")
        if any(f.primary_key for f in fields):
            raise ValueError("bulk_update() cannot be used with primary key fields.")
        if not objs:
            return
        for obj in objs:
            obj._prepare_related_fields_for_save(
                operation_name="bulk_update", fields=fields
            )
        # PK is used twice in the resulting update query, once in the filter
        # and once in the WHEN. Each field will also have one CAST.
        self._for_write = True
        connection = self.conn
        max_batch_size = connection.ops.bulk_batch_size(["pk", "pk"] + fields, objs)
        batch_size = min(batch_size, max_batch_size) if batch_size else max_batch_size
        requires_casting = connection.features.requires_casted_case_in_updates
        batches = (objs[i : i + batch_size] for i in range(0, len(objs), batch_size))
        updates = []
        for batch_objs in batches:
            update_kwargs = {}
            for field in fields:
                when_statements = []
                for obj in batch_objs:
                    attr = getattr(obj, field.attname)
                    if not hasattr(attr, "resolve_expression"):
                        attr = Value(attr, output_field=field)
                    when_statements.append(When(pk=obj.pk, then=attr))
                case_statement = Case(*when_statements, output_field=field)
                if requires_casting:
                    case_statement = Cast(case_statement, output_field=field)
                update_kwargs[field.attname] = case_statement
            updates.append(([obj.pk for obj in batch_objs], update_kwargs))
        # rows_updated = 0
        queryset = self.using(self.db)
        db = self.database
        async with (
            DummyContent() if no_transaction else db.async_transaction(savepoint=False)
        ):
            for pks, update_kwargs in updates:
                await queryset.filter(pk__in=pks).aupdate(**update_kwargs)
        # return rows_updated

    async def adelete(self):
        if not self.support_pure_async:
            return await sync_to_async(self.delete)()
        # -------------------------------
        # COPIED FROM DJANGO 4.1.5
        # -------------------------------
        """Delete the records in the current QuerySet."""
        self._not_support_combined_queries("delete")
        if self.query.is_sliced:
            raise TypeError("Cannot use 'limit' or 'offset' with delete().")
        if self.query.distinct or self.query.distinct_fields:
            raise TypeError("Cannot call delete() after .distinct().")
        if self._fields is not None:
            raise TypeError("Cannot call delete() after .values() or .values_list()")

        del_query = self._chain()

        # The delete is actually 2 queries - one to find related objects,
        # and one to delete. Make sure that the discovery of related
        # objects is performed on the same database as the deletion.
        del_query._for_write = True

        # Disable non-supported fields.
        del_query.query.select_for_update = False
        del_query.query.select_related = False

        clear_query_ordering(del_query.query, True)

        kwargs = dict(using=del_query.db)
        if django.VERSION >= (4, 0):
            kwargs.update(origin=self)
        collector = self.collector_cls(**kwargs)
        if collector.can_fast_delete(del_query):
            await collector.acollect(del_query)
        else:
            pks = await self.values_list("pk", flat=True).result()
            if not pks:
                return True, 0
            await collector.acollect([self.model(pk=pk) for pk in pks])

        deleted, _rows_count = await collector.async_delete()
        # Clear the result cache, in case this QuerySet gets reused.
        self._result_cache = None
        return deleted, _rows_count


class AwaitableManager(Manager.from_queryset(AwaitableQuerySet)):
    pass

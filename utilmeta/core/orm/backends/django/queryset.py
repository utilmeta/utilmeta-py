import inspect
from django.db.models import QuerySet, Manager, Model, sql, AutoField
from django.db.models.options import Options
from django.db.models.query import ValuesListIterable, NamedValuesListIterable, \
    FlatValuesListIterable, ModelIterable
from django.core import exceptions
from django.db.models.utils import resolve_callables
from django.utils.functional import partition
from utilmeta.utils import awaitable
from ...databases import DatabaseConnections
from .expressions import Count, Ref, Value, Case, When, Cast, Col
from . import exceptions
import django
from .deletion import AwaitableCollector
from typing import Optional, Tuple
from .query import AwaitableQuery, AwaitableSQLUpdateCompiler


class DummyContent:
    def __enter__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class AwaitableQuerySet(QuerySet):
    connections_cls = DatabaseConnections
    query_cls = AwaitableQuery
    query: query_cls
    collector_cls = AwaitableCollector

    def __init__(self, model, query=None, using=None, hints=None):
        super().__init__(model, query=query or self.query_cls(model), using=using, hints=hints)

    def __aiter__(self):
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

        if issubclass(self._iterable_class, (ValuesListIterable, FlatValuesListIterable)):
            list_result = []
            if self._iterable_class == NamedValuesListIterable:
                from collections import namedtuple
                t = namedtuple('Row', names)
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
        pk = values.get('id', values.get('pk'))
        if pk is not None:
            obj_values.setdefault('pk', pk)
        obj = self.model(**obj_values)
        if getattr(obj, 'id', None) is None:
            setattr(obj, 'id', obj.pk)
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
        return await (self if self.ordered else self.order_by('pk'))[:1].instance()

    async def alast(self):
        return await (self.reverse() if self.ordered else self.order_by('pk'))[:1].instance()

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
        db = self.connections_cls.get(self.db)
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
        return getattr(self.model, '_meta')

    async def acreate(self, **kwargs):
        obj: Model = self.model(**kwargs)
        if self.meta.parents:
            db = self.connections_cls.get(self.db)
            async with db.async_transaction(savepoint=False):
                await self._insert_obj_parents(obj)
                print('PARENTS:', obj.pk)
                return await self._insert_obj(obj, raw=True)
        else:
            return await self._insert_obj(obj)

    async def _insert_obj_parents(self, obj: Model, cls=None):
        """Save all the parents of cls using values from self."""
        cls = cls or obj.__class__
        if getattr(cls, '_meta').proxy:
            cls = getattr(cls, '_meta').concrete_model
        meta = cls._meta

        for parent, field in meta.parents.items():
            # Make sure the link fields are synced between parent and self.
            parent_meta: Options = getattr(parent, '_meta')
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

    async def _insert_obj(self, obj: Model, cls=None, raw: bool = False):
        cls = cls or obj.__class__
        if getattr(cls, '_meta').proxy:
            cls = getattr(cls, '_meta').concrete_model
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
            [obj],
            fields=fields, cls=cls,
            returning_fields=returning_fields,
            raw=raw
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
        ignore_conflicts=False  # compat django 3
    ):
        self._for_write = True
        if using is None:
            using = self.db

        cls = cls or self.model
        if getattr(cls, '_meta').proxy:
            cls = getattr(cls, '_meta').concrete_model

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
        compiler.returning_fields = returning_fields or [self.meta.pk]
        # inherit models does not have returning_fields
        # which will make cursor.description = None for sqlite backend in encode/databases
        # causing errors, so we use [self.meta.pk] as default fallback
        values = []
        for q, params in compiler.as_sql():
            for val in await db.fetchall(q, params):
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
        no_transaction: bool = False
    ):
        """
        Internal django implementation of bulk_create is too complicate to split into async code
        and since it's async, we can do a async joined task to create all objects
        """
        if not objs:
            return objs
        has_parent = None
        for parent in self.model._meta.get_parent_list():
            if parent._meta.concrete_model is not self.model._meta.concrete_model:
                has_parent = True

        if has_parent:
            tasks = []
            import asyncio
            for obj in objs:
                tasks.append(asyncio.create_task(self._insert_obj(obj)))
            try:
                await asyncio.gather(*tasks, return_exceptions=ignore_conflicts)
                # use await here to expect throw the exception to terminate the whole query
            except Exception:
                for t in tasks:
                    t.cancel()
                # if error raised here, it's because the force_raise_error flag or field.fail_silently=False
                # either of which we will directly cancel the unfinished tasks and raise the error
                raise
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
        db = self.connections_cls.get(self.db)

        async with (DummyContent() if no_transaction else db.async_transaction(savepoint=False)):
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
        query = self.query.clone()
        # query.clear_select_clause()
        # query.clear_select_fields()
        # query.clear_ordering()
        if django.VERSION < (4, 2):
            query.add_annotation(Count('*'), alias='__count', is_summary=True)
            r = await query.aget_aggregation(self.db, ['__count']) or {}
        else:
            r = await query.aget_aggregation(self.db, {"__count": Count("*")}) or {}
        number = r.get('__count') or r.get('count') or 0
        # weird, don't know why now
        return number

    async def aaggregate(self, *args, **kwargs):
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
        query = self.query.exists(self.db)
        db = self.connections_cls.get(self.db)
        try:
            q, params = query.get_compiler(self.db).as_sql()
        except exceptions.EmptyResultSet:
            return False
        # if django.VERSION > (4, 1):
        #     if params:
        #         params = (str(params[0]), *params[1:])
        return bool(await db.fetchone(q, params))

    async def aupdate(self, **kwargs):
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
        # return await self.aget_or_create(defaults, **kwargs)
        self._for_write = True
        try:
            return await self.aget(**kwargs), False
        except self.model.DoesNotExist:
            params = self._extract_model_params(defaults, **kwargs)
            # Try to create an object using passed params.
            db = self.connections_cls.get(self.db)
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
        db = self.connections_cls.get(self.db)
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
        # return await self.aupdate_or_create(defaults, **kwargs)
        defaults = defaults or {}
        self._for_write = True
        db = self.connections_cls.get(self.db)
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

    async def abulk_update(self, objs, fields, batch_size=None, no_transaction: bool = False):
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
        batches = (objs[i: i + batch_size] for i in range(0, len(objs), batch_size))
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
        db = self.connections_cls.get(self.db)
        async with (DummyContent() if no_transaction else db.async_transaction(savepoint=False)):
            for pks, update_kwargs in updates:
                await queryset.filter(pk__in=pks).aupdate(**update_kwargs)
        # return rows_updated

    async def adelete(self):
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
        del_query.query.clear_ordering(force=True)

        collector = self.collector_cls(using=del_query.db, origin=self)
        if collector.can_fast_delete(del_query):
            await collector.acollect(del_query)
        else:
            pks = await self.values_list('pk', flat=True).result()
            if not pks:
                return True, 0
            await collector.acollect([self.model(pk=pk) for pk in pks])

        deleted, _rows_count = await collector.async_delete()
        # Clear the result cache, in case this QuerySet gets reused.
        self._result_cache = None
        return deleted, _rows_count


class AwaitableManager(Manager.from_queryset(AwaitableQuerySet)): pass

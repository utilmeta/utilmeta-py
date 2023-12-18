import inspect

import django
from django.db.models.deletion import Collector, Counter
from collections import defaultdict
from itertools import chain
from django.db.models.deletion import get_candidate_relations_to_delete, \
    DO_NOTHING, ProtectedError, RestrictedError
from django.db.models import QuerySet, sql, signals
from django.db import models
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from ...databases import DatabaseConnections
from functools import reduce
from operator import attrgetter, or_


class AwaitableCollector(Collector):
    connections_cls = DatabaseConnections

    @classmethod
    async def delete_single(cls, qs: QuerySet, db: DatabaseConnections.database_cls):
        query = qs.query.clone()
        query.__class__ = sql.DeleteQuery
        q, params = query.get_compiler(qs.db).as_sql()
        await db.execute(q, params)
        # cursor = query.get_compiler(self.using).execute_sql(CURSOR)
        # if cursor:
        #     with cursor:
        #         return cursor.rowcount
        return 0

    @classmethod
    async def update_batch(cls, model, pk_list, values, db: DatabaseConnections.database_cls):
        query = sql.UpdateQuery(model)
        query.add_update_values(values)
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            query.clear_where()
            query.add_filter(
                "pk__in", pk_list[offset: offset + GET_ITERATOR_CHUNK_SIZE]
            )
            q, params = query.get_compiler(db.alias).as_sql()
            await db.execute(q, params)

    @classmethod
    async def delete_batch(cls, model, pk_list, db: DatabaseConnections.database_cls):
        """
        Set up and execute delete queries for all the objects in pk_list.

        More than one physical query may be executed if there are a
        lot of values in pk_list.
        """
        query = sql.DeleteQuery(model)
        # number of objects deleted
        num_deleted = 0
        field = query.get_meta().pk
        for offset in range(0, len(pk_list), GET_ITERATOR_CHUNK_SIZE):
            query.clear_where()
            query.add_filter(
                f"{field.attname}__in",
                pk_list[offset: offset + GET_ITERATOR_CHUNK_SIZE],
            )
            where = query.where
            table = query.get_meta().db_table
            query.alias_map = {table: query.alias_map[table]}
            query.where = where
            q, params = query.get_compiler(db.alias).as_sql()
            await db.execute(q, params)
        return num_deleted

    async def async_delete(self):
        # ---------------------------------------------
        # COPIED FROM DJANGO 4.1.5
        # ---------------------------------------------
        # sort instance collections
        for model, instances in self.data.items():
            self.data[model] = sorted(instances, key=attrgetter("pk"))

        # if possible, bring the models in an order suitable for databases that
        # don't support transactions or cannot defer constraint checks until the
        # end of a transaction.
        self.sort()
        # number of objects deleted for each model label
        deleted_counter = Counter()

        db = self.connections_cls.get(self.using)
        await db.connect()

        # Optimize for the case with a single obj and no dependencies
        if len(self.data) == 1:
            model = list(self.data.keys())[0]
            instances = list(self.data.values())[0]
            if len(instances) == 1:
                instance = list(instances)[0]
                if self.can_fast_delete(instance):
                    async with db.async_transaction():
                        # with transaction.mark_for_rollback_on_error(self.using):
                        count = await self.delete_batch(model, pk_list=[instance.pk], db=db)
                        setattr(instance, model._meta.pk.attname, None)
                        return count, {model._meta.label: count}

        async with db.async_transaction(savepoint=False):
            # send pre_delete signals
            for model, obj in self.instances_with_model():
                if not model._meta.auto_created:
                    signals.pre_delete.send(
                        sender=model,
                        instance=obj,
                        using=self.using,
                        origin=self.origin,
                    )

            # fast deletes
            for qs in self.fast_deletes:
                count = await self.delete_single(qs, db)
                if count:
                    deleted_counter[qs.model._meta.label] += count

            # update fields
            if django.VERSION >= (4, 2):
                for (field, value), instances_list in self.field_updates.items():
                    updates = []
                    objs = []
                    for instances in instances_list:
                        if (
                            isinstance(instances, models.QuerySet)
                            and instances._result_cache is None
                        ):
                            updates.append(instances)
                        else:
                            objs.extend(instances)
                    if updates:
                        combined_updates = reduce(or_, updates)
                        from .queryset import AwaitableQuerySet
                        if not isinstance(combined_updates, AwaitableQuerySet):
                            combined_updates = AwaitableQuerySet(
                                model=combined_updates.model,
                                query=combined_updates.query,
                                using=combined_updates.db
                            )
                        await combined_updates.aupdate(**{field.name: value})
                    if objs:
                        model = objs[0].__class__
                        # query = sql.UpdateQuery(model)
                        await self.update_batch(
                            model, pk_list=[obj.pk for obj in objs],
                            values={field.name: value}, db=db
                        )
            else:
                for model, instances_for_fieldvalues in self.field_updates.items():
                    for (field, value), instances in instances_for_fieldvalues.items():
                        await self.update_batch(
                            model, pk_list=[obj.pk for obj in instances],
                            values={field.name: value}, db=db
                        )

            # reverse instance collections
            for instances in self.data.values():
                instances.reverse()

            # delete instances
            for model, instances in self.data.items():
                pk_list = [obj.pk for obj in instances]
                count = await self.delete_batch(model, pk_list=pk_list, db=db)
                if count:
                    deleted_counter[model._meta.label] += count

                if not model._meta.auto_created:
                    for obj in instances:
                        signals.post_delete.send(
                            sender=model,
                            instance=obj,
                            using=self.using,
                            origin=self.origin,
                        )

        if django.VERSION < (4, 2):
            # update collected instances
            for instances_for_fieldvalues in self.field_updates.values():
                for (field, value), instances in instances_for_fieldvalues.items():
                    for obj in instances:
                        setattr(obj, field.attname, value)

        for model, instances in self.data.items():
            for instance in instances:
                setattr(instance, model._meta.pk.attname, None)
        return sum(deleted_counter.values()), dict(deleted_counter)

    def related_objects(self, related_model, related_fields, objs):
        """
        Get a QuerySet of the related model to objs via related fields.
        """
        from django.db.models import query_utils
        predicate = query_utils.Q.create(
            [(f"{related_field.name}__in", objs) for related_field in related_fields],
            connector=query_utils.Q.OR,
        )
        from .queryset import AwaitableQuerySet
        return AwaitableQuerySet(model=related_model).using(self.using).filter(predicate)

    async def aadd(self, objs, source=None, nullable=False, reverse_dependency=False):
        """
        Add 'objs' to the collection of objects to be deleted.  If the call is
        the result of a cascade, 'source' should be the model that caused it,
        and 'nullable' should be set to True if the relation can be null.

        Return a list of all objects that were not already collected.
        """
        from .queryset import AwaitableQuerySet
        new_objs = []
        if isinstance(objs, AwaitableQuerySet):
            if not await objs.aexists():
                return []
            model = objs.model
        else:
            if not objs:
                return []
            model = objs[0].__class__
        instances = self.data[model]
        if isinstance(objs, AwaitableQuerySet):
            async for obj in objs:
                if isinstance(obj, dict):
                    obj = model(**obj)
                if obj not in instances:
                    new_objs.append(obj)
        else:
            for obj in objs:
                if obj not in instances:
                    new_objs.append(obj)
        instances.update(new_objs)
        # Nullable relationships can be ignored -- they are nulled out before
        # deleting, and therefore do not affect the order in which objects have
        # to be deleted.
        if source is not None and not nullable:
            self.add_dependency(source, model, reverse_dependency=reverse_dependency)
        return new_objs

    async def acollect(
        self,
        objs,
        source=None,
        nullable=False,
        collect_related=True,
        source_attr=None,
        reverse_dependency=False,
        keep_parents=False,
        fail_on_restricted=True,
    ):
        """
        Add 'objs' to the collection of objects to be deleted as well as all
        parent instances.  'objs' must be a homogeneous iterable collection of
        model instances (e.g. a QuerySet).  If 'collect_related' is True,
        related objects will be handled by their respective on_delete handler.

        If the call is the result of a cascade, 'source' should be the model
        that caused it and 'nullable' should be set to True, if the relation
        can be null.

        If 'reverse_dependency' is True, 'source' will be deleted before the
        current model, rather than after. (Needed for cascading to parent
        models, the one case in which the cascade follows the forwards
        direction of an FK rather than the reverse direction.)

        If 'keep_parents' is True, data of parent model's will be not deleted.

        If 'fail_on_restricted' is False, error won't be raised even if it's
        prohibited to delete such objects due to RESTRICT, that defers
        restricted object checking in recursive calls where the top-level call
        may need to collect more objects to determine whether restricted ones
        can be deleted.
        """
        if self.can_fast_delete(objs):
            self.fast_deletes.append(objs)
            return

        from .queryset import AwaitableQuerySet
        if isinstance(objs, QuerySet):
            model = objs.model
            if not isinstance(objs, AwaitableQuerySet):
                objs = AwaitableQuerySet(model=model, query=objs.query, using=objs.db)
        else:
            model = objs[0].__class__

        new_objs = await self.aadd(
            objs, source, nullable, reverse_dependency=reverse_dependency
        )
        if not new_objs:
            return

        if not keep_parents:
            # Recursively collect concrete model's parent models, but not their
            # related objects. These will be found by meta.get_fields()
            concrete_model = model._meta.concrete_model
            for ptr in concrete_model._meta.parents.values():
                if ptr:
                    parent_objs = [getattr(obj, ptr.name) for obj in new_objs]
                    await self.acollect(
                        parent_objs,
                        source=model,
                        source_attr=ptr.remote_field.related_name,
                        collect_related=False,
                        reverse_dependency=True,
                        fail_on_restricted=False,
                    )
        if not collect_related:
            return

        parents = set(model._meta.get_parent_list()) if keep_parents else set()
        model_fast_deletes = defaultdict(list)
        protected_objects = defaultdict(list)
        for related in get_candidate_relations_to_delete(model._meta):
            # Preserve parent reverse relationships if keep_parents=True.
            if keep_parents and related.model in parents:
                continue
            field = related.field
            on_delete = field.remote_field.on_delete
            if on_delete == DO_NOTHING:
                continue
            related_model = related.related_model
            if self.can_fast_delete(related_model, from_field=field):
                model_fast_deletes[related_model].append(field)
                continue
            batches = self.get_del_batches(new_objs, [field])
            for batch in batches:
                sub_objs = self.related_objects(related_model, [field], batch)
                # Non-referenced fields can be deferred if no signal receivers
                # are connected for the related model as they'll never be
                # exposed to the user. Skip field deferring when some
                # relationships are select_related as interactions between both
                # features are hard to get right. This should only happen in
                # the rare cases where .related_objects is overridden anyway.
                if not (
                    sub_objs.query.select_related
                    or self._has_signal_listeners(related_model)
                ):
                    referenced_fields = set(
                        chain.from_iterable(
                            (rf.attname for rf in rel.field.foreign_related_fields)
                            for rel in get_candidate_relations_to_delete(
                                related_model._meta
                            )
                        )
                    )
                    sub_objs = sub_objs.only(*tuple(referenced_fields))
                if getattr(on_delete, "lazy_sub_objs", False) or await sub_objs.aexists():
                    try:
                        r = on_delete(self, field, sub_objs, self.using)
                        if inspect.isawaitable(r):
                            await r
                    except ProtectedError as error:
                        key = "'%s.%s'" % (field.model.__name__, field.name)
                        protected_objects[key] += error.protected_objects
        if protected_objects:
            raise ProtectedError(
                "Cannot delete some instances of model %r because they are "
                "referenced through protected foreign keys: %s."
                % (
                    model.__name__,
                    ", ".join(protected_objects),
                ),
                set(chain.from_iterable(protected_objects.values())),
            )

        for related_model, related_fields in model_fast_deletes.items():
            batches = self.get_del_batches(new_objs, related_fields)
            for batch in batches:
                sub_objs = self.related_objects(related_model, related_fields, batch)
                self.fast_deletes.append(sub_objs)

        for field in model._meta.private_fields:
            if hasattr(field, "bulk_related_objects"):
                # It's something like generic foreign key.
                sub_objs = field.bulk_related_objects(new_objs, self.using)
                await self.acollect(
                    sub_objs, source=model, nullable=True, fail_on_restricted=False
                )

        if fail_on_restricted:
            # Raise an error if collected restricted objects (RESTRICT) aren't
            # candidates for deletion also collected via CASCADE.
            for related_model, instances in self.data.items():
                self.clear_restricted_objects_from_set(related_model, instances)
            for qs in self.fast_deletes:
                self.clear_restricted_objects_from_queryset(qs.model, qs)
            if self.restricted_objects.values():
                restricted_objects = defaultdict(list)
                for related_model, fields in self.restricted_objects.items():
                    for field, objs in fields.items():
                        if objs:
                            key = "'%s.%s'" % (related_model.__name__, field.name)
                            restricted_objects[key] += objs
                if restricted_objects:
                    raise RestrictedError(
                        "Cannot delete some instances of model %r because "
                        "they are referenced through restricted foreign keys: "
                        "%s."
                        % (
                            model.__name__,
                            ", ".join(restricted_objects),
                        ),
                        set(chain.from_iterable(restricted_objects.values())),
                    )

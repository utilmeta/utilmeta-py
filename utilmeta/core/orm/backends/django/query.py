import decimal

from django.db.models import sql, Case
from django.db.models.sql.compiler import SQLUpdateCompiler, SQLCompiler
from ...databases import DatabaseConnections
from .expressions import Ref, Value
import django
from datetime import date, time, timedelta, datetime


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
                query,
                connection=connections[self.using],
                using=self.using
            )
            await compiler.async_execute_sql(case_update)

    @classmethod
    def _parse_update_param(cls, param):
        if isinstance(param, (datetime, date, time)):
            return str(param)
        elif isinstance(param, timedelta):
            return param.total_seconds()
        elif isinstance(param, (list, tuple, set)):
            return '{%s}' % ','.join([str(p) for p in param])
        return param


class AwaitableQuery(sql.Query):
    connections_cls = DatabaseConnections

    # adapt backend
    if django.VERSION < (4, 2):
        def exists(self, using, limit=True):
            q = super().exists(using, limit=limit)
            q.add_annotation(Value("1"), "a")       # use str instead of int
            return q

        def get_aggregation_query(self, added_aggregate_names):
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
                            self.model._meta.pk.get_col(inner_query.get_initial_alias()),
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
                        expression, col_cnt = inner_query.rewrite_cols(expression, col_cnt)
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
            q.add_annotation(Value("1"), "a")       # use str instead of int
            return q

        def get_aggregation_query(self, aggregate_exprs):
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
                            self.model._meta.pk.get_col(inner_query.get_initial_alias()),
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
        outer_query = self.get_aggregation_query(added_aggregate_names)
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

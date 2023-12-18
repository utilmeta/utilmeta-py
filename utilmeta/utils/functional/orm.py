import re
from ..constant import PK, ID, SEG
from typing import List, Set, Any, Dict, Tuple
from functools import wraps

__all__ = [
    'add_field_id',
    'del_field_id',
    'merge_multiple',
    'validate_query_alias',
    'get_sql_info',
    'print_queries',
]


def validate_query_alias(name: str):
    if name.endswith('_'):
        # because this will disrupt the lookup syntax
        raise ValueError(f'Invalid query alias: {repr(name)}, cannot endswith "_"')
    if '--' in name:
        raise ValueError(f'Invalid query alias: {repr(name)}, cannot contains SQL comments "--"')
    invalids = {'"', "'", ';', '[', ']', '`', ' ', '%', '\t', '\n', '\r', '\x0b', '\x0c'}
    cross = set(invalids).intersection(name)
    if cross:
        raise ValueError(f'Invalid query alias: {repr(name)}, contains invalid chars: {cross}')
    return


# def clean_pks(pk_fields: Set[str], values: List[dict]):
#     if pk_fields != {PK}:
#         for val in values:
#             if PK not in val:
#                 continue
#             pk = val[PK] if PK in pk_fields else val.pop(PK)
#             for f in pk_fields:
#                 val.setdefault(f, pk)
#     return values


def print_queries(alias='default'):
    def deco(f, a=alias):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from django.db import connections
            import time
            start = time.time()
            connection = connections[a]
            qs = len(connection.queries)
            r = f(*args, **kwargs)
            end = time.time()
            t = round(end - start, 3)
            qc = len(connection.queries) - qs
            print(f'function {f.__name__} cost {t} s with {qc} queries')
            return r
        return wrapper

    if callable(alias):
        return deco(alias, 'default')

    return deco


def merge_multiple_tuple(data: List[tuple], fields: List[str], key=PK, depth: int = 1) -> List[tuple]:
    if len(data) < 2:
        return data
    orders = []
    index = fields.index(key)
    values: Dict[str, List[tuple]] = {}
    for d in data:
        if d[index] is None:
            continue
        vk: str = d[index]
        if vk not in orders:
            orders.append(vk)
        if vk in values:
            values[vk].append(d)
        else:
            values[vk] = [d]
    if len(values) == len(data):
        return data

    result = [tuple()] * len(values)
    merged_fields = set()
    for i, f in enumerate(fields):
        f: str
        if SEG not in f:
            continue
        lks = f.split(SEG)
        if depth > 1 and not f.startswith(key + SEG):
            continue
        if len(lks) <= depth:
            continue
        for lk in [SEG.join(lks[:i]) for i in range(depth, len(lks))]:
            if lk in fields:
                merged_fields.update({lk})
                break

    for kv, val in values.items():
        item: List[Any] = [None] * len(fields)
        item[index] = kv

        for v in val:
            for i, t in enumerate(v):
                k = fields[i]
                if k in merged_fields:
                    continue
                if depth > 1 and not k.startswith(key + SEG):
                    continue
                if item[i] is None:
                    item[i] = t
                    continue
                p = item[i]
                if t is None:
                    continue
                elif isinstance(p, tuple):
                    if t not in p:
                        p = p + (t,)
                elif p != t:
                    p = (p, t)
                item[i] = p

        for f in merged_fields:
            value = merge_multiple_tuple(val, fields=fields, key=f, depth=depth + 1)
            for i, k in enumerate(fields):
                if k.startswith(f + SEG):
                    item[i] = value[0][i] if len(value) == 1 else [v[i] for v in value]

        for i, v in enumerate(item):
            if isinstance(v, tuple):
                item[i] = list(v)

        result[orders.index(kv)] = tuple(item)
    return result


def merge_multiple(data: List[dict], key=PK, rel_key=None, depth: int = 1) -> List[dict]:
    if not key or len(data) < 2:
        return data

    orders = []
    values: Dict[str, list] = {}
    for d in data:
        if d.get(key) is None:
            continue
        vk: str = d[key]
        if vk not in orders:
            orders.append(vk)
        if vk in values:
            values[vk].append(d)
        else:
            values[vk] = [d]

    if not values or len(values) == len(data):
        return data

    result = [{}] * len(values)
    fields = tuple(data[0].keys())
    merged_fields = set()
    for f in fields:
        f: str
        if SEG not in f:
            continue
        lks = f.split(SEG)
        if depth > 1 and not f.startswith(key + SEG):
            continue
        if len(lks) <= depth:
            continue
        for lk in [SEG.join(lks[:i]) for i in range(depth, len(lks))]:
            if lk in fields:
                merged_fields.update({lk})
                break
    # print('merge:', depth, merge_fields)

    for kv, val in values.items():
        merged_item = {}
        for f in merged_fields:
            value = merge_multiple(val, key=f, depth=depth+1)
            if not value:
                merged_item[f] = None
                continue
            v0 = {k: v for k, v in value[0].items() if k.startswith(f + SEG)}
            if len(value) == 1:
                merged_item.update(v0)
            else:
                merged_item.update({k: [v[k] for v in value] for k in v0.keys()})

        item = {key: kv}
        for v in val:
            v: dict
            if rel_key:
                if rel_key not in v:
                    continue
                if rel_key in item:
                    item_val = item[rel_key]
                    rel_val = v[rel_key]
                    if isinstance(item_val, tuple):
                        if rel_val in item_val:
                            continue
                    elif rel_val == item_val:
                        continue

            for k, t in v.items():
                k: str
                if k == key or k in merged_item:
                    continue
                if depth > 1 and not k.startswith(key + SEG):
                    continue
                if k not in item:
                    item[k] = t
                    continue
                i = item[k]

                if rel_key:
                    if isinstance(i, tuple):
                        i = i + (t,)
                    else:
                        i = (i, t)
                else:
                    if t is None:
                        continue
                    elif i is None:
                        i = t
                    elif isinstance(i, tuple):
                        if t not in i:
                            i = i + (t,)
                    elif i != t:
                        i = (i, t)

                item[k] = i

        item.update(merged_item)

        for k in list(item.keys()):
            if isinstance(item[k], tuple):
                item[k] = list(item[k])

        result[orders.index(kv)] = item
    return result


def del_field_id(field: str) -> str:
    if not field:
        raise ValueError(f'Empty field: {field}')
    return field if field[-3:] != '_id' else field[:-3]


def add_field_id(field: str) -> str:
    if not field:
        raise ValueError(f'Empty field: {field}')
    if field == PK or field == ID:
        return field
    return field if field[-3:] == '_id' else field + '_id'


def get_sql_info(sql_str: str, table_min_length: int = 2, str_parse: bool = True) -> Tuple[str, List[str]]:
    if not sql_str:
        return '', []

    sql_str = re.sub(re.compile('in \\((.+?)\\)', re.I | re.S), 'IN (0)', sql_str)
    sql_str = re.sub(re.compile("'(.+?)'", re.I | re.S), "''", sql_str)  # avoid string interfere the string parse
    # replace large in sector to improve performance
    if str_parse:
        # patterns = [' FROM "%s"', ' JOIN "%s"', ' INTO "%s"', 'UPDATE "%s" ']
        # types = ['select', 'update', 'insert', 'delete']
        types_map = {
            'select': [' from ', ' join '],
            'update': ['update '],
            'delete': [' from '],
            'insert': ['insert into ']
        }
        opt = sql_str.split()[0]
        tokens = types_map.get(opt.lower())
        if not tokens:
            return '', []
        tables = []
        for token in tokens:
            b, *s = (sql_str.split(token) if token in sql_str else sql_str.split(token.upper()))
            for statement in s:
                tb: str = statement.strip().split()[0].strip('"')
                if table_min_length and len(tb) <= table_min_length:
                    continue
                if not tb.isidentifier():
                    continue
                tables.append(tb)
        return opt.upper(), tables

    import sqlparse
    from sqlparse.sql import Identifier
    sql = sqlparse.parse(sql_str)
    if not sql:
        return '', []
    tables = []
    preserves = ['CONFLICT', 'subquery']
    for statement in sql:
        for token in statement.tokens:
            if isinstance(token, Identifier):
                if token.get_name() and not token.get_ordering():
                    name = token.get_name()
                    if table_min_length and len(name) <= table_min_length:
                        continue
                    if str(name).startswith(SEG):
                        # maybe __count
                        continue
                    if name in preserves:
                        continue
                    tables.append(name)
    return sql[0].get_type(), tables

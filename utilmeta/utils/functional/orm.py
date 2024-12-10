import re
from ..constant import PK, ID, SEG
from typing import List, Set, Any, Dict, Tuple
from functools import wraps

__all__ = [
    "get_sql_info",
    "print_queries",
]


def print_queries(alias="default"):
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
            print(f"function {f.__name__} cost {t} s with {qc} queries")
            return r

        return wrapper

    if callable(alias):
        return deco(alias, "default")

    return deco


def get_sql_info(
    sql_str: str, table_min_length: int = 2, str_parse: bool = True
) -> Tuple[str, List[str]]:
    if not sql_str:
        return "", []

    sql_str = re.sub(re.compile("in \\((.+?)\\)", re.I | re.S), "IN (0)", sql_str)
    sql_str = re.sub(
        re.compile("'(.+?)'", re.I | re.S), "''", sql_str
    )  # avoid string interfere the string parse
    # replace large in sector to improve performance
    if str_parse:
        # patterns = [' FROM "%s"', ' JOIN "%s"', ' INTO "%s"', 'UPDATE "%s" ']
        # types = ['select', 'update', 'insert', 'delete']
        types_map = {
            "select": [" from ", " join "],
            "update": ["update "],
            "delete": [" from "],
            "insert": ["insert into "],
        }
        opt = sql_str.split()[0]
        tokens = types_map.get(opt.lower())
        if not tokens:
            return "", []
        tables = []
        for token in tokens:
            b, *s = (
                sql_str.split(token)
                if token in sql_str
                else sql_str.split(token.upper())
            )
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
        return "", []
    tables = []
    preserves = ["CONFLICT", "subquery"]
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

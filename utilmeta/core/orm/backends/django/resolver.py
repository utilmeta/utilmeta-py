import hashlib
import math
import re
from utilmeta.utils import UTF_8, ignore_errors, iterable, parse_list
from django.db.models.expressions import BaseExpression
from functools import partial, wraps
from . import expressions as exp

__all__ = ['resolve_expression', 'Lookup', 'expressions_resolver', 'std_dev', 'variance']

list_parser = partial(parse_list, merge=True, distinct_merge=False)


def avg(values):
    values = list_parser(values, merge_type=int)
    return float(sum(values) / len(values)) if values else None


def variance(values, default=None):
    if not values:
        return default
    x = avg(values)
    return sum([(v - x) ** 2 for v in values]) / len(values)


def std_dev(values, default=None):
    if not values:
        return default
    if len(values) < 2:
        return 0
    return math.sqrt(variance(values))


expressions_resolver = {
    exp.Count: lambda values: len(list_parser(values)),
    exp.Sum: lambda values: sum(list_parser(values, merge_type=int)),
    exp.Max: lambda values: max(list_parser(values)),
    exp.Min: lambda values: min(list_parser(values)),

    exp.Abs: abs,
    exp.Round: round,
    exp.Avg: avg,
    exp.Variance: variance,
    exp.StdDev: std_dev,

    exp.Length: len,
    exp.Value: lambda value: value,
    exp.Reverse: lambda value: ''.join(list(reversed(value))),
    exp.F: lambda value: value,
    exp.Upper: lambda value: str(value).upper(),
    exp.Lower: lambda value: str(value).lower(),
    exp.LTrim: lambda value: str(value).lstrip(),

    exp.ACos: math.acos,
    exp.Cos: math.cos,
    exp.ASin: math.asin,
    exp.Sin: math.sin,
    exp.ATan: math.atan,
    exp.Tan: math.tan,
    exp.Ceil: math.ceil,
    exp.Floor: math.floor,
    exp.Cot: lambda value: (1 / math.tan(value)) if math.tan(value) else None,
    exp.Sqrt: math.sqrt,
    exp.Degrees: math.degrees,
    exp.Exp: math.exp,
    exp.Ln: lambda value: math.log(value, math.e),
}

if hasattr(exp, 'MD5'):
    # django>2.2
    expressions_resolver.update({
        exp.MD5: lambda value: hashlib.md5(str(value).encode(UTF_8)).hexdigest(),
        exp.SHA1: lambda value: hashlib.sha1(str(value).encode(UTF_8)).hexdigest(),
        exp.SHA256: lambda value: hashlib.sha256(str(value).encode(UTF_8)).hexdigest(),
        exp.SHA224: lambda value: hashlib.sha224(str(value).encode(UTF_8)).hexdigest(),
        exp.SHA384: lambda value: hashlib.sha384(str(value).encode(UTF_8)).hexdigest(),
        exp.SHA512: lambda value: hashlib.sha512(str(value).encode(UTF_8)).hexdigest(),
    })


@ignore_errors(default=None, log=True)
def resolve_expression(expression: BaseExpression, value):
    if value is None:
        return None
    cls = expression.__class__
    if cls not in expressions_resolver:
        return ...
    return expressions_resolver[cls](value)


class Lookup:
    @classmethod
    def not_decorator(cls, f):
        @wraps(f)
        def func(*_, **__):
            return not f(*_, **__)
        return func

    @classmethod
    def common(cls, func):
        return func in (cls.exact, cls.IN)

    @classmethod
    @ignore_errors
    def exact(cls, value, e):
        if (value is None) ^ (e is None):
            return False
        return str(value) == str(e)

    @classmethod
    @ignore_errors
    def iexact(cls, value, e):
        if (value is None) ^ (e is None):
            return False
        return str(value).lower() == str(e).lower()

    @classmethod
    @ignore_errors
    def startswith(cls, value, s):
        return str(value).startswith(str(s))

    @classmethod
    @ignore_errors
    def istartswith(cls, value, s):
        return str(value).lower().startswith(str(s).lower())

    @classmethod
    @ignore_errors
    def endswith(cls, value, s):
        return str(value).endswith(str(s))

    @classmethod
    @ignore_errors
    def iendswith(cls, value, s):
        return str(value).lower().endswith(str(s).lower())

    @classmethod
    @ignore_errors
    def contains(cls, value, c):
        if iterable(value):
            return c in value
        return False

    @classmethod
    @ignore_errors
    def icontains(cls, value, c):
        if isinstance(value, str):
            return c.lower() in value.lower()
        return cls.contains(value, c)

    @classmethod
    @ignore_errors
    def gt(cls, value, v):
        try:
            return float(value) > float(v)
        except (ValueError, TypeError):
            return str(value) > str(v)

    @classmethod
    @ignore_errors
    def gte(cls, value, v):
        try:
            return float(value) >= float(v)
        except (ValueError, TypeError):
            return str(value) >= str(v)

    @classmethod
    @ignore_errors
    def lt(cls, value, v):
        try:
            return float(value) < float(v)
        except (ValueError, TypeError):
            return str(value) < str(v)

    @classmethod
    @ignore_errors
    def lte(cls, value, v):
        try:
            return float(value) <= float(v)
        except (ValueError, TypeError):
            return str(value) <= str(v)

    @classmethod
    @ignore_errors
    def regex(cls, value, r):
        return re.fullmatch(r, value)

    @classmethod
    @ignore_errors
    def iregex(cls, value, r):
        return re.fullmatch(r, value, re.I)

    @classmethod
    @ignore_errors
    def IN(cls, value, lst):
        for v in lst:
            if cls.exact(value, v):
                return True
        return False

    @classmethod
    @ignore_errors
    def NOT(cls, value, v):
        return value != v

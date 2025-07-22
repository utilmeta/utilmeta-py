from utype.types import *
from datetime import datetime, timedelta, date, time
from uuid import UUID
from django.db import models

SM = 32767
MD = 2147483647
LG = 9223372036854775807
PK = "pk"
ID = "id"
SEG = "__"

FIELDS_TYPE = {
    (
        "CharField",
        "ImageField",
        "ChoiceField",
        "PasswordField",
        "EmailField",
        "FilePathField",
        "FileField",
        "URLField",
        "SlugField",
        "GenericIPAddressField",
        "IPAddressField",
        "TextField",
        "RichTextField",
    ): str,
    ("UUIDField",): UUID,
    ("TimeField",): time,
    ("DateField",): date,
    ("DurationField",): timedelta,
    ("DateTimeField",): datetime,
    (
        "AutoField",
        "BigAutoField",
        "SmallAutoField",
        "BigIntegerField",
        "IntegerField",
        "PositiveIntegerField",
        "PositiveBigIntegerField",
        "SmallIntegerField",
        "PositiveSmallIntegerField",
        "SmallIntegerField",
    ): int,
    ("FloatField",): float,
    ("DecimalField",): Decimal,
    (
        "BooleanField",
        "NullBooleanField",
    ): bool,
    (
        "CommaSeparatedIntegerField",
        "ArrayField",
        "ManyToManyField",
        "ManyToOneRel",
        "ManyToManyRel",
    ): list,
    ("HStoreField",): dict,
    ("JSONField",): Any,
    ("BinaryField",): bytes,
}

TRANSFORM_TYPE_MAP = {
    "date": date,
    "time": time,
    "year": Year,
    "iso_year": Year,
    "month": Month,
    "day": Day,
    "week": Week,
    "week_day": WeekDay,
    "quarter": Quarter,
    "hour": Hour,
    "minute": Minute,
    "second": Second,
    "len": int,
    "length": int,
    "has_key": str,
    "has_any_keys": list,
    "has_keys": list,
    "keys": list,
    "values": list,
    "isempty": bool,
    "upper_inc": bool,
    "lower_inc": bool,
    "upper_inf": bool,
    "lower_inf": bool,
}

LOOKUP_TYPE_MAP = {
    'exact': Self,
    'iexact': str,
    'contains': str,
    'icontains': str,
    'in': list,
    'gt': Self,
    'gte': Self,
    'lt': Self,
    'lte': Self,
    'startswith': str,
    'istartswith': str,
    'endswith': str,
    'iendswith': str,
    'range': list,
    'isnull': bool,
    'regex': str,
    'iregex': str,
    "has_key": str,
    "has_keys": list,
    "has_any_keys": list,
    "contained_by": list,
    "overlap": list,
}

TRANSFORM_OUTPUT_TYPES = {
    # date/time transforms
    "date": models.DateField,
    "time": models.TimeField,
    "year": models.PositiveIntegerField,
    "iso_year": models.PositiveIntegerField,
    "month": models.PositiveSmallIntegerField,
    "day": models.PositiveSmallIntegerField,
    "week": models.PositiveSmallIntegerField,
    "week_day": models.PositiveSmallIntegerField,
    "quarter": models.PositiveSmallIntegerField,
    "hour": models.PositiveSmallIntegerField,
    "minute": models.PositiveSmallIntegerField,
    "second": models.PositiveSmallIntegerField,

    # char transforms
    "length": models.PositiveIntegerField,
    "len": models.PositiveIntegerField,
    "lower": models.CharField,
    "upper": models.CharField,
    "trim": models.CharField,
    "ltrim": models.CharField,
    "rtrim": models.CharField,

    "sha256": models.CharField,
    "md5": models.CharField,
    "left": models.CharField,
    "right": models.CharField,
    "concat": models.CharField,
    "repeat": models.CharField,
    "replace": models.CharField,
    "reverse": models.CharField,
    "strpos": models.PositiveIntegerField,
    "substr": models.CharField,
    "regex_replace": models.CharField,
}

# OPERATOR_FIELDS = [
#     dict(cls=models.FloatField, type=float, operators=["+", "-", "/", "*", "%", "^"]),
#     dict(cls=models.IntegerField, type=int, operators=["+", "-", "%"]),
#     dict(cls=models.IntegerField, type=float, operators=["/", "*", "^"]),
#     dict(
#         cls=models.DecimalField, type=Decimal, operators=["+", "-", "/", "*", "%", "^"]
#     ),
#     dict(cls=models.CharField, type=str, operators=["+"]),  # 'abc' + 'd' = 'abcd'
#     dict(cls=models.TextField, type=str, operators=["+"]),
#     dict(cls=models.CharField, type=int, operators=["*"]),
#     dict(cls=models.TextField, type=int, operators=["*"]),
#     dict(cls=models.DurationField, type=timedelta, operators=["+", "-"]),
#     dict(cls=models.DurationField, type=float, operators=["*", "/"]),
#     dict(cls=models.DateTimeField, type=timedelta, operators=["+", "-"]),
# ]

# PK_TYPES = (int, str, float, Decimal, UUID)

from utype.types import *
from datetime import datetime, timedelta, date, time
from uuid import UUID
from django.db import models

SM = 32767
MD = 2147483647
LG = 9223372036854775807
PK = 'pk'
ID = 'id'
SEG = '__'

FIELDS_TYPE = {
    ('CharField', 'ImageField', 'ChoiceField', 'PasswordField',
     'EmailField', 'FilePathField', 'FileField', 'URLField', 'SlugField',
     'GenericIPAddressField', 'IPAddressField', 'TextField',
     'RichTextField',): str,
    ('UUIDField',): UUID,
    ('TimeField',): time,
    ('DateField',): date,
    ('DurationField',): timedelta,
    ('DateTimeField',): datetime,
    ('AutoField', 'BigAutoField', 'SmallAutoField', 'BigIntegerField',
     'IntegerField', 'PositiveIntegerField', 'PositiveBigIntegerField',
     'SmallIntegerField', 'PositiveSmallIntegerField', 'SmallIntegerField',): int,
    ('FloatField',): float,
    ('DecimalField',): Decimal,
    ('BooleanField', 'NullBooleanField',): bool,
    ('CommaSeparatedIntegerField', 'ArrayField', 'ManyToManyField',
     'ManyToOneRel', 'ManyToManyRel'): list,
    ('JSONField', 'HStoreField'): dict,
    ('BinaryField',): bytes
}

datetime_lookups = ['date', 'time']
date_lookups = ['year', 'iso_year', 'month', 'day', 'week', 'week_day', 'quarter']
time_lookups = ['hour', 'minute', 'second']
option_allowed_lookups = [*datetime_lookups, *date_lookups, *time_lookups, 'len']

ADDON_FIELD_LOOKUPS = {
    'DateField': date_lookups,
    'TimeField': time_lookups,
    'DateTimeField': [*date_lookups, *time_lookups, *datetime_lookups],
    'JSONField': ['contains', 'contained_by', 'has_key', 'has_any_keys', 'has_keys'],
    'ArrayField': ['contains', 'contained_by', 'overlap', 'len'],
    'HStoreField': ['contains', 'contained_by', 'has_key', 'has_any_keys', 'has_keys', 'keys', 'values'],
    'RangeField': ['contains', 'contained_by', 'overlap', 'fully_lt', 'fully_gt', 'not_lt',
                   'not_gt', 'adjacent_to', 'isempty', 'lower_inc', 'lower_inf', 'upper_inc', 'upper_inf']
}

ADDON_LOOKUP_RULES = {
    'date': date,
    'time': time,
    'year': Year,
    'iso_year': Year,
    'month': Month,
    'day': Day,
    'week': Week,
    'week_day': WeekDay,
    'quarter': Quarter,
    'hour': Hour,
    'minute': Minute,
    'second': Second,
    'len': int,
    'has_key': str,
    'has_any_keys': list,
    'has_keys': list,
    'keys': list,
    'values': list,
    'isempty': bool,
    'upper_inc': bool,
    'lower_inc': bool,
    'upper_inf': bool,
    'lower_inf': bool,
}
ADDON_FIELDS = {
    'date': models.DateField,
    'time': models.TimeField,
    'year': models.PositiveIntegerField,
    'iso_year': models.PositiveIntegerField,
    'month': models.PositiveSmallIntegerField,
    'day': models.PositiveSmallIntegerField,
    'week': models.PositiveSmallIntegerField,
    'week_day': models.PositiveSmallIntegerField,
    'quarter': models.PositiveSmallIntegerField,
    'hour': models.PositiveSmallIntegerField,
    'minute': models.PositiveSmallIntegerField,
    'second': models.PositiveSmallIntegerField,
    'len': models.PositiveIntegerField,
}

OPERATOR_FIELDS = [dict(
    cls=models.FloatField,
    type=float,
    operators=['+', '-', '/', '*', '%', '^']
), dict(
    cls=models.IntegerField,
    type=int,
    operators=['+', '-', '%']
), dict(
    cls=models.IntegerField,
    type=float,
    operators=['/', '*', '^']
), dict(
    cls=models.DecimalField,
    type=Decimal,
    operators=['+', '-', '/', '*', '%', '^']
), dict(
    cls=models.CharField,
    type=str,
    operators=['+']     # 'abc' + 'd' = 'abcd'
), dict(
    cls=models.TextField,
    type=str,
    operators=['+']
), dict(
    cls=models.CharField,
    type=int,
    operators=['*']
), dict(
    cls=models.TextField,
    type=int,
    operators=['*']
), dict(
    cls=models.DurationField,
    type=timedelta,
    operators=['+', '-']
), dict(
    cls=models.DurationField,
    type=float,
    operators=['*', '/']
), dict(
    cls=models.DateTimeField,
    type=timedelta,
    operators=['+', '-']
)]

# PK_TYPES = (int, str, float, Decimal, UUID)

from django.db import models
from .queryset import AwaitableManager, AwaitableQuerySet
from utilmeta.utils.datastructure import Static
from django.db.models import CharField, NOT_PROVIDED


class PasswordField(CharField):
    @classmethod
    def guess_encoded(cls, pwd: str):
        if len(pwd) < 60:
            return False
        if pwd.count("$") < 3:
            return False
        if not pwd.endswith("="):
            return False
        return True

    def get_prep_value(self, value):
        if self.null and value is None:
            return None
        from django.contrib.auth.hashers import make_password
        from utilmeta.utils.functional import gen_key

        if self.guess_encoded(value):
            # already encoded, maybe error update using save() but did not specify update_fields
            return value
        return make_password(value, gen_key(self.salt_length))

    def __init__(
        self,
        max_length: int,
        min_length: int = 1,
        salt_length=32,
        regex: str = None,
        *args,
        **kwargs,
    ):
        kwargs["max_length"] = 80 + salt_length
        assert (
            isinstance(max_length, int)
            and isinstance(min_length, int)
            and max_length >= min_length > 0
        ), f"Password field length config must satisfy max_length >= min_length > 0"
        self.salt_length = salt_length
        self.regex = regex
        self._max_length = max_length
        self._min_length = min_length
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["max_length"] = self._max_length
        kwargs["min_length"] = self._min_length
        kwargs["salt_length"] = self.salt_length
        kwargs["regex"] = self.regex
        return name, path, args, kwargs


class ChoiceField(CharField):
    from typing import Union, Type, List, Optional
    from enum import Enum

    def get_prep_value(self, value):
        if self.null and value is None:
            return None
        v = str(value)
        if v in self.keys:
            if self.store_key:
                return v
            return self.choices_map[v]
        if not self.store_key:
            if v in self.values:
                return v
            if self.none_default:
                raise ValueError(
                    f"ChoiceField contains value: {value} out of choices scope {self.values}, "
                    f"if you don't wan't exception here, set a default value"
                )
        val = self.reverse_choices_map.get(v)
        if val:
            return val
        if self.none_default:
            raise ValueError(
                f"ChoiceField contains value: {value} out of choices scope {self.keys + self.values}, "
                f"if you don't wan't exception here, set a default value"
            )
        return self.default

    def from_db_value(self, value, expression=None, connection=None):
        return self.to_python(value)
        # return str(value)

    def to_python(self, value):
        # print('TO PYTHON:', value, self.retrieve_key)
        if value is None:
            return value
        if self.retrieve_key:
            if value in self.keys:
                return value
            return self.reverse_choices_map.get(value, self.default)
        if value in self.values:
            return value
        return self.choices_map.get(value, "")

    def get_value(self, value):
        if value is None:
            return value
        if value in self.values:
            return value
        return self.choices_map.get(value, value)

    def __init__(
        self,
        choices: Union[Type[Static], Type[Enum], dict, tuple, List[str]],
        retrieve_key: bool = False,
        store_key: bool = True,
        max_length: int = None,
        default: Optional[str] = NOT_PROVIDED,
        *args,
        **kwargs,
    ):
        from utilmeta.utils.functional import repeat, multi
        import inspect
        import collections
        from enum import Enum

        _max_length = 0

        keys = []
        values = []
        _choices = []
        if (
            inspect.isclass(choices)
            and issubclass(choices, Static)
            or isinstance(choices, Static)
        ):
            choices = choices.dict(reverse=True)
        if inspect.isclass(choices) and issubclass(choices, Enum):
            choices = dict(choices.__members__)

        if not choices:
            raise ValueError(f"ChoiceField must specify choices, got {choices}")
        if isinstance(choices, collections.Iterator):
            choices = list(choices)

        if isinstance(choices, tuple):
            _max_length = len(str(len(choices) - 1))
            for i, c in enumerate(choices):
                if multi(c):
                    choices = list(choices)
                    _max_length = 0
                    # classic django choices
                    break

                keys.append(str(i))
                values.append(str(c))
                _choices.append((str(i), str(c)))

        if isinstance(choices, list):
            for i, t in enumerate(choices):
                if isinstance(t, tuple):
                    assert len(t) == 2, ValueError(
                        "Choice field for list choices must be a 2-item tuple"
                    )

                _k = t[0] if isinstance(t, tuple) else str(i)
                _v = t[1] if isinstance(t, tuple) else str(t)

                if _max_length < len(str(t[0])):
                    _max_length = len(str(t[0]))

                keys.append(_k)
                values.append(_v)
                _choices.append((_k, _v))

        if isinstance(choices, dict):
            for k in choices.keys():
                if _max_length < len(str(k)):
                    _max_length = len(str(k))
                v = choices[k]

                if isinstance(v, Enum):
                    items = (str(v.value), v.name)
                else:
                    items = (str(k), str(v))

                keys.append(items[0])
                values.append(items[1])
                _choices.append(items)

        if not _choices:
            raise ValueError(
                f"ChoiceField choices must be list/tuple/dict got {choices}"
            )

        if not store_key:
            retrieve_key = False
        elif repeat(keys + values):
            raise ValueError(
                f"ChoiceField choices's keys {keys} and values {values} should't repeat"
            )

        self.keys = tuple(keys)
        self.values = tuple(values)
        self.value_set = self.keys + self.values
        self.retrieve_key = retrieve_key
        self.store_key = store_key

        self.choices_map = dict(_choices)
        self.reverse_choices_map = {c[1]: c[0] for c in _choices}

        if isinstance(default, Enum):
            default = default.value

        self.default = default
        if default is None:
            kwargs["null"] = True
        elif not self.none_default:
            if self.store_key:
                if str(default) not in self.keys:
                    try:
                        self.default = self.reverse_choices_map[str(default)]
                    except KeyError:
                        raise ValueError(
                            f"ChoiceField default value: {default} "
                            f"out of scope: {self.keys} and {self.values}"
                        )
            else:
                if str(default) not in self.values:
                    try:
                        self.default = self.choices_map[str(default)]
                    except KeyError:
                        raise ValueError(
                            f"ChoiceField default value: {default} "
                            f"out of scope: {self.keys} and {self.values}"
                        )

            # self.default = str(default) \
            #     if str(default) in self.keys else self.reverse_choices_map[default]
            if isinstance(self.default, str):
                if _max_length < len(self.default):
                    _max_length = len(self.default)
        if not self.store_key:
            _max_length = max([len(c) for c in self.choices_map.values()])

        if max_length and max_length < _max_length:
            raise ValueError(
                f"ChoiceField max_length: {max_length} "
                f"if less than the longest choice length: {_max_length}"
            )

        kwargs["max_length"] = max_length or _max_length
        kwargs["default"] = self.default
        kwargs["choices"] = tuple(_choices)
        self._choices = _choices  # be list type
        super().__init__(*args, **kwargs)

    @property
    def none_default(self):
        return self.default is NOT_PROVIDED

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["retrieve_key"] = self.retrieve_key
        kwargs["store_key"] = self.store_key
        kwargs["choices"] = self._choices
        return name, path, args, kwargs


class AwaitableModel(models.Model):
    objects = AwaitableManager()

    class Meta:
        abstract = True

    async def asave(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        qs = AwaitableQuerySet(model=self.__class__).using(using)
        if force_insert:
            await qs._insert_obj(self)
        else:
            if self.pk and (force_update or update_fields):
                # update
                fields = update_fields or qs.meta.local_concrete_fields
                data = {}
                for field in fields:
                    name = field
                    if not isinstance(field, str):
                        if hasattr(field, "attname"):
                            name = field.attname
                    if not isinstance(name, str):
                        continue
                    if hasattr(self, name):
                        data[name] = getattr(self, name)
                await qs.filter(pk=self.pk).aupdate(**data)
            else:
                await qs._insert_obj(self)

    async def adelete(self):
        if not self.pk:
            return
        return (
            await AwaitableQuerySet(model=self.__class__).filter(pk=self.pk).adelete()
        )


async def ACASCADE(collector, field, sub_objs, using):
    await collector.acollect(
        sub_objs,
        source=field.remote_field.model,
        source_attr=field.name,
        nullable=field.null,
        fail_on_restricted=False,
    )
    from django.db import connections

    if field.null and not connections[using].features.can_defer_constraint_checks:
        collector.add_field_update(field, None, sub_objs)


class AbstractSession(AwaitableModel):
    session_key = models.CharField(max_length=60, unique=True)
    encoded_data = models.TextField(null=True)

    # user = models.CharField(max_length=200, default=None, null=True)        # _user_id
    # somehow we allow anonymous session

    # ip = models.GenericIPAddressField()
    # ua_info = models.JSONField(default=dict)  # User-Agent string
    created_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=None, null=True)
    expiry_time = models.DateTimeField(default=None, null=True)
    deleted_time = models.DateTimeField(default=None, null=True)  # already expired

    class Meta:
        abstract = True

from . import multi, represent, Attr, SEG, ImmutableDict, distinct_add
from typing import Dict, Any, TypeVar, List
import inspect

T = TypeVar('T')

__all__ = ['Util', 'Meta']


# class UtilKey:
#     CLS = '@'
#     PATH = '@path'
#     ARGS = '@args'
#     OPERATOR = '@operator'
#     CONDITIONS = '@conditions'


class Meta(type):
    def __init__(cls, name, bases: tuple, attrs: dict, **kwargs):
        super().__init__(name, bases, attrs)

        __init = attrs.get(Attr.INIT)   # only track current init

        cls._kwargs = kwargs
        cls._pos_var = None
        cls._key_var = None
        cls._pos_keys = []
        cls._kw_keys = []
        cls._defaults = {}
        cls._requires = set()

        if not bases:
            return

        defaults = {}
        requires = set()
        for base in bases:
            if isinstance(base, Meta):
                defaults.update(base._defaults)
                requires.update(base._requires)
                distinct_add(cls._pos_keys, base._pos_keys)
                distinct_add(cls._kw_keys, base._kw_keys)
                if base._key_var:
                    cls._key_var = base._key_var
                if base._pos_var:
                    cls._pos_var = base._pos_var

        if __init:
            _self, *parameters = inspect.signature(__init).parameters.items()
            for k, v in parameters:
                v: inspect.Parameter
                if k.startswith(SEG) and k.endswith(SEG):
                    continue
                if v.default is not v.empty:
                    defaults[k] = v.default
                    if k in requires:
                        # if base is required but subclass not
                        requires.remove(k)
                elif v.kind not in (v.VAR_KEYWORD, v.VAR_POSITIONAL):
                    requires.add(k)

                if v.kind == v.VAR_POSITIONAL:
                    cls._pos_var = k
                elif v.kind == v.POSITIONAL_ONLY:
                    if k not in cls._pos_keys:
                        cls._pos_keys.append(k)
                elif v.kind == v.VAR_KEYWORD:
                    cls._key_var = k
                else:
                    if k not in cls._kw_keys:
                        cls._kw_keys.append(k)

        cls._defaults = ImmutableDict(defaults)
        cls._requires = requires
        cls._attr_names = [a for a in attrs if not a.startswith('_')]

    @property
    def cls_path(cls):
        return f'{cls.__module__}.{cls.__name__}'

    @property
    def kw_keys(cls):
        return cls._kw_keys

    @property
    def pos_slice(cls) -> slice:
        if cls._pos_var:
            return slice(0, None)
        return slice(0, len(cls._pos_keys))


class Util(metaclass=Meta):
    def __init__(self, __params__: Dict[str, Any]):
        args = []
        kwargs = {}
        spec = {}

        for key, val in __params__.items():
            if key.startswith(SEG) and key.endswith(SEG):
                continue
            if val is self:
                continue
            if key == self._pos_var:
                args += list(val)
                continue
            elif key == self._key_var:
                if isinstance(val, dict):
                    _kwargs = {k: v for k, v in val.items() if not k.startswith(SEG)}
                    kwargs.update(_kwargs)
                    spec.update(_kwargs)    # also update spec
                continue
            elif key in self._pos_keys:
                args.append(key)
            elif key in self._kw_keys:
                kwargs[key] = val
            else:
                continue
            if val != self._defaults.get(key):   # for key_var or pos_var the default is None
                spec[key] = val

        self.__args__ = tuple(args)
        self.__kwargs__ = kwargs
        self.__spec_kwargs__ = ImmutableDict(spec)

    def __hash__(self):
        return hash(repr(self))

    def __eq__(self, other: 'Util'):
        if inspect.isclass(self):
            return super().__eq__(other)
        if not isinstance(other, self.__class__):
            return False
        return self.__spec_kwargs__ == other.__spec_kwargs__ and self.__args__ == other.__args__

    def __bool__(self):
        # !! return not self.vacuum
        # prevent use <not self.vacuum> as bool (causing lots of recessive errors)
        # let sub utils define there own way of bool
        return True

    def __str__(self):
        return self._repr()

    def __repr__(self):
        return self._repr()

    @classmethod
    def _copy(cls, data, copy_class: bool = False):
        if multi(data):
            return type(data)([cls._copy(d) for d in data])
        if isinstance(data, dict):
            return {key: cls._copy(val) for key, val in data.items()}
        if inspect.isclass(data) and not copy_class:
            # prevent class util that carry other utils cause RecursiveError
            return data
        if isinstance(data, Util):
            return data.__copy__()
        return data

    def __deepcopy__(self, memo):
        return self.__copy__()

    def __copy__(self):
        # use copied version of sub utils
        # return self.__class__(*self._args, **self._kwargs)
        if inspect.isclass(self):
            bases = getattr(self, Attr.BASES, ())
            attrs = dict(self.__dict__)
            # pop(attrs, Attr.LOCK)       # pop __lock__
            cls: type = self.__class__
            return cls(self.__name__, bases, self._copy(attrs))
        return self.__class__(*self._copy(self.__args__), **self._copy(self.__spec_kwargs__))

    @property
    def _cls_name(self):
        if inspect.isclass(self):
            cls = self
        else:
            cls = self.__class__
        try:
            return cls.__qualname__
        except AttributeError:
            return cls.__name__

    def _repr(self, params: List[str] = None, excludes: List[str] = None):
        if inspect.isclass(self):
            return f'<{self._cls_name} class "{self.__module__}.{self._cls_name}">'
        attrs = []
        for k, v in self.__spec_kwargs__.items():
            # if not isinstance(v, bool) and any([s in str(k).lower() for s in self._secret_names]) and v:
            #     v = SECRET
            if k.startswith('_'):
                continue
            if params is not None and k not in params:
                continue
            if excludes is not None and k in excludes:
                continue
            attrs.append(k + '=' + represent(v))     # str(self.display(v)))
        s = ', '.join([represent(v) for v in self.__args__] + attrs)
        return f'{self._cls_name}({s})'

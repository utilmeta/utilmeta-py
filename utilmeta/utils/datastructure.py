import inspect
from email.header import Header as HttpHeader
import sys
from collections.abc import Mapping


class ImmutableDict(dict):
    def __error__(self, *args, **kwargs):
        raise AttributeError("ImmutableDict can not modify value")

    __delitem__ = __error__
    __setitem__ = __error__

    def __str__(self):
        return f'{self.__class__.__name__}({super().__repr__()})'

    def __repr__(self):
        return f'{self.__class__.__name__}({super().__repr__()})'

    setdefault = __error__
    pop = __error__
    popitem = __error__
    clear = __error__
    update = __error__


class ImmutableList(list):
    def error(self, *args, **kwargs):
        raise AttributeError("ImmutableList can not modify value")

    def __str__(self):
        return f'{self.__class__.__name__}({super().__repr__()})'

    def __repr__(self):
        return f'{self.__class__.__name__}({super().__repr__()})'

    append = error
    clear = error
    extend = error
    insert = error
    pop = error
    remove = error
    reverse = error
    sort = error
    __iadd__ = error
    __imul__ = error
    __setitem__ = error
    __delitem__ = error


# class RuntimeImmutable:
#     """
#     RunTime Immutable mixin apply to classes and instances
#     apply to class (API/Module/Schema)    : let it's metaclass inherit this class
#     apply to instance (Utils)             : let it's class inherit this class
#
#     when the service is setuped, it's consider runtime
#     and will call ._lock_all() method, then all the targets
#     instances and classes will be locked
#
#     and all the instances created after setuped is consider
#     user defined and will not be locked unless you manually called _lock()
#
#     take the first lock operation as valid
#     """
#     _MUTABLE = False
#
#     def _lock(self):
#         try:
#             self.__locked__ = True
#         except AttributeError:
#             pass
#
#     @classmethod
#     def _lock_all(cls):
#         try:
#             global _LOCKED, _IMMUTABLE
#             for child in _IMMUTABLE:
#                 child: cls
#                 child._lock()
#             _LOCKED = True
#             _IMMUTABLE = []
#         except AttributeError:
#             pass
#
#     def __setattr__(self, key: str, value):
#         if getattr(self, '__locked__', None):
#             raise AttributeError(f'{self.__class__.__name__} is readonly and'
#                                  f' cannot be set attribute ({key} -> {repr(value)}) during runtime')
#         return super().__setattr__(key, value)
#
#     def __delattr__(self, item):
#         if getattr(self, '__locked__', None):
#             raise AttributeError(f'{self.__class__.__name__} is readonly and'
#                                  f' cannot be delete attribute ({item}) during runtime')
#         return super().__delattr__(item)
#
#     def __init__(self):
#         try:
#             if not _LOCKED and not self._MUTABLE:
#                 global _IMMUTABLE
#                 _IMMUTABLE.append(self)
#         except AttributeError:
#             pass


class Static:
    def __init_subclass__(cls, ignore_duplicate: bool = False, **kwargs):
        attrs = []
        for name, attr in cls.__dict__.items():
            if name.startswith('_'):
                continue
            if attr in attrs and not ignore_duplicate:
                raise ValueError(f'Static value cannot be duplicated, got {attr}')
            attrs.append(attr)

    @classmethod
    def gen(cls) -> tuple:
        attrs = []
        for name, attr in cls.__dict__.items():
            if '__' in name:
                continue
            if callable(attr) or inspect.isfunction(attr) or inspect.ismethod(attr) or\
                    isinstance(attr, classmethod) or isinstance(attr, staticmethod):
                continue
            attrs.append(attr)
        return tuple(attrs)

    @classmethod
    def dict(cls, reverse: bool = False, lower: bool = False):
        attrs = {}
        for name, attr in cls.__dict__.items():
            if '__' in name:
                continue
            if callable(attr) or inspect.isfunction(attr) or inspect.ismethod(attr) or \
                    isinstance(attr, classmethod) or isinstance(attr, staticmethod):
                continue
            name = name.lower() if lower else name
            if reverse:
                attrs[attr] = name
            else:
                attrs[name] = attr
        return attrs


def immutable(val):
    if isinstance(val, dict):
        data = {}
        for k, v in val.items():
            data[k] = immutable(v)
        return ImmutableDict(data)
    elif isinstance(val, list):
        data = []
        for v in val:
            data.append(immutable(v))
        return ImmutableList(data)
    return val


class CaseInsensitiveMapping(Mapping):
    def __init__(self, data):
        self._store = {k.lower(): (k, v) for k, v in self._unpack_items(data)}

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __len__(self):
        return len(self._store)

    def __eq__(self, other):
        return isinstance(other, Mapping) and {
            k.lower(): v for k, v in self.items()
        } == {k.lower(): v for k, v in other.items()}

    def __iter__(self):
        return (original_key for original_key, value in self._store.values())

    def __repr__(self):
        return repr({key: value for key, value in self._store.values()})

    @staticmethod
    def _unpack_items(data):
        # Explicitly test for dict first as the common case for performance,
        # avoiding abc's __instancecheck__ and _abc_instancecheck for the
        # general Mapping case.
        if isinstance(data, (dict, Mapping)):
            yield from data.items()
            return
        for i, elem in enumerate(data):
            if len(elem) != 2:
                raise ValueError(
                    "dictionary update sequence element #{} has length {}; "
                    "2 is required.".format(i, len(elem))
                )
            if not isinstance(elem[0], str):
                raise ValueError(
                    "Element key %r invalid, only strings are allowed" % elem[0]
                )
            yield elem


class Headers(CaseInsensitiveMapping):
    def __delitem__(self, key):
        self.pop(key)

    def __setitem__(self, key: str, value):
        key = self._convert_to_charset(key, "ascii")
        value = self._convert_to_charset(str(value), "latin-1", mime_encode=True)
        self._store[key.lower()] = (key, value)

    def pop(self, key, default=None):
        return self._store.pop(key.lower(), default)

    def setdefault(self, key, value):
        if key not in self:
            self[key] = value

    def update(self, **kwargs):
        for key, val in kwargs.items():
            self[key] = val

    @classmethod
    def _convert_to_charset(cls, value, charset, mime_encode=False):
        """
        Convert headers key/value to ascii/latin-1 native strings.
        `charset` must be 'ascii' or 'latin-1'. If `mime_encode` is True and
        `value` can't be represented in the given charset, apply MIME-encoding.
        """
        try:
            if isinstance(value, str):
                # Ensure string is valid in given charset
                value.encode(charset)
            elif isinstance(value, bytes):
                # Convert bytestring using given charset
                value = value.decode(charset)
            else:
                value = str(value)
                # Ensure string is valid in given charset.
                value.encode(charset)
            if "\n" in value or "\r" in value:
                raise ValueError(
                    f"Header values can't contain newlines (got {value!r})"
                )
        except UnicodeError as e:
            # Encoding to a string of the specified charset failed, but we
            # don't know what type that value was, or if it contains newlines,
            # which we may need to check for before sending it to be
            # encoded for multiple character sets.
            if (isinstance(value, bytes) and (b"\n" in value or b"\r" in value)) or (
                isinstance(value, str) and ("\n" in value or "\r" in value)
            ):
                raise ValueError(
                    f"Header values can't contain newlines (got {value!r})"
                ) from e
            if mime_encode:
                value = HttpHeader(value, "utf-8", maxlinelen=sys.maxsize).encode()
            else:
                # e.reason += ", HTTP response headers must be in %s format" % charset
                raise
        return value


try:
    from django.utils.functional import SimpleLazyObject
    from django.utils.decorators import classonlymethod

    class LazyLoadObject(SimpleLazyObject):
        def __init__(self, ref: str):
            def _load_func():
                from .functional import import_obj
                return import_obj(ref)
            self.__dict__['_ref'] = ref
            super().__init__(_load_func)

except (ModuleNotFoundError, ImportError):
    class classonlymethod(classmethod):
        def __get__(self, instance, cls=None):
            if instance is not None:
                raise AttributeError("This method is available only on the class, not on instances.")
            return super().__get__(instance, cls)

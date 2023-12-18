import inspect
import os
import importlib
from .. import constant
import typing
from functools import wraps

__all__ = [
    'return_type',
    'file_like',
    'print_time',
    'import_obj',
    'print_dict',
    'class_func',
    'get_generator_result',
    'represent',
    'valid_attr',
    'check_requirement',
    'get_root_base',
    'function_pass',
    'common_representable',
    'get_doc',
    'get_base_type',
]


def _f_pass_doc(): """"""


def _f_pass(): pass


PASSED_CODES = (
    _f_pass.__code__.co_code,
    _f_pass_doc.__code__.co_code,
)


def represent(val) -> str:
    if isinstance(val, type):
        if val is type(None):
            return 'type(None)'
        return val.__name__
    if inspect.isfunction(val) or inspect.ismethod(val) or inspect.isclass(val) or inspect.isbuiltin(val):
        return val.__name__
    return repr(val)


def common_representable(data) -> bool:
    from .data import multi
    if multi(data):
        for val in data:
            if not common_representable(val):
                return False
        return True
    elif isinstance(data, dict):
        for key, val in data.items():
            if not common_representable(key) or not common_representable(val):
                return False
        return True
    elif type(data) in constant.COMMON_TYPES:
        return True
    return False


def class_func(f):
    return isinstance(f, (staticmethod, classmethod)) or inspect.ismethod(f) or inspect.isfunction(f)


def function_pass(f):
    if not inspect.isfunction(f):
        return False
    return getattr(f, constant.Attr.CODE).co_code in PASSED_CODES


def valid_attr(name: str):
    from keyword import iskeyword
    return name.isidentifier() and not iskeyword(name)


def get_root_base(cls):
    if not inspect.isclass(cls):
        if hasattr(cls, constant.Attr.CLS):
            return getattr(cls.__class__, constant.Attr.NAME, None)
        return None
    if cls.__bases__:
        if len(cls.__bases__) == 1 and cls.__bases__[0] is object:
            return cls.__name__
        return get_root_base(cls.__bases__[0])
    return cls.__name__


def get_base_type(value) -> typing.Optional[type]:
    if value in constant.COMMON_TYPES:
        return value
    if isinstance(value, object):
        tp = type(value)
    elif isinstance(value, type):
        tp = value
    else:
        return None
    if not inspect.isclass(tp):
        return None
    for base in tp.__bases__:
        t = get_base_type(base)
        if t:
            return t
    return None


def print_time(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        import time
        start = time.time()
        r = f(*args, **kwargs)
        end = time.time()
        t = round(end - start, 3)
        name = f.__name__
        print(f'function {name} cost {t} s')
        return r
    return wrapper


def print_dict(data):
    if isinstance(data, list):
        print('[')
        for d in data:
            print_dict(d)
            print(',')
        print(']\n')
        return
    items = getattr(data, 'items', None)
    if callable(items):
        print('{')
        for key, val in items():
            print(f'\t{repr(key)}: {repr(val)},')
        print('}')
        return
    print(data)


def file_like(obj) -> bool:
    try:
        return callable(getattr(obj, 'read')) and callable(getattr(obj, 'seek')) \
               and callable(getattr(obj, 'write')) and callable(getattr(obj, 'close'))
    except AttributeError:
        return False


def return_type(f, raw: bool = False):
    if isinstance(f, (staticmethod, classmethod)):
        f = f.__func__
    if not f:
        return None
    _t = getattr(f, constant.Attr.ANNOTATES).get('return')
    if raw:
        return _t
    try:
        t = typing.get_type_hints(f).get('return')
    except NameError:
        return _t
    if t is type(None):
        return None
    return t


def get_generator_result(result):
    if hasattr(result, '__next__'):
        # convert generator yield result into list
        # result = list(result)
        values = []
        recursive = False
        while True:
            try:
                v = next(result)
            except StopIteration:
                break
            if hasattr(v, '__next__'):
                recursive = True
                result = v
            else:
                values.append(v)
        if not values:
            result = None
        elif len(values) == 1 and recursive:
            result = values[0]
        else:
            result = values
    return result


def get_doc(obj) -> str:
    if not obj:
        return ''
    if isinstance(obj, str):
        return obj
    return inspect.cleandoc(getattr(obj, constant.Attr.DOC, '') or '')
    # return (getattr(obj, Attr.DOC, '') or '').replace('\t', '').strip('\n').strip()


def check_requirement(pkg: str, hint: str = None, check: bool = True, install_when_require: bool = False):
    try:
        if check:
            import_obj(pkg)
        else:
            raise ImportError
    except (ModuleNotFoundError, ImportError):
        if install_when_require:
            print(f'INFO: current service require <{pkg}> package, installing...')
            try:
                import sys
                os.system(f'{sys.executable} -m pip install {pkg}')
            except Exception as e:
                print(f'install package failed with error: {e}, fallback to internal solution')
                import pip
                pip_main = import_obj('pip._internal:main')
                pip_main(['install', pkg])
        else:
            if hint:
                print(hint)
            raise ImportError(f'package <{pkg}> is required for current settings, please install it '
                              f'or set install-when-require=True at meta.ini to allow auto installation')


def import_obj(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    if '/' in dotted_path and os.path.exists(dotted_path):
        from importlib.util import spec_from_file_location
        name = dotted_path.split(os.sep)[-1].rstrip(constant.PY)
        spec = spec_from_file_location(name, dotted_path)
        return spec.loader.load_module()
    try:
        # directly import packages and modules
        return importlib.import_module(dotted_path)
    except (ImportError, ModuleNotFoundError) as e:
        if dotted_path not in str(e):
            raise e
    if ':' not in dotted_path and '.' not in dotted_path:
        # module only
        return importlib.import_module(dotted_path)
    try:
        if ':' in dotted_path:
            module_path, class_name = dotted_path.split(':')
        else:
            module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    module = importlib.import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError('Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        ) from err

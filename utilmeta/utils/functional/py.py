import inspect
import os
import importlib
from .. import constant, exceptions
import typing
from functools import wraps
import subprocess
import sys
import asyncio

__all__ = [
    "return_type",
    "file_like",
    "print_time",
    "import_obj",
    "print_dict",
    "class_func",
    "get_generator_result",
    "represent",
    "valid_attr",
    # "check_requirement",
    "get_ref",
    "get_root_base",
    "function_pass",
    "common_representable",
    "get_doc",
    "requires",
    "get_base_type",
    "lazy_classmethod_loader",
    "async_to_sync_gen"
]


def _f_pass_doc():
    """"""


def _f_pass():
    pass


PASSED_CODES = (
    _f_pass.__code__.co_code,
    _f_pass_doc.__code__.co_code,
)


def represent(val) -> str:
    if isinstance(val, type):
        if val is type(None):
            return "type(None)"
        return val.__name__
    if (
        inspect.isfunction(val)
        or inspect.ismethod(val)
        or inspect.isclass(val)
        or inspect.isbuiltin(val)
    ):
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
    return (
        isinstance(f, (staticmethod, classmethod))
        or inspect.ismethod(f)
        or inspect.isfunction(f)
    )


def lazy_classmethod_loader(f: classmethod):
    if not isinstance(f, classmethod):
        return f

    func = f.__func__
    module_name = getattr(func, "__module__", '__main__')
    try:
        module = sys.modules[module_name]
    except KeyError:
        module = import_obj(module_name)

    qualname = func.__qualname__
    classes = qualname.split('.')[:-1]

    def get_class():
        # import class lazily at runtime
        cls = module
        for name in classes:
            try:
                cls = getattr(cls, name)
            except AttributeError:
                return cls
        return cls

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(get_class(), *args, **kwargs)

    return wrapper


def function_pass(f):
    if not inspect.isfunction(f):
        f = getattr(f, "__func__", None)
        if not f or not inspect.isfunction(f):
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
    if inspect.iscoroutinefunction(f):

        @wraps(f)
        async def wrapper(*args, **kwargs):
            import time

            start = time.time()
            r = await f(*args, **kwargs)
            end = time.time()
            t = round(end - start, 3)
            name = f.__name__
            print(f"function {name} cost {t} s")
            return r

    else:

        @wraps(f)
        def wrapper(*args, **kwargs):
            import time

            start = time.time()
            r = f(*args, **kwargs)
            end = time.time()
            t = round(end - start, 3)
            name = f.__name__
            print(f"function {name} cost {t} s")
            return r

    return wrapper


def print_dict(data):
    if isinstance(data, list):
        print("[")
        for d in data:
            print_dict(d)
            print(",")
        print("]\n")
        return
    items = getattr(data, "items", None)
    if callable(items):
        print("{")
        for key, val in items():
            print(f"\t{repr(key)}: {repr(val)},")
        print("}")
        return
    print(data)


def file_like(obj) -> bool:
    try:
        return (
            callable(getattr(obj, "read"))
            and callable(getattr(obj, "seek"))
            and callable(getattr(obj, "write"))
            and callable(getattr(obj, "close"))
        )
    except AttributeError:
        return False


def return_type(f, raw: bool = False):
    if isinstance(f, (staticmethod, classmethod)):
        f = f.__func__
    if not f:
        return None
    _t = getattr(f, constant.Attr.ANNOTATES).get("return")
    if raw:
        return _t
    try:
        t = typing.get_type_hints(f).get("return")
    except NameError:
        return _t
    if t is type(None):
        return None
    return t


def get_generator_result(result):
    if hasattr(result, "__next__"):
        # convert generator yield result into list
        # result = list(result)
        values = []
        recursive = False
        while True:
            try:
                v = next(result)
            except StopIteration:
                break
            if hasattr(v, "__next__"):
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
        return ""
    if isinstance(obj, str):
        return obj
    return inspect.cleandoc(getattr(obj, constant.Attr.DOC, "") or "")
    # return (getattr(obj, Attr.DOC, '') or '').replace('\t', '').strip('\n').strip()


# def check_requirement(
#     *pkgs: str, hint: str = None, check: bool = True, install_when_require: bool = False
# ):
#     if len(pkgs) > 1:
#         for pkg in pkgs:
#             try:
#                 return import_obj(pkg)
#             except (ModuleNotFoundError, ImportError):
#                 pass
#     for pkg in pkgs:
#         try:
#             if check:
#                 import_obj(pkg)
#             else:
#                 raise ImportError
#         except (ModuleNotFoundError, ImportError):
#             if install_when_require:
#                 print(f"INFO: current service require <{pkg}> package, installing...")
#                 try:
#                     import sys
#
#                     os.system(f"{sys.executable} -m pip install {pkg}")
#                 except Exception as e:
#                     print(
#                         f"install package failed with error: {e}, fallback to internal solution"
#                     )
#                     pip_main = import_obj("pip._internal:main")
#                     pip_main(["install", pkg])
#             else:
#                 if hint:
#                     print(hint)
#                 raise ImportError(
#                     f"package <{pkg}> is required for current settings, please install it "
#                     f"or set install-when-require=True at meta.ini to allow auto installation"
#                 )


def install_package(package, retires: int = 3, timeout: int = None):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--retries",
            str(retires),
            package,
        ],
        check=True,
        timeout=timeout,
    )


def requires(*names, **mp):
    if names:
        for name in names:
            mp[name] = str(name).split(".")[0]
    for import_name, install_name in mp.items():
        try:
            return import_obj(import_name)
            # return the 1st importable
        except (ModuleNotFoundError, ImportError):
            pass

    from utilmeta.conf import Preference

    pref = Preference.get()
    mps = []
    for import_name, install_name in mp.items():
        mps.append(f"{import_name}: pip install {install_name}")
    if pref.dependencies_auto_install_disabled:
        raise exceptions.DependencyNotInstalled(
            f"""Required module not installed:
%s
"""
            % "\n".join(mps)
        )

    for import_name, install_name in mp.items():
        print(f"INFO: current service require <{install_name}> package, installing...")

        try:
            install_package(install_name)
        except Exception as e:
            print(f"install package: <{install_name}> failed with error: {e}")

        # try:
        #     import sys
        #     os.system(f"{sys.executable} -m pip install {install_name}")
        #     # fixme: some uninstallable packages keep failing
        # except Exception as e:
        #     print(
        #         f"install package failed with error: {e}, fallback to internal solution"
        #     )
        #     pip_main = import_obj("pip._internal:main")
        #     pip_main(["install", install_name])
        try:
            return import_obj(import_name)
        except (ModuleNotFoundError, ImportError):
            pass
    raise exceptions.DependencyNotInstalled(
        f"""Required module not installed:
    %s
    """
        % "\n".join(mps)
    )
    # do not just return or raise ModuleNotFoundError,
    # this will cause ServerAdaptor to recursively dispatch further


def get_ref(obj) -> typing.Optional[str]:
    module = getattr(obj, '__module__', '')
    name = getattr(obj, '__qualname__', '') or getattr(obj, '__name__', '')
    return '.'.join([module, name]) or None


def import_obj(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    if "/" in dotted_path and os.path.exists(dotted_path):
        from importlib.util import spec_from_file_location

        name = dotted_path.split(os.sep)[-1].rstrip(constant.PY)
        spec = spec_from_file_location(name, dotted_path)
        return spec.loader.load_module()
    try:
        # directly import packages and modules
        return importlib.import_module(dotted_path)
    except (ImportError, ModuleNotFoundError) as e:
        if ":" not in dotted_path and "." not in dotted_path:
            # module only
            raise
    try:
        if ":" in dotted_path:
            module_path, *objs = dotted_path.split(":")
        else:
            module_path, *objs = dotted_path.split(".")
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    obj = importlib.import_module(module_path)

    try:
        for obj_name in objs:
            obj = getattr(obj, obj_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (module_path, '.'.join(objs))
        ) from err

    return obj


def async_to_sync_gen(async_gen):
    loop = asyncio.get_event_loop()
    agen = async_gen.__aiter__()
    while True:
        try:
            chunk = loop.run_until_complete(agen.__anext__())
            yield chunk
        except StopAsyncIteration:
            break

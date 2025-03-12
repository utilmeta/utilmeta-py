from utype.types import *
from utilmeta.utils import import_obj
import sys
import inspect


class BaseAdaptor:
    __path_loaded__ = False
    __backends_package__ = None
    __backends_route__ = None
    __backends_names__ = None
    backend = None

    @classmethod
    def get_module_name(cls, obj):
        name = None
        if inspect.ismodule(obj):
            name = obj.__name__
        if isinstance(obj, str):
            name = obj

        return name

    @classmethod
    def dispatch(cls, obj, *args, **kwargs):
        if isinstance(obj, cls):
            # adaptor
            return obj

        name = cls.get_module_name(obj)
        if name:
            ref = (
                f"{cls.__backends_package__}.{name}"
                if cls.__backends_package__
                else name
            )
            try:
                import_obj(ref)
            except (ModuleNotFoundError, ImportError):
                # ignore import error
                pass
        else:
            cls.load_from_base()

        if cls.qualify(obj):
            return cls(obj, *args, **kwargs)  # noqa
        to = cls.recursively_dispatch(cls, obj, *args, **kwargs)
        if to:
            return to
        raise NotImplementedError(
            f"{cls}: adaptor for {obj}: {repr(name)} is not implemented"
        )

    @classmethod
    def recursively_dispatch(cls, base, obj, *args, **kwargs):
        for impl in base.__subclasses__():
            impl: Type["BaseAdaptor"]
            try:
                if impl.qualify(obj):
                    return impl(obj, *args, **kwargs)  # noqa
            except (NotImplementedError, ModuleNotFoundError, ImportError):
                # consider this error means that the impl is not qualified
                continue
            to = cls.recursively_dispatch(impl, obj)
            if to:
                return to
        return None

    @classmethod
    def reconstruct(cls, adaptor: "BaseAdaptor"):
        raise NotImplementedError

    @classmethod
    def qualify(cls, obj):
        return False

    @classmethod
    def load_from_base(cls):
        if cls.__path_loaded__:
            return
        if cls.__backends_names__:
            for name in cls.__backends_names__:
                ref = (
                    f"{cls.__backends_package__}.{name}"
                    if cls.__backends_package__
                    else name
                )
                import_obj(ref)
        cls.__path_loaded__ = True

    @classmethod
    def set_backends_pkg(cls):
        if cls.__backends_package__:
            return
        module_parts = cls.__module__.split(".")
        module = sys.modules[cls.__module__]
        if not hasattr(module, "__path__"):
            module_parts = module_parts[:-1]
        if cls.__backends_route__:
            module_parts.append(cls.__backends_route__)
        cls.__backends_package__ = ".".join(module_parts)

    def __init_subclass__(cls, **kwargs):
        cls.set_backends_pkg()

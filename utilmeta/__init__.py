__website__ = 'https://utilmeta.com'
__homepage__ = 'https://utilmeta.com/py'
__author__ = 'Xulin Zhou (@voidZXL)'
__version__ = '2.7.0-alpha'


def version_info() -> str:
    import platform
    import sys
    from pathlib import Path

    info = {
        'utilmeta version': __version__,
        'installed path': Path(__file__).resolve().parent,
        'python version': sys.version,
        'platform': platform.platform(),
    }
    return '\n'.join('{:>30} {}'.format(k + ':', str(v).replace('\n', ' ')) for k, v in info.items())


def init_settings():
    try:
        from utype.settings import warning_settings
    except (ModuleNotFoundError, ImportError):
        return
    warning_settings.rule_length_constraints_on_unsupported_types = False
    warning_settings.field_unresolved_types_with_throw_options = False
    warning_settings.function_non_default_follows_default_args = False
    warning_settings.rule_no_arg_transformer = False
    warning_settings.rule_no_origin_transformer = False
    warning_settings.globals_name_conflict = False


init_settings()

from .core.server.service import UtilMeta

service: 'UtilMeta'     # current service in this process

_cmd_env = False

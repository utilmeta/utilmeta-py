from .core.server.service import UtilMeta

service: 'UtilMeta'     # current service in this process

__website__ = 'https://utilmeta.com'
__homepage__ = 'https://utilmeta.com/py'
__author__ = 'Xulin Zhou (@voidZXL)'
__version__ = '2.5.7'


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

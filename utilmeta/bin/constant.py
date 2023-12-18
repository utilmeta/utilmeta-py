import sys
LINUX = 'linux'
BSD = 'bsd'
WIN = 'win'
META_INI = 'meta.ini'
INIT_FILE = '__init__.py'
UWSGI = 'uwsgi'
GUNICORN = 'gunicorn'
NGINX = 'nginx'
APACHE = 'apache'
DOT = '●'
PRODUCTION = 'PRODUCTION'
DEBUG = 'DEBUG'
PYTHON = 'python'
SPACE_4 = ' ' * 4
JOINER = '\n' + SPACE_4
JOINER2 = JOINER + SPACE_4
PY_NAMES = (UWSGI, GUNICORN, PYTHON, '%s.exe' % PYTHON)
SERVER_NAMES = (NGINX, APACHE, UWSGI, GUNICORN)
UWSGI_CONFIG = f'{UWSGI}.ini'
GUNICORN_CONFIG = f'{GUNICORN}.conf'
NGINX_CONFIG = f'conf.{NGINX}'
APACHE_CONFIG = f'{APACHE}.conf'
WSGI_CHOICES = [UWSGI, GUNICORN]
WEB_CHOICES = [NGINX, APACHE]
DEFAULT_GITIGNORE = """
*/__pycache__
__pycache__/
*.py[cod]

*/env
!*/env/__init__.py

.idea
.vscode
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
"""


GREEN = '\033[1;32m%s\033[0m'
RED = '\033[1;31m%s\033[0m'
BLUE = '\033[1;34m%s\033[0m'
YELLOW = '\033[1;33m%s\033[0m'
BANNER = '\033[1;30;47m%s\033[0m'

LINE_WIDTH = 100
if sys.platform != LINUX:
    # window not support color print
    try:
        import colorama

        colorama.init(autoreset=True)
    except ModuleNotFoundError:
        # DOWN GRADE
        GREEN = '%s'
        RED = '%s'
        BLUE = '%s'
        YELLOW = '%s'
        BANNER = '%s'

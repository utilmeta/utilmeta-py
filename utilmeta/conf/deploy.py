from .base import Config

# preload_app = True [must]
GUNICORN_POST_FORK = """
def post_fork(server, worker):
    try:
        from utilmeta import service
    except (ModuleNotFoundError, ImportError):
        pass
    else:
        service.startup()
"""
# todo: For backend that does not have native on_startup hook
#   we need to use the post_fork function in the uwsgi / gunicorn
#   uwsgi has uwsgidecorators which can apped automatically
#   but gunicorn requires a explict config in the config file,
#   we will inject the above code the the generated gunicorn config
#


class Deploy(Config):
    pass

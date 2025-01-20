from utilmeta.conf import Env


class ServiceEnvironment(Env):
    PRODUCTION: bool = False
    DJANGO_SECRET_KEY: str = ""


env = ServiceEnvironment(sys_env="UTILMETA_")

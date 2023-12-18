from utilmeta.conf import Env


class ServiceEnvironment(Env):
    PRODUCTION: bool = False


env = ServiceEnvironment(sys_env='META_')

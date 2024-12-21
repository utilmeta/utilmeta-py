class NotConfigured(NotImplementedError):
    def __init__(self, config_cls):
        self.config_cls = config_cls
        super().__init__(self.msg)

    @property
    def msg(self):
        return f"Config: {self.config_cls} not configured"


class SettingNotConfigured(NotConfigured):
    def __init__(self, config_cls, item: str):
        self.item = item
        super().__init__(config_cls)

    @property
    def msg(self):
        return f"Config: {self.config_cls}.{self.item} not configured"


class ConfigError(Exception):
    pass


class UnsetError(ConfigError):
    # some config is required to set a value in some condition but remain empty (None)
    pass


class InvalidDeclaration(Exception):
    pass


class DependencyNotInstalled(Exception):
    def __init__(self, msg: str = None, *, import_name: str = None, install_name: str = None):
        msg = msg or f"""Required module not installed: 
{import_name}: {install_name}
        """
        super().__init__(msg)
        self.import_name = import_name
        self.install_name = install_name

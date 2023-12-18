
class MissingPrimaryKey(ValueError):
    def __init__(self, msg: str, model=None):
        self.model = model
        super().__init__(msg or 'orm.Error: pk is missing for update')


class EmptyQueryset(ValueError):
    def __init__(self, msg: str, model=None):
        self.model = model
        super().__init__(msg or 'orm.Error: result is empty')


class InvalidMode(TypeError):
    pass

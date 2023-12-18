from .schema import BaseSessionSchema


class AioFilesSession(BaseSessionSchema):
    def exists(self, session_key):
        pass

    def create(self):
        pass

    def save(self, must_create=False):
        pass

    def delete(self, session_key=None):
        pass

    def load(self):
        pass

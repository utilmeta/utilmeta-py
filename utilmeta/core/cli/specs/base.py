
class BaseClientGenerator:
    __version__ = None
    __spec__ = None

    # None -> dict
    # json -> json string
    # yml -> yml string

    def __init__(self, document):
        self.document = document

    @classmethod
    def generate_from(cls, url_or_file):
        raise NotImplementedError

    def generate(self):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        return self.generate()

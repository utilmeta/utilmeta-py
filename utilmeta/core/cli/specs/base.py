import os


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

    def __call__(self, file=None, console: bool = False):
        content = self.generate()
        if file:
            file_path = file
            if not os.path.isabs(file):
                file_path = os.path.join(os.getcwd(), file)
            with open(file, 'w', encoding='utf-8') as f:
                f.write(content)
            return file_path
        elif console:
            print(content)
        return content

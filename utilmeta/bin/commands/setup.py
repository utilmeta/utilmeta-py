from ..base import Arg, command
from .base import BaseServiceCommand
from typing import Literal, Optional
import os
from ..constant import RED, META_INI, BLUE
from utilmeta.bin import template as package
from utilmeta.utils import read_from, write_to, import_obj, check_requirement
import shutil

TEMP_PATH = package.__path__[0]


class SetupCommand(BaseServiceCommand):
    SERVER_BACKENDS = 'utilmeta.core.server.backends'
    DEFAULT_SUPPORTS = [
        'django',
        'flask',
        'fastapi',
        'starlette',
        'sanic',
        'tornado'
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.wsgi = None
        self.email = None
        self.web_server = None
        self.backend = None
        self.host = None
        self.project_name: Optional[str] = None
        self.description: Optional[str] = None
        # self.inside = False
        # self.service_name = None

    @property
    def default_host(self):
        if not self.project_name:
            return
        return f'{self.project_name}.com'.lower()

    @property
    def default_backend(self):
        return 'django'

    @command('')
    def setup(self, name: str = '', *,
              template: Literal['full', 'lite'] = Arg('--temp', alias_from=['--t', '--template'], default='lite')):
        """
        Set up a new project
        :param name: project name
        :param template: [optional] template suite, chose from 'full', 'lite', default to 'lite'
        """
        if not name:
            print(RED % 'meta Error: project name is required for setup')
            exit(1)

        if self.ini_path:
            print(RED % 'meta Error: you are already inside an utilmeta project, '
                        'please chose a empty dir to setup your new project')
            exit(1)

        project_dir = self.cwd

        if os.sep in name or '/' in name:
            print(RED % f'meta Error: project name ({repr(name)}) should not contains path separator')
            exit(1)

        self.project_name = name
        print(f'meta: setting up project [{name}]')

        print(f'description of this project (optional)')
        self.description = input('>>> ') or ''

        print(f'Choose the http backend of your project')
        for pkg in self.DEFAULT_SUPPORTS:
            print(f' - {pkg}%s' % (' (default)' if pkg == self.default_backend else ''))

        while not self.backend:
            self.backend = (input('>>> ') or self.default_backend).lower()
            try:
                import_obj(f'{self.SERVER_BACKENDS}.{self.backend}')
            except ModuleNotFoundError:
                if self.backend in self.DEFAULT_SUPPORTS:
                    check_requirement(self.backend, install_when_require=True)
                else:
                    print(f'backend: {repr(self.backend)} not supported or not installed, please enter again')
                    self.backend = None

        print(f'Enter the production host of your service (default: {self.default_host})')
        self.host = input('>>> ') or self.default_host

        temp_path = os.path.join(TEMP_PATH, template)
        project_path = os.path.join(project_dir, name)
        # -------------------------------------
        self.ini_path = os.path.join(project_path, META_INI)
        # assign ini path here so project_root can be automatically passed,
        # later write ini if not inside a project

        # --------------------------------------

        if os.path.exists(project_path):
            print(RED % f'meta Error: project path {project_path} already exist, chose a different name')
            exit(1)

        shutil.copytree(temp_path, project_path)

        for ab_path, dirs, files in os.walk(project_path):
            for file in files:
                path = os.path.join(ab_path, file)

                if str(file).endswith('.py') or str(file).endswith('.ini'):
                    content = read_from(path)
                    write_to(path, self.render(content.replace('# noqa', '')))

        print(f'UtilMeta project <{BLUE % self.project_name}> successfully setup at path: {project_path}')

    def render(self, content) -> str:
        def _format(text: str, *args, **kwargs):
            for i in range(0, len(args)):
                k = "{" + str(i) + "}"
                text = text.replace(k, str(args[i]))
            for key, val in kwargs.items():
                k = "{" + key + "}"
                text = text.replace(k, str(val))
            return text

        return _format(
            content,
            name=self.project_name,
            backend=self.backend,
            import_backend=f'import {self.backend}',
            description=self.description,
            host=self.host
        )

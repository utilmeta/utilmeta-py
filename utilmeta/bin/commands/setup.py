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
    name = 'setup'

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
              template: Literal['full', 'lite'] = Arg('--temp', alias_from=['--t', '--template'], default='lite'),
              with_operations: bool = Arg('--ops', default=False),
              ):
        """
        Set up a new project
        --t: select template: full / lite
        --ops: with operations configuration
        """
        while not name:
            print(f'Enter the name of your project:')
            name = input('>>> ').strip()

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

        if self.backend == 'starlette':
            check_requirement('uvicorn', install_when_require=True)

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
                    write_to(path, self.render(
                        content.replace('# noqa', ''),
                        with_operations=with_operations,
                        template=template
                    ))

        print(f'UtilMeta project <{BLUE % self.project_name}> successfully setup at path: {project_path}')

    def render(self, content, with_operations: bool = False, template: str = None) -> str:
        def _format(text: str, *args, **kwargs):
            for i in range(0, len(args)):
                k = "{" + str(i) + "}"
                text = text.replace(k, str(args[i]))
            for key, val in kwargs.items():
                k = "{" + key + "}"
                text = text.replace(k, str(val))
            return text

        if template == 'full':
            operations_text = """
    from utilmeta.ops.config import Operations
    from utilmeta.conf.time import Time
    
    service.use(Time(
        time_zone='UTC',
        use_tz=True,
        datetime_format="%Y-%m-%dT%H:%M:%SZ"
    ))
    service.use(Operations(
        route='ops',
        database=Database(
            name='{name}_utilmeta_ops',
            engine='sqlite3',
        ),
    ))
""".format(name=self.project_name)
        else:
            operations_text = """
from utilmeta.ops.config import Operations
from utilmeta.conf.time import Time
from utilmeta.core.orm.databases import DatabaseConnections, Database

service.use(DatabaseConnections({{
    'default': Database(
        name='{name}',
        engine='sqlite3',
    )
}}))
service.use(Time(
    time_zone='UTC',
    use_tz=True,
    datetime_format="%Y-%m-%dT%H:%M:%SZ"
))
service.use(Operations(
    route='ops',
    database=Database(
        name='{name}_utilmeta_ops',
        engine='sqlite3',
    ),
))
""".format(name=self.project_name)

        return _format(
            content,
            name=self.project_name,
            backend=self.backend,
            import_backend=f'import {self.backend}',
            description=self.description,
            host=self.host,
            operations=operations_text if with_operations else '',
            plugins="""
@api.CORS(allow_origin='*')""" if with_operations else ''
        )

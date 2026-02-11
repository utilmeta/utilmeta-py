from utype.types import *
from utype.specs.json_schema.generator import JsonSchemaGenerator
from utilmeta.utils import get_ref, get_doc, import_obj
from utype import parse


class BaseHandler:
    DEFAULT_SEVERITY = 3    # INFO

    def __init__(self, handler: Callable,
                 name: str = None,
                 title: str = None,
                 description: str = None,
                 ):

        self.handler = handler
        self.name = name or handler.__name__
        if self.name.startswith('_'):
            raise ValueError(f'{self.__class__.__name__}: handler name cannot startswith "_“, got {self.name}')
        self.ref = get_ref(self.handler)
        self.title = title
        self.description = description
        # --------
        self.parameters = None
        self.return_value = None
        self.setup_handler()

        self._registry = None

    @classmethod
    def deserialize(cls, ref: str):
        try:
            obj = import_obj(ref)
        except (ModuleNotFoundError, AttributeError, ImportError):
            # this handler is probably deleted from code
            return None
        if not isinstance(obj, cls):
            return None
        return obj

    def setup_handler(self):
        spec_data = JsonSchemaGenerator(self.handler)()
        return_type = spec_data.get('returnValue')
        params = dict(spec_data.get('parameters') or {})
        required = list(spec_data.get('required') or [])
        if required:
            for req in required:
                params.setdefault(req, {}).update(required=True)
        self.parameters = params
        self.return_value = return_type
        self.description = self.description or get_doc(self.handler)
        if self.parameters:
            self.handler = parse(self.handler, ignore_result=True)

    def setup(self, registry=None, name: str = None, ref: str = None):
        if registry:
            self._registry = registry
        if name:
            self.name = name
        if ref:
            self.ref = ref

    @property
    def registry(self):
        if self._registry:
            return self._registry
        registry_ref = '.'.join(self.ref.split('.')[-1])
        try:
            return import_obj(registry_ref)
        except ImportError:
            return None

    def dict(self) -> dict:
        return dict(
            name=self.name,
            ref=self.ref,
            title=self.title,
            description=self.description,
            parameters=self.parameters,
            return_value=self.return_value,
        )

from utilmeta.core import api, request
from .utils import SupervisorObject, supervisor_var, WrappedResponse, opsRequire
from utilmeta.utils import import_obj, reduce_value, SECRET, adapt_async, exceptions, awaitable
from utilmeta.core.orm import ModelAdaptor
from utype.types import *
from .utils import config
import utype
import os


class QuerySchema(utype.Schema):
    # id_list: list = None
    query: dict = {}
    orders: List[str] = ['pk']
    rows: int = utype.Field(default=10, le=100, ge=1)
    page: int = utype.Field(default=1, ge=1)
    fields: list = []
    max_length: Optional[int] = None


class CreateDataSchema(utype.Schema):
    data: List[dict]
    return_fields: List[str] = utype.Field(default_factory=list)
    return_max_length: Optional[int] = None


class UpdateDataSchema(utype.Schema):
    data: List[dict]


class DataAPI(api.API):
    supervisor: SupervisorObject = supervisor_var
    response = WrappedResponse

    model: str = request.QueryParam(required=True)
    # model ref
    # using: str = request.QueryParam(default=None)

    def import_model(self):
        if '.' not in self.model:
            return None
        from utilmeta import service
        *packages, model_name = self.model.split('.')
        model_file = os.path.join(service.project_dir, *packages)
        # this is to prevent model from importing the packages outside the project
        # (that may cause security issues)
        if not os.path.exists(model_file) and not os.path.exists(model_file + '.py'):
            package = packages[0]
            if package and any([package == p for p in config.trusted_packages]):
                # this package is trusted
                pass
            else:
                raise exceptions.BadRequest(f'Invalid model: {self.model}')
        # package.file.modelName
        try:
            return import_obj(self.model)
        except (ModuleNotFoundError, ImportError):
            raise exceptions.BadRequest(f'Invalid model: {self.model}')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._adaptor = None
        # not trigger adaptor load until the first access
        self.model_class = None

    @property
    def adaptor(self):
        if self._adaptor:
            return self._adaptor
        self.model_class = self.import_model()
        try:
            self._adaptor = ModelAdaptor.dispatch(self.model_class)
        except NotImplementedError:
            raise exceptions.BadRequest(f'Invalid model: {self.model}')
        return self._adaptor

    def parse_result(self, data, max_length: Optional[int] = None):
        if isinstance(data, list):
            for d in data:
                self.parse_result(d, max_length=max_length)
            return data
        elif isinstance(data, dict):
            for k in list(data.keys()):
                if k == 'pk':
                    continue
                field = self.adaptor.get_field(k)
                if config.is_secret(k) and not field.related_model:
                    if data[k] and not isinstance(data[k], bool):
                        # if value is empty string or None, keep it the same
                        data[k] = SECRET
                if isinstance(max_length, int):
                    data[k] = reduce_value(data[k], max_length=max_length)
            return data
        return reduce_value(data, max_length=max_length)

    # scope: data.view:[TABLE_IDENT]
    @api.post('query')
    @opsRequire('data.query')
    @adapt_async
    def query_data(self, query: QuerySchema = request.Body):
        try:
            unsliced_qs = self.adaptor.get_queryset(**query.query)
            count = unsliced_qs.count()
            qs = unsliced_qs.order_by(*query.orders)[(query.page - 1) * query.rows: query.page * query.rows]
            fields = query.fields
            if not fields:
                fields = ['pk'] + [f.column_name for f in self.adaptor.get_fields(
                    many=False, no_inherit=True) if f.column_name]
            values = self.adaptor.values(qs, *fields)
        except self.adaptor.field_errors as e:
            raise exceptions.BadRequest(str(e)) from e
        return self.response(
            self.parse_result(values, max_length=query.max_length),
            count=count
        )

    @api.post('create')
    @opsRequire('data.create')
    @adapt_async
    def create_data(self, data: CreateDataSchema = request.Body):
        objs = []
        for val in data.data:
            objs.append(self.adaptor.init_instance(**val))
        qs = self.adaptor.bulk_create(objs)
        values = self.adaptor.values(qs, *data.return_fields)
        return self.parse_result(values, max_length=data.return_max_length)

    @api.post('update')
    @opsRequire('data.update')
    @adapt_async
    def update_data(self, data: UpdateDataSchema = request.Body):
        objs = []
        fields = set()
        for val in data.data:
            obj = self.adaptor.init_instance(**val)
            fields.update(set(val))
            if obj.pk:
                objs.append(obj)
        fields = fields.difference({'pk'})
        return self.adaptor.bulk_update(objs, fields=fields)

    def delete_data(self,
                    id: str = request.BodyParam
                    # query: dict = request.BodyParam,
                    # limit: Optional[int] = request.BodyParam(None)
                    ):
        # qs = self.adaptor.get_queryset(**query)
        # if limit is not None:
        #     qs = qs.order_by('pk')[:limit]
        return self.adaptor.delete(pk=id)

    @api.post('delete')
    @opsRequire('data.delete')
    @awaitable(delete_data)
    async def delete_data(self,
                          id: str = request.BodyParam
                          ):
        # apply for async CASCADE
        return await self.adaptor.adelete(pk=id)

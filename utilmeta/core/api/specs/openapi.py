"""
Implement OpenAPI document generation
"""
import inspect

from ..endpoint import Endpoint
from utilmeta.core.api.base import API
from utilmeta.core.api.route import APIRoute
from utilmeta.core.request import properties
from utilmeta.core.response import Response
from utilmeta.core.auth.base import BaseAuthentication
from utilmeta.core.auth.properties import User
from utilmeta.core.response.base import Headers, JSON, OCTET_STREAM, PLAIN
from utilmeta.utils.context import Property, ParserProperty
from utilmeta.utils.constant import HAS_BODY_METHODS
from utype import Schema, Field, JsonSchemaGenerator
from utype.parser.field import ParserField
from utype.parser.rule import LogicalType
from utype.utils.datastructures import unprovided
from utype.utils.functional import get_obj_name
from typing import Type, Tuple, Dict, List, TYPE_CHECKING, Optional
from .base import BaseAPISpec
import os
import json

if TYPE_CHECKING:
    from utilmeta import UtilMeta


def guess_content_type(schema: dict):
    if not schema:
        return JSON

    type = schema.get('type')
    format = schema.get('format')

    if type in ('object', 'array'):
        return JSON

    if schema.get('$ref'):
        return JSON

    if format == 'binary':
        return OCTET_STREAM

    return PLAIN

# todo: for schema, consider INPUT/OUTPUT and mode, and count it to different schema


class OpenAPIGenerator(JsonSchemaGenerator):
    DEFAULT_REF_PREFIX = "#/components/schemas/"

    def generate_for_field(self, f: ParserField, options=None):
        data = super().generate_for_field(f, options=options)
        if data is None:
            return data
        t = f.output_type if self.output else f.type
        if isinstance(t, LogicalType) and f.discriminator_map:
            # not part of json-schema, but in OpenAPI
            data.update(discriminator=dict(
                propertyName=f.field.discriminator,
                mapping={k: self.generate_for_type(v) for k, v in f.discriminator_map.items()}
            ))
        return data

    def generate_for_response(self, response: Type[Response]):
        parser = getattr(response, '__parser__', None)
        result_field = parser.get_field('result') if parser else None
        headers_field = parser.get_field('headers') if parser else None

        result_schema = self.generate_for_field(result_field) if result_field else None
        headers_schema = self.__class__(headers_field.type, output=True)() \
            if headers_field and headers_field.type != Headers else {}
        # headers is different, doesn't need to generate $ref

        headers_props = headers_schema.get('properties') or {}
        headers_required = headers_schema.get('required') or []
        headers = {}
        for key, val_schema in headers_props.items():
            headers[key] = {
                'schema': val_schema,
                'required': key in headers_required
            }

        content_type = response.content_type
        # todo: headers wrapped
        if response.wrapped:
            props = {}
            if response.result_key:
                props[response.result_key] = result_schema
            if response.message_key:
                msg = dict(self.generate_for_type(str))
                msg.update(
                    title='Message',
                    description='an error message of response',
                )
                props[response.message_key] = msg
            if response.state_key:
                state = dict(self.generate_for_type(str))
                state.update(
                    title='State',
                    description='action state code of response',
                )
                props[response.state_key] = state
            if response.count_key:
                cnt = dict(self.generate_for_type(int))
                cnt.update(
                    title='Count',
                    description='a count of the total number of query result',
                )
                props[response.count_key] = cnt

            data_schema = {
                'type': 'object',
                'properties': props,
                'required': list(props)
            }
            content_type = JSON
        else:
            data_schema = result_schema
            if not content_type:
                content_type = guess_content_type(data_schema)

        return dict(
            description=response.description,
            headers=headers,
            content={content_type: {
                'schema': data_schema
            }},
        )

    # def generate_for_authentication(self, auth: BaseAuthentication):
    #     return auth.openapi_scheme()


class OpenAPIInfo(Schema):
    title: str
    version: str
    description: str
    term_of_service: str = Field(alias='termsOfService', alias_from=['tos'], default='')
    contact: dict = Field(default_factory=dict)
    license: dict = Field(default_factory=dict)


class ServerSchema(Schema):
    url: str
    description: str = Field(default='')
    variables: dict = Field(default_factory=dict)


class OpenAPISchema(Schema):
    openapi: str
    info: OpenAPIInfo
    paths: Dict[str, dict]
    servers: List[ServerSchema]
    components: dict


_generated_document = None


class OpenAPI(BaseAPISpec):
    __version__ = '3.1.0'
    generator_cls = OpenAPIGenerator
    FORMATS = ['json', 'yaml']
    PARAMS_IN = ['path', 'query', 'header', 'cookie']
    # None -> dict
    # json -> json string
    # yml -> yml string

    def __init__(self, service: 'UtilMeta'):
        super().__init__(service)
        self.defs = {}
        self.names = {}
        self.responses = {}
        self.response_names = {}
        self.paths: Dict[str, dict] = {}
        self.security_schemas = {}
        # self.operations = {}

    def get_def_name(self, t: type):
        for k, v in self.names.items():
            if v == t:
                return k
        return get_obj_name(t)

    def get_defs(self) -> Dict[str, dict]:
        defs = {}
        for t, values in self.defs.items():
            name = self.get_def_name(t)
            defs[name] = values
        return defs

    def get_responses(self) -> Dict[str, dict]:
        resp = {}
        for r, values in self.responses.items():
            name = self.get_response_name(r)
            resp[name] = values
        return resp

    def __call__(self):
        self.generate_paths()
        return OpenAPISchema(
            openapi=self.__version__,
            info=self.generate_info(),
            components=self.components,
            paths=self.paths,
            servers=[self.server]
        )

    def get_generator(self, t, output: bool = False):
        return self.generator_cls(t, defs=self.defs, names=self.names, output=output)

    @property
    def components(self):
        return dict(
            schemas=self.get_defs(),
            responses=self.get_responses(),
            securitySchemes=self.security_schemas
        )

    @property
    def server(self):
        return dict(url=self.service.base_url)

    def save(self, format: str = 'json'):
        schema = self()

        if format == 'json':

            return json.dumps(schema, ensure_ascii=False)
        elif format == 'yaml':
            import yaml     # requires pyyaml
            return yaml.dump(schema)

        else:
            raise ValueError(f'format: {repr(format)} not supported')

    @classmethod
    def as_api(cls, path: str = None, private: bool = True):
        from utilmeta.core import api

        # if path is not specified, use local mem instead
        class OpenAPI_API(API):
            response = Response

            @api.get(private=private)
            def get(self):
                from utilmeta import service

                # if path:
                #     file_path = os.path.join(service.project_dir, path)
                #     if os.path.exists(file_path):
                #         return self.response(file=open(file_path, 'r'))

                global _generated_document
                if _generated_document:
                    return _generated_document

                openapi = cls(service)
                # generate document
                _generated_document = openapi()
                if path:
                    file_path = os.path.join(service.project_dir, path)
                    if path.endswith('.yml'):
                        import yaml  # requires pyyaml
                        content = yaml.dump(_generated_document)
                    else:
                        content = json.dumps(_generated_document, ensure_ascii=False)
                    with open(file_path, 'w') as f:
                        f.write(content)
                    return content

                return _generated_document

        return OpenAPI_API

    @classmethod
    def _path_join(cls, *routes):
        return '/' + '/'.join([str(r or '').strip('/') for r in routes]).rstrip('/')

    def generate_info(self) -> OpenAPIInfo:
        data = dict(
            title=self.service.title or self.service.name or self.service.description,
            description=self.service.description or self.service.title,
            version=self.service.version
        )
        if self.service.info:
            data.update(self.service.info)
        return OpenAPIInfo(**data)

    def generate_paths(self):
        api = self.service.resolve()
        if not issubclass(api, API):
            raise TypeError(f'Invalid root_api: {api}')
        # return self.from_api(api, path=self.service.root_url)
        return self.from_api(api)

    @classmethod
    def merge_requires(cls, base_requires: List[dict], requires: List[dict]) -> list:
        if not base_requires:
            return requires
        if not requires:
            return base_requires
        base_optional = {} in base_requires
        optional = {} in requires
        res = []
        mp = {}
        for base_req in base_requires:
            if not base_req:
                continue
            mp.update(base_req)

        for req in requires:
            if not req:
                continue
            for k, v in req.items():
                if not mp.get(k) and v:
                    mp[k] = v

        for k, v in mp.items():
            res.append({k: v})
        if base_optional and optional:
            res.append({})
        return res

    def get_response_name(self, response: Type[Response], tags: list = ()):
        if response == Response:
            return Response.__name__
        if response in self.responses:
            for k, v in self.response_names.items():
                if v == response:
                    return k
        names = list(tags)
        names.append(response.name or get_obj_name(response))
        return '_'.join(names)

    def set_response(self, response: Type[Response], tags: list = ()):
        name = self.get_response_name(response, tags=tags)

        if response in self.responses:
            return name

        gen = self.get_generator(response, output=True)
        data = gen.generate_for_response(response)

        while name in self.response_names:
            resp = self.response_names.get(name)
            resp_data = self.responses.get(resp)
            if resp_data and str(resp_data) == str(data):
                # exact data
                return name
            # de-duplicate name
            name += '_1'

        self.responses[response] = data
        self.response_names[name] = response
        return name

    def parse_properties(self, props: Dict[str, ParserProperty]) -> Tuple[dict, dict, list]:
        params = {}
        media_types = {}
        body_params = {}
        body_params_required = []
        body_required = False
        body_description = ''
        auth_requirements = []

        for key, prop_holder in props.items():
            if not isinstance(prop_holder, ParserProperty):
                continue

            field = prop_holder.field
            prop = prop_holder.prop

            auth = None
            scope = []
            if isinstance(prop, User):
                scope = ['login']
                auth = prop.authentication
                if not prop.required:
                    auth_requirements.append({})
                    # empty object means optional requirement
            elif isinstance(prop, BaseAuthentication):
                # authentication:
                auth = prop

            generator = self.get_generator(field.type)

            if auth:
                security_name = auth.name
                security_schema = auth.openapi_scheme()
                if security_schema:
                    # todo: oauth2 scopes
                    self.security_schemas[security_name] = security_schema
                    auth_requirements.append({security_name: scope})
                continue

            if prop.__in__:
                # this prop is in the __in__
                if inspect.isclass(prop.__in__) and issubclass(prop.__in__, Property):
                    _in = prop.__in__.__ident__
                else:
                    _in = str(prop.__in__)

                if _in == 'body':
                    if field.is_required(generator.options):
                        body_params_required.append(key)
                    body_params[key] = generator.generate_for_field(field)
                elif _in in self.PARAMS_IN:
                    data = {
                        'in': _in,
                        'name': key,
                        'required': prop.required,
                        'schema': generator(),
                    }
                    if prop.description:
                        data['description'] = prop.description
                    if prop.deprecated:
                        data['deprecated'] = True

                    if isinstance(field.field, properties.RequestParam):
                        if field.field.style:
                            data.update(style=field.field.style)
                    if not unprovided(field.field.example):
                        data.update(example=field.field.example)
                    params[key] = data

            elif prop.__ident__ == 'body':
                schema = generator()
                # treat differently
                content_type = getattr(prop, 'content_type', None)
                if not content_type:
                    # guess
                    content_type = guess_content_type(schema)
                media_types[content_type] = {
                    'schema': schema
                }
                body_description = prop.description
                body_required = prop.required

            elif prop.__ident__ in self.PARAMS_IN:
                # all the params in this prop is in the __ident__
                schema = generator()
                schema_type = schema.get('type')
                if schema_type != 'object' and not schema.get('$ref'):
                    raise TypeError(f'Invalid object type: {field.type} for request property: '
                                    f'{repr(prop.__ident__)}, must be a object type, got {repr(schema_type)}')
                params[key] = {
                    'in': prop.__ident__,
                    'name': key,
                    'schema': schema,
                    'style': 'form',
                    'explode': True
                }

        if media_types:
            if body_params:
                for value in media_types.values():
                    schema: dict = value.get('schema')
                    if not schema:
                        continue
                    schema.setdefault('properties', {}).update(body_params)
        elif body_params:
            # content type is default to be json
            media_types = {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': body_params,
                        'required': body_params_required
                    }
                }
            }

        body = None
        if media_types:
            body = dict(
                content=media_types,
                description=body_description,
                required=body_required
            )
        return params, body, auth_requirements

    def from_endpoint(self, endpoint: Endpoint,
                      tags: list = (),
                      extra_params: dict = None,
                      extra_body: dict = None,
                      response_cls: Type[Response] = None,
                      extra_responses: dict = None,
                      extra_requires: list = None
                      ) -> dict:
        # https://spec.openapis.org/oas/v3.1.0#operationObject
        operation_names = list(tags) + [endpoint.name]
        operation_id = '_'.join(operation_names)

        params, body, requires = self.parse_properties(endpoint.wrapper.properties)
        responses = dict(extra_responses or {})

        rt = endpoint.parser.return_type
        # if isinstance(rt, LogicalType):
        #     # resolve multiple responses
        #     if inspect.isclass(rt) and issubclass(rt, Rule):
        #         pass
        #
        # else:
        if inspect.isclass(rt) and issubclass(rt, Response):
            resp = rt
        elif rt is not None:
            resp = (response_cls or Response)[rt]
        else:
            resp = response_cls or Response

        resp_name = self.set_response(resp, tags=tags)
        responses[resp.status or 200] = {'$ref': f'#/components/responses/{resp_name}'}

        if extra_params:
            # _params = dict(extra_params)
            # _params.update(params)
            params.update(extra_params)
            # endpoint params can override before hook params
            # the more front params should be exposed
        if extra_body:
            body = body or extra_body

        operation: dict = dict(
            operationId=operation_id,
            tags=tags,
            responses=responses,
            security=self.merge_requires(extra_requires, requires)
        )
        if params:
            operation.update(parameters=list(params.values()))
        if body and endpoint.method in HAS_BODY_METHODS:
            operation.update(requestBody=body)
        if endpoint.idempotent is not None:
            operation.update({'x-idempotent': endpoint.idempotent})
        if endpoint.ref:
            operation.update({'x-ref': endpoint.ref})
        return operation

    def from_route(self, route: APIRoute,
                   *routes: str,
                   tags: list = (),
                   params: dict = None,
                   response_cls: Type[Response] = None,
                   responses: dict = None,
                   requires: list = None) -> dict:
        # https://spec.openapis.org/oas/v3.1.0#pathItemObject
        new_routes = [*routes, route.route] if route.route else list(routes)
        new_tags = [*tags, route.name] if route.name else list(tags)
        path = self._path_join(*new_routes)
        route_data = {k: v for k, v in dict(
            summary=route.summary,
            description=route.description,
            deprecated=route.deprecated
        ).items() if v is not None}

        extra_body = None
        extra_params = {}
        extra_requires = []
        extra_responses = dict(responses or {})     # the deeper (close to the api response) is prior
        # before hooks
        for before in route.before_hooks:
            prop_params, body, before_requires = self.parse_properties(before.wrapper.properties)
            if body and not extra_body:
                extra_body = body
            extra_params.update(prop_params)
            extra_requires = self.merge_requires(extra_requires, before_requires)

        for after in route.after_hooks:
            if after.response:
                response_cls = after.response

        for error, hook in route.error_hooks.items():
            if hook.response:
                resp_name = self.set_response(hook.response, tags=tags)
                extra_responses[hook.response.status or 'default'] = {'$ref': f'#/components/responses/{resp_name}'}

        path_data = {}
        if route.is_endpoint:
            # generate endpoint data
            endpoint_data = self.from_endpoint(
                route.handler,
                # path_args=route.path_args,
                tags=tags,
                extra_params=extra_params,
                extra_body=extra_body,
                response_cls=response_cls,
                extra_responses=extra_responses,
                extra_requires=extra_requires
            )
            # inject data in the endpoint, not the route with probably other endpoints
            endpoint_data.update(route_data)
            method_data = {route.method: endpoint_data}

            path_data: dict = self.paths.get(path)
            if path_data:
                path_data.update(method_data)
            else:
                self.paths[path] = path_data = method_data
                if params:
                    path_data.update(parameters=list(params.values()))
            # responses
        else:
            common_params = dict(params or {})
            common_params.update(extra_params)
            core_data = self.from_api(
                route.handler, *new_routes,
                tags=new_tags,
                params=common_params,
                response_cls=response_cls,
                responses=extra_responses,
                requires=requires
            )
            if core_data:
                core_data.update(route_data)
                # only update the core methods route of the API (if have)

        return path_data

    def from_api(self, api: Type[API], *routes,
                 tags: list = (),
                 params: dict = None,
                 response_cls: Type[Response] = None,
                 responses: dict = None,
                 requires: list = None) -> Optional[dict]:
        if api.__external__:
            # external APIs will not participate in docs
            return None
        core_data = None
        extra_params = dict(params or {})
        prop_params, body, prop_requires = self.parse_properties(api._properties)
        extra_params.update(prop_params)

        response_cls = getattr(api, 'response', response_cls)

        for api_route in api._routes:
            if api_route.private:
                continue
            route_paths = self.from_route(
                api_route, *routes,
                tags=tags,
                params=extra_params,
                response_cls=response_cls,
                responses=responses,
                requires=self.merge_requires(requires, prop_requires)
            )
            if not api_route.route and api_route.method:
                # core api methods
                core_data = route_paths
                continue
        # props
        return core_data

"""
Generate client code based on OpenAPI document
"""
import inspect
import re

from .base import BaseClientGenerator
from utilmeta.core.api.specs.openapi import OpenAPISchema
import utype
from utype.specs.json_schema import JsonSchemaParser, JsonSchemaGroupParser
from utype.specs.python import PythonCodeGenerator
from utype.parser.rule import LogicalType, Rule
from utilmeta.utils import valid_url
import json
from typing import Tuple, List, Union, Optional, Type
from utilmeta.core.response import Response
from utilmeta.core import request


def tab_for(content: str, tabs: int = 1) -> str:
    return '\n'.join([f'%s{line}' % ('\t' * tabs) for line in content.splitlines()])


class OpenAPIClientGenerator(BaseClientGenerator):
    __spec__ = 'openapi'
    __version__ = '3.1.0'
    FORMATS = ['json', 'yaml']
    PARAMS_IN = ['path', 'query', 'header', 'cookie']
    PARAMS_MAP = {
        'path': request.PathParam,
        'query': request.QueryParam,
        'header': request.HeaderParam,
        'cookie': request.CookieParam,
        'body': request.BodyParam,
    }

    # None -> dict
    # json -> json string
    # yml -> yml string

    openapi: OpenAPISchema

    schema_parser_cls = JsonSchemaParser
    schema_group_parser_cls = JsonSchemaGroupParser
    python_generator_cls = PythonCodeGenerator

    NON_NAME_REG = '[^A-Za-z0-9]+'

    ref_prefix = '#/components/schemas'
    def_prefix = 'schemas'

    def __init__(self, document: dict):
        if not isinstance(document, dict) or not document.get(self.__spec__):
            raise ValueError(f'Invalid openapi document: {document}')
        super().__init__(document)
        try:
            self.openapi = OpenAPISchema(document)
        except utype.exc.ParseError as e:
            raise e.__class__(f'Invalid openapi document: {e}') from e
        self.refs = {}

    def get_schema_parser(self, json_schema: dict, name: str = None, description: str = None):
        return self.schema_parser_cls(
            json_schema,
            name=name,
            description=description,
            refs=self.refs,
            ref_prefix=self.ref_prefix,
            def_prefix=self.def_prefix,
        )

    def get_def_name(self, ref: str) -> str:
        ref_name = ref.lstrip(self.ref_prefix)
        return self.def_prefix + ref_name

    @classmethod
    def generate_from(cls, url_or_file: str):
        url = valid_url(url_or_file, raise_err=False)
        if url:
            pass
        else:
            file_path = url_or_file
            content = open(file_path, 'r').read()
            if file_path.endswith(',yml') or file_path.endswith('.yaml'):
                from utilmeta.utils import check_requirement
                check_requirement('pyyaml', install_when_require=True)
                import yaml
                document = yaml.safe_load(content)
            else:
                # try to load with json
                try:
                    document = json.loads(content)
                except json.decoder.JSONDecodeError as e:
                    raise ValueError(f'Invalid openapi document at {repr(file_path)}: {e}') from e
            return cls(document)

    def generate(self):
        pass


    def generate_schemas(self):
        schemas = self.openapi.components.schemas
        if not schemas:
            return ''
        schemas_parser = self.schema_group_parser_cls(
            schemas=schemas,
            ref_prefix=self.ref_prefix,
            def_prefix=self.def_prefix
        )
        schemas_refs = schemas_parser.parse()
        group_lines = ['class schemas:\n']
        for ref, schema_cls in schemas_refs.items():
            schema_content = self.python_generator_cls(schema_cls)()
            group_lines.append(tab_for(schema_content, tabs=1))
            group_lines.append('\n')
        return ''.join(group_lines)

    def generate_responses(self):
        responses = self.openapi.components.responses
        if not responses:
            return ''
        group_lines = ['class responses:\n']
        for name, response in responses.items():
            response_content = self.generate_response(response, name=name)
            group_lines.append(tab_for(response_content, tabs=1))
            group_lines.append('\n\n')
        return ''.join(group_lines)

    def get_headers_schema(self, headers: dict, name: str):
        return self.get_schema_parser({
            'type': 'object',
            'properties': {key: val.get('schema') for key, val in headers.items()},
            'required': [key for key in headers.keys() if headers[key].get('required')]
        },
            name=name
        )()

    def generate_response(self, response: dict, name: str):
        content = response.get('content') or {}
        headers = response.get('headers') or {}
        description = response.get('description') or ''

        if not content:
            pass

        headers_content = None
        headers_annotation = None
        resp_name = re.sub(self.NON_NAME_REG, '_', name)

        if headers:
            headers_schema = self.get_headers_schema(headers, name=resp_name + 'Headers')
            headers_content = self.python_generator_cls(headers_schema)()
            headers_annotation = headers_schema.__name__

        # single_content = len(content) == 1
        resp_lines = [
            f'class {resp_name}(Response):',
        ]
        if description:
            resp_lines.append(f'\t"""{description}"""')

        result_annotations = []
        result_contents = []
        content_types = []

        for content_type, content_obj in content.items():
            if not content_obj or not isinstance(content_obj, dict):
                continue
            content_schema = content_obj.get('schema')
            content_description = content_obj.get('description')
            result_annotation, schema_contents = self.get_schema_annotations(
                content_schema,
                name=resp_name + 'Result',
                description=content_description
            )
            if result_annotation:
                result_annotations.append(result_annotation)
            if schema_contents:
                result_contents.extend(schema_contents)
            content_types.append(content_type)

        if headers_content:
            resp_lines.append(tab_for(headers_content, tabs=1) + '\n')
        if result_contents:
            for result_content in result_contents:
                resp_lines.append(tab_for(result_content, tabs=1) + '\n')

        if len(content_types) == 1:
            resp_lines.append(f'\tcontent_type = {repr(content_types[0])}')
        if headers_annotation:
            resp_lines.append(f'\theaders: {headers_annotation}')
        if result_annotations:
            result_annotation = result_annotations[0] if len(result_annotations) == 1 \
                else f'Union[%s]' % (', '.join(result_annotations))
            resp_lines.append(f'\tresult: {result_annotation}')

        if len(resp_lines) == 1:
            resp_lines.append('\tpass')
        return '\n'.join(resp_lines)

    def get_schema_annotations(self, json_schema: dict,
                               name: str = None,
                               description: str = None) -> Tuple[str, List[str]]:
        if not json_schema:
            return '', []
        # Union[X1, X2]
        # Optional[X1]
        # List[...]
        # Tuple[...]
        # Dict[...]
        # ClassName
        ref = json_schema.get('$ref')
        if ref:
            return repr(self.get_def_name(ref)), []
        schema = self.get_schema_parser(
            json_schema=json_schema,
            name=name,
            description=description
        )()

        parser = self.python_generator_cls(schema)
        args = []
        if isinstance(schema, LogicalType):
            if schema.combinator:
                args = schema.args
            elif isinstance(schema, Rule):
                args = schema.__args__
        if not args:
            args = [schema]

        annotation = parser.generate_for_type(schema, with_constraints=False, annotation=True)
        schema_contents = [parser.generate_for_type(arg, with_constraints=True, annotation=False) for arg in args]
        return annotation, schema_contents

    def get_parameter(self, param: dict) -> Optional[inspect.Parameter]:
        ref = param.get('$ref')
        if ref:
            param: dict = self.openapi.components.parameters.get(ref)
        if not param:
            return None

        name = param.get('name')
        _in = param.get('in')
        schema = param.get('schema')
        description = param.get('description')
        required = param.get('required')

        param_cls = self.PARAMS_MAP.get(_in)
        parser = self.schema_parser_cls(schema)
        field_type, field = parser.parse_field(
            schema,
            description=description,
            required=required,
            field_cls=param_cls
        )
        if not field.__spec_kwargs__:
            field = utype.unprovided
        return inspect.Parameter(
            name=name,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=field_type,
            default=field
        )

    @classmethod
    def get_body_param_name(cls, content_type: str, excludes: List[str] = None):
        name = 'body'
        if 'json' in content_type:
            name = 'data'
        elif 'form' in content_type:
            name = 'form'
        elif 'html' in content_type:
            name = 'html'
        elif 'xml' in content_type:
            name = 'xml'
        elif 'text' in content_type:
            name = 'text'
        elif 'stream' in content_type:
            name = 'file'
        elif 'image' in content_type:
            name = 'image'
        elif 'audio' in content_type:
            name = 'audio'
        elif 'video' in content_type:
            name = 'video'
        while excludes and name in excludes:
            if name == 'data':
                name = 'json'
            else:
                name = name + '_data'
        return name

    def get_body_parameters(self, body: dict, excludes: List[str] = None) -> List[inspect.Parameter]:
        body_required = body.get('required')
        body_content = body.get('content') or {}
        body_description = body.get('description')

        excludes = list(excludes or [])
        body_params = []

        for content_type, content in body_content.items():
            if not isinstance(content, dict) or not content:
                continue

            param_name = self.get_body_param_name(content_type, excludes=excludes)
            excludes.append(param_name)
            content_example = content.get('example')
            content_schema = content.get('schema')

            parser = self.schema_parser_cls(content_schema)
            field_type, field = parser.parse_field(
                content_schema,
                description=body_description,
                required=body_required and len(body_required) >= 1,
                example=content_example,
                field_cls=request.Body
            )

            if not field.__spec_kwargs__:
                field = utype.unprovided
            body_params.append(inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=field_type,
                default=field
            ))

        return body_params

    def get_response(self, response: dict, name: str) -> Optional[Type[Response]]:
        ref = response.get('$ref')
        if ref:
            response: dict = self.openapi.components.responses.get(ref)
        if not response:
            return None

        resp_name = re.sub(self.NON_NAME_REG, '_', name)
        content = response.get('content') or {}
        headers = response.get('headers') or {}
        description = response.get('description') or ''
        attrs = {}
        annotations = {}
        content_types = []

        if headers:
            headers_name = resp_name + 'Headers'
            headers_schema = self.get_headers_schema(headers, name=resp_name)
            attrs.update({headers_name: headers_schema})
            annotations.update({'headers': headers_schema})

        for content_type, content_obj in content.items():
            if not content_obj or not isinstance(content_obj, dict):
                continue
            content_schema = content_obj.get('schema')
            content_description = content_obj.get('description')
            result_name = resp_name + 'Result'
            schema = self.get_schema_parser(
                json_schema=content_schema,
                name=result_name,
                description=content_description
            )()
            attrs.update({result_name: schema})
            annotations.update({'result': schema})
            content_types.append(content_type)

        if description:
            attrs.update(__doc__=description)
        if len(content_types) == 1:
            attrs.update(content_type=content_types[0])
        if annotations:
            attrs.update(__annotations__=annotations)

        resp_cls: Type[Response] = type(resp_name, (Response,), attrs)  # noqa
        return resp_cls

    def get_responses_annotation(self, responses: dict):
        response_args = []
        for name, resp in responses.items():
            response_cls = self.get_response(resp, name=name)
            if response_cls:
                response_args.append(response_cls)
        if not response_args:
            return None
        if len(response_args) == 1:
            return response_args[0]
        return Union[tuple(response_args)]

    def get_operation_function(self, operation: dict):
        def f():
            pass

        func_name = operation.get('operationId')
        parameters = operation.get('parameters')
        body = operation.get('requestBody')
        responses = operation.get('responses')

        func_parameters = []
        for param in parameters:
            func_param = self.get_parameter(param)
            if not func_param:
                continue
            func_parameters.append(func_param)

        if body and isinstance(body, dict):
            body_parameters = self.get_body_parameters(
                body,
                excludes=[param.name for param in func_parameters]
            )
            func_parameters.extend(body_parameters)

        return_annotation = self.get_responses_annotation(responses)
        f.__name__ = func_name
        f.__signature__ = inspect.signature(f).replace(
            parameters=func_parameters,
            return_annotation=return_annotation
        )
        return f

    def generate_path_item(self, method: str, path: str, operation: dict):
        decorator = f'@api.{method}({repr(path)})'
        func = self.get_operation_function(operation)
        func_content = self.python_generator_cls(func)()
        # todo: get schemas
        return decorator + '\n' + func_content + '\n'

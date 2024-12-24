"""
Generate client code based on OpenAPI document
"""
import inspect
import keyword
import re

from .base import BaseClientGenerator
from utilmeta.core.api.specs.openapi import OpenAPISchema
import utype
from utype.specs.json_schema import JsonSchemaParser, JsonSchemaGroupParser
from utype.specs.python import PythonCodeGenerator
from utype.parser.rule import LogicalType, Rule
from utilmeta.utils import (
    valid_url,
    HTTP_METHODS_LOWER,
    valid_attr,
    time_now,
    json_dumps,
)
import json
from typing import Tuple, List, Union, Optional
from utilmeta.core import request
from utype.types import ForwardRef


def tab_for(content: str, tabs: int = 1) -> str:
    return "\n".join([f"%s{line}" % ("\t" * tabs) for line in content.splitlines()])


class OpenAPIClientGenerator(BaseClientGenerator):
    __spec__ = "openapi"
    __version__ = "3.1.0"
    FORMATS = ["json", "yaml"]
    PARAMS_IN = ["path", "query", "header", "cookie"]
    PARAMS_MAP = {
        "path": request.PathParam,
        "query": request.QueryParam,
        "header": request.HeaderParam,
        "cookie": request.CookieParam,
        "body": request.BodyParam,
    }

    # None -> dict
    # json -> json string
    # yml -> yml string

    openapi: OpenAPISchema

    schema_parser_cls = JsonSchemaParser
    schema_group_parser_cls = JsonSchemaGroupParser
    python_generator_cls = PythonCodeGenerator

    NON_NAME_REG = "[^A-Za-z0-9]+"
    JSON = "application/json"

    ref_prefix = "#/components"
    schema_ref_prefix = "#/components/schemas"
    response_ref_prefix = "#/components/responses"
    schema_def_prefix = "schemas"
    response_def_prefix = "responses"

    client_class_name = "APIClient"
    IMPORTS = """from utilmeta.core import api, cli, response, request
import utype
from utype.types import *
"""

    def __init__(
        self,
        document: dict,
        space_ident: bool = False,
        black_format: bool = False,
        split_body_params: bool = False,
    ):
        if not isinstance(document, dict) or not document.get(self.__spec__):
            raise ValueError(f"Invalid openapi document: {document}")
        super().__init__(document)
        try:
            self.openapi = OpenAPISchema(document)
        except utype.exc.ParseError as e:
            raise e.__class__(f"Invalid openapi document: {e}") from e
        self.ref_prefix = self.ref_prefix.rstrip("/") + "/"
        self.schema_ref_prefix = self.schema_ref_prefix.rstrip("/") + "/"
        self.response_ref_prefix = self.response_ref_prefix.rstrip("/") + "/"
        self.schema_def_prefix = (
            (self.schema_def_prefix.rstrip(".") + ".") if self.schema_def_prefix else ""
        )
        self.response_def_prefix = (
            (self.response_def_prefix.rstrip(".") + ".")
            if self.response_def_prefix
            else ""
        )
        self.schema_refs = dict(self.openapi.components.schemas)
        self.responses_refs = dict(self.openapi.components.responses)
        self.space_ident = space_ident
        self.black_format = black_format
        self.split_body_params = split_body_params

    def get_schema_parser(
        self,
        json_schema: dict,
        name: str = None,
        description: str = None,
        force_forward_ref: bool = True,
    ):
        return self.schema_parser_cls(
            json_schema,
            name=name,
            description=description,
            refs=self.schema_refs,
            ref_prefix=self.schema_ref_prefix,
            def_prefix=self.schema_def_prefix,
            force_forward_ref=force_forward_ref,
        )

    def get_code_parser(self, t):
        return self.python_generator_cls(t)

    def get_def_name(self, ref: str) -> str:
        if ref.startswith(self.schema_ref_prefix):
            ref = ref[len(self.schema_ref_prefix) :]
        ref_name = self.get_param_name(ref)
        return self.schema_def_prefix + ref_name

    def get_response_def_name(self, ref: str) -> str:
        if ref.startswith(self.response_ref_prefix):
            ref = ref[len(self.response_ref_prefix) :]
        ref_name = self.get_param_name(ref)
        return self.response_def_prefix + ref_name

    def register_response_ref(self, name: str, schema: dict) -> str:
        i = 1
        cls_name = name
        while name in self.responses_refs:
            name = f"{cls_name}_{i}"
            i += 1
        self.responses_refs[name] = schema
        return self.get_response_def_name(name)

    def get_ref_object(self, ref: str) -> Optional[dict]:
        if ref.startswith(self.ref_prefix):
            ref = ref[len(self.ref_prefix) :]

        ref_routes = ref.strip("/").split("/")
        obj = self.openapi.components
        for route in ref_routes:
            if not obj:
                return None
            obj = obj.get(route)
        return obj

    @classmethod
    def generate_from(cls, url_or_file: str) -> "OpenAPIClientGenerator":
        url = valid_url(url_or_file, raise_err=False)
        if url:
            from utilmeta.core.api.specs.openapi import get_docs_from_url

            document = get_docs_from_url(url)
            if document:
                return cls(document)
            raise ValueError(f"Invalid document url: {url}")
        else:
            file_path = url_or_file
            content = open(file_path, "r").read()
            if file_path.endswith(",yml") or file_path.endswith(".yaml"):
                from utilmeta.utils import requires

                requires(yaml="pyyaml")
                import yaml

                document = yaml.safe_load(content)
            else:
                # try to load with json
                try:
                    document = json.loads(content)
                except json.decoder.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid openapi document at {repr(file_path)}: {e}"
                    ) from e
            return cls(document)

    def generate(self):
        base_url = self.openapi.servers[0].url if self.openapi.servers else None
        client_content = self.generate_paths()
        responses_content = self.generate_responses()
        schemas_content = self.generate_schemas()
        from utilmeta import __version__

        content = f"""# Generated by UtilMeta {__version__} on {str(time_now().strftime("%Y-%m-%d %H:%M"))}
# generator spec: {self.__spec__} {self.__version__}
# generator class: utilmeta.core.cli.specs.openapi.OpenAPIClientGenerator
{self.IMPORTS}
        
{schemas_content}

{responses_content}

{client_content}
client = {self.client_class_name}(
    base_url={repr(base_url)}
)
"""
        if self.space_ident:
            content.replace("\t", " " * 4)
        if self.black_format:
            try:
                import black
            except (NameError, ModuleNotFoundError):
                pass
            else:
                content = black.format_str(content, mode=black.FileMode())
        return content

    @classmethod
    def represent_data(cls, data):
        return json_dumps(data, sort_keys=True, indent="\t")

    def generate_paths(self):
        operations = []
        for path, methods in self.openapi.paths.items():
            methods = self.get_schema(methods)
            if not methods:
                continue
            summary = methods.get("summary")
            description = methods.get("description")
            path_parameters = methods.get("parameters")

            for method, operation in methods.items():
                if str(method).lower() in HTTP_METHODS_LOWER:
                    operations.append(
                        tab_for(
                            self.generate_path_item(
                                method=method,
                                path=path,
                                operation=operation,
                                summary=summary,
                                description=description,
                                parameters=path_parameters,
                            ),
                            tabs=1,
                        )
                        + "\n"
                    )
        client_lines = ["class APIClient(cli.Client):"]
        if self.openapi.info:
            client_lines.append(
                tab_for(f"__info__ = {self.represent_data(self.openapi.info)}", tabs=1)
            )
        if self.openapi.servers:
            client_lines.append(
                tab_for(
                    f"__servers__ = {self.represent_data(self.openapi.servers)}", tabs=1
                )
            )
        client_lines.extend(operations)
        return "\n".join(client_lines)

    def generate_schemas(self):
        schemas = self.schema_refs
        if not schemas:
            return ""
        schemas_parser = self.schema_group_parser_cls(
            schemas=schemas,
            ref_prefix=self.schema_ref_prefix,
            def_prefix=self.schema_def_prefix,
        )
        schemas_refs = schemas_parser.parse()
        group_lines = ["class schemas:"]
        for ref, schema_cls in schemas_refs.items():
            schema_content = self.get_code_parser(schema_cls)()
            group_lines.append(tab_for(schema_content, tabs=1) + "\n")
        return "\n".join(group_lines)

    def generate_responses(self):
        responses = self.responses_refs
        if not responses:
            return ""
        group_lines = ["class responses:\n"]
        for name, response in responses.items():
            response_content = self.generate_response(response, name=name)
            group_lines.append(tab_for(response_content, tabs=1))
            group_lines.append("\n\n")
        return "".join(group_lines)

    def get_headers_schema(self, headers: dict, name: str):
        return self.get_schema_parser(
            {
                "type": "object",
                "properties": {key: val.get("schema") for key, val in headers.items()},
                "required": [
                    key for key in headers.keys() if headers[key].get("required")
                ],
            },
            name=name,
            force_forward_ref=False,
        )()

    def get_schema(self, schema: dict):
        if not schema:
            return {}
        ref = schema.get("$ref")
        if ref:
            return self.get_ref_object(ref)
        return schema

    def generate_response(self, response: dict, name: str):
        content = response.get("content") or {}
        headers = response.get("headers") or {}
        description = response.get("description") or ""
        response_name = response.get("x-response-name") or ""

        headers_content = None
        headers_annotation = None
        resp_name = re.sub(self.NON_NAME_REG, "_", name).strip("_")

        if headers:
            headers_schema = self.get_headers_schema(
                headers, name=resp_name + "Headers"
            )
            headers_content = self.get_code_parser(headers_schema)()
            headers_annotation = headers_schema.__name__

        # single_content = len(content) == 1
        resp_lines = [
            f"class {resp_name}(response.Response):",
        ]
        if description:
            resp_lines.append(f'\t"""{description}"""')
        if response_name:
            resp_lines.append(f"\tname = {repr(str(response_name))}")

        result_annotations = []
        result_contents = []
        content_types = []

        for content_type, content_obj in content.items():
            if not content_obj or not isinstance(content_obj, dict):
                continue
            content_schema = content_obj.get("schema") or {}
            content_description = content_obj.get("description")
            result_schema = content_schema
            if self.JSON in content_type:
                # HANDLE RESPONSE KEYS
                schema = dict(self.get_schema(content_schema))
                if schema.get("type") == "object":
                    props = schema.get("properties") or {}
                    result_key = schema.get("x-response-result-key") or ""
                    message_key = schema.get("x-response-message-key") or ""
                    state_key = schema.get("x-response-state-key") or ""
                    count_key = schema.get("x-response-count-key") or ""
                    if result_key:
                        result_schema = props.get(result_key)
                        resp_lines.append(f"\tresult_key = {repr(str(result_key))}")
                    if message_key:
                        resp_lines.append(f"\tmessage_key = {repr(str(message_key))}")
                    if state_key:
                        resp_lines.append(f"\tstate_key = {repr(str(state_key))}")
                    if count_key:
                        resp_lines.append(f"\tcount_key = {repr(str(count_key))}")

            result_annotation, schema_contents = self.get_schema_annotations(
                result_schema,
                name=resp_name + "Result",
                description=content_description,
            )
            if result_annotation:
                result_annotations.append(result_annotation)
            if schema_contents:
                result_contents.extend(schema_contents)
            content_types.append(content_type)

        if headers_content:
            resp_lines.append(tab_for(headers_content, tabs=1) + "\n")
        if result_contents:
            for result_content in result_contents:
                resp_lines.append(tab_for(result_content, tabs=1) + "\n")

        if len(content_types) == 1:
            resp_lines.append(f"\tcontent_type = {repr(content_types[0])}")
        if headers_annotation:
            resp_lines.append(f"\theaders: {headers_annotation}")
        if result_annotations:
            result_annotation = (
                result_annotations[0]
                if len(result_annotations) == 1
                else f"Union[%s]" % (", ".join(result_annotations))
            )
            resp_lines.append(f"\tresult: {result_annotation}")

        if len(resp_lines) == 1:
            resp_lines.append("\tpass")
        return "\n".join(resp_lines)

    def get_schema_annotations(
        self, json_schema: dict, name: str = None, description: str = None
    ) -> Tuple[str, List[str]]:
        if not json_schema:
            return "", []
        # Union[X1, X2]
        # Optional[X1]
        # List[...]
        # Tuple[...]
        # Dict[...]
        # ClassName
        ref = json_schema.get("$ref")
        if ref:
            return repr(self.get_def_name(ref)), []
        schema = self.get_schema_parser(
            json_schema=json_schema,
            name=self.get_param_name(name),
            description=description,
            force_forward_ref=False,
        )()

        parser = self.get_code_parser(schema)
        args = []
        if isinstance(schema, LogicalType):
            if schema.combinator:
                args = schema.args
            elif issubclass(schema, Rule):
                args = schema.__args__
        if not args:
            args = [schema]

        annotation = parser.generate_for_type(
            schema, with_constraints=False, annotation=True
        )
        schema_contents = [
            parser.generate_for_type(arg, with_constraints=True, annotation=False)
            for arg in args
            if self.required_generate(arg)
        ]
        return annotation, schema_contents

    @classmethod
    def required_generate(cls, t):
        parser = getattr(t, "__parser__", None)
        if parser:
            from utype.parser.cls import ClassParser

            if isinstance(parser, ClassParser):
                return True
        elif isinstance(t, LogicalType) and issubclass(t, Rule):
            if t.__origin__:
                if cls.required_generate(t.__origin__):
                    return True
            elif t.__args__:
                if any([cls.required_generate(arg) for arg in t.__args__]):
                    return True
        return False

    @classmethod
    def get_param_name(cls, name: str, excludes: list = None):
        name = re.sub(cls.NON_NAME_REG, "_", name).strip("_")
        if keyword.iskeyword(name):
            name += "_value"
        if excludes:
            i = 1
            origin = name
            while name in excludes:
                name = f"{origin}_{i}"
                i += 1
        return name

    def get_parameter(
        self, param: dict, excludes: list = None
    ) -> Optional[inspect.Parameter]:
        param: dict = self.get_schema(param)
        if not param:
            return None

        name = param.get("name")
        _in = param.get("in")
        description = param.get("description")
        required = param.get("required")
        schema = self.get_schema(param.get("schema"))
        param_cls = self.PARAMS_MAP.get(_in)
        parser = self.get_schema_parser(schema)
        attname = schema.get("x-var-name") or name
        alias = None
        if not valid_attr(attname) or excludes and attname in excludes:
            attname = self.get_param_name(attname, excludes)
        if attname != name:
            alias = name
        elif _in == "header":
            alias = name

        field_type, field = parser.parse_field(
            schema,
            description=description,
            required=required,
            field_cls=param_cls,
            alias=alias,
        )
        if not field.__spec_kwargs__:
            if param_cls == request.QueryParam:
                field = inspect.Parameter.empty
            else:
                field = param_cls
        return inspect.Parameter(
            name=attname,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=field_type,
            default=field,
        )

    @classmethod
    def get_body_param_name(cls, content_type: str, excludes: List[str] = None):
        name = "body"
        if "json" in content_type:
            name = "data"
        elif "form" in content_type:
            name = "form"
        elif "html" in content_type:
            name = "html"
        elif "xml" in content_type:
            name = "xml"
        elif "text" in content_type:
            name = "text"
        elif "stream" in content_type:
            name = "file"
        elif "image" in content_type:
            name = "image"
        elif "audio" in content_type:
            name = "audio"
        elif "video" in content_type:
            name = "video"
        while excludes and name in excludes:
            if name == "data":
                name = "json"
            else:
                name = name + "_data"
        return name

    def get_body_parameters(
        self, body: dict, endpoint_name: str = None, excludes: List[str] = None
    ) -> List[inspect.Parameter]:
        body = self.get_schema(body)
        if not body:
            return []
        body_required = body.get("required")
        body_content = body.get("content") or {}
        body_description = body.get("description")

        excludes = list(excludes or [])
        body_params = []

        for content_type, content in body_content.items():
            if not isinstance(content, dict) or not content:
                continue

            param_name = self.get_body_param_name(content_type, excludes=excludes)
            schema_name = (
                "".join(
                    [v.capitalize() for v in endpoint_name.split("_")]
                    + [param_name.capitalize()]
                )
                if endpoint_name
                else param_name.capitalize()
            )
            content_example = content.get("example")
            content_schema = content.get("schema") or {}

            if self.split_body_params and self.JSON in content_type:
                # if content_schema is $ref, we will directly use Body instead of split
                if content_schema.get("type") == "object":
                    schema_props = content_schema.get("properties")
                    if schema_props:
                        schema_required = content_schema.get("required") or []
                        for key, prop in schema_props.items():
                            schema_key_name = schema_name + str(key).capitalize()
                            prop_parser = self.get_schema_parser(
                                prop,
                                name=schema_key_name,
                            )
                            field_required = key in schema_required
                            field_type, field = prop_parser.parse_field(
                                prop,
                                description=body_description,
                                required=field_required,
                                field_cls=request.BodyParam,
                                name=schema_key_name,
                            )
                            attname = self.get_param_name(key, excludes=excludes)
                            excludes.append(attname)
                            body_params.append(
                                inspect.Parameter(
                                    name=attname,
                                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                    annotation=field_type,
                                    default=field,
                                )
                            )
                        continue
            excludes.append(param_name)
            parser = self.get_schema_parser(
                content_schema,
                name=schema_name,
            )
            field_type, field = parser.parse_field(
                content_schema,
                description=body_description,
                required=(body_required and len(body_content) <= 1) or False,
                example=content_example,
                field_cls=request.Body,
                content_type=content_type,
                name=schema_name,
            )

            if not field.__spec_kwargs__:
                field = request.Body
            body_params.append(
                inspect.Parameter(
                    name=param_name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=field_type,
                    default=field,
                )
            )

        return body_params

    # def get_response(self, response: dict, name: str) -> Optional[Type[Response]]:
    #     ref = response.get('$ref')
    #     if ref:
    #         response: dict = self.get_ref_object(ref)
    #
    #     if not response:
    #         return None
    #
    #     resp_name = re.sub(self.NON_NAME_REG, '_', name)
    #     content = response.get('content') or {}
    #     headers = response.get('headers') or {}
    #     description = response.get('description') or ''
    #     attrs = {}
    #     annotations = {}
    #     content_types = []
    #
    #     if headers:
    #         headers_name = resp_name + 'Headers'
    #         headers_schema = self.get_headers_schema(headers, name=resp_name)
    #         attrs.update({headers_name: headers_schema})
    #         annotations.update({'headers': headers_schema})
    #
    #     for content_type, content_obj in content.items():
    #         if not content_obj or not isinstance(content_obj, dict):
    #             continue
    #         content_schema = content_obj.get('schema')
    #         content_description = content_obj.get('description')
    #         result_name = resp_name + 'Result'
    #         schema = self.get_schema_parser(
    #             json_schema=content_schema,
    #             name=result_name,
    #             description=content_description,
    #             force_forward_ref=False
    #         )()
    #         attrs.update({result_name: schema})
    #         annotations.update({'result': schema})
    #         content_types.append(content_type)
    #
    #     if description:
    #         attrs.update(__doc__=description)
    #     if len(content_types) == 1:
    #         attrs.update(content_type=content_types[0])
    #     if annotations:
    #         attrs.update(__annotations__=annotations)
    #
    #     resp_cls: Type[Response] = type(resp_name, (Response,), attrs)  # noqa
    #     return resp_cls

    def get_responses_annotation(self, responses: dict, endpoint_name: str = None):
        response_args = []
        for name, resp in sorted(responses.items(), key=lambda x: x[0]):
            # response_cls = self.get_response(resp, name=name)
            # if response_cls:
            #     response_args.append(response_cls)
            if not resp:
                continue
            ref = resp.get("$ref")
            if ref:
                resp_def_name = self.get_response_def_name(ref)
            else:
                resp_name = (
                    "".join(
                        [v.capitalize() for v in endpoint_name.split("_")]
                        + ["Response"]
                    )
                    if endpoint_name
                    else "Response"
                )
                resp_def_name = self.register_response_ref(name=resp_name, schema=resp)
            suffix = f"[{name}]" if name != "default" else ""
            response_args.append(ForwardRef(resp_def_name + suffix))
        response_args.append(ForwardRef("response.Response"))
        # if not response_args:
        #     return None
        if len(response_args) == 1:
            return response_args[0]
        return Union[tuple(response_args)]

    def get_operation_function(self, operation: dict, path_parameters: list = None):
        func_name = operation.get("operationId")
        parameters = operation.get("parameters") or []
        body = operation.get("requestBody")
        responses = operation.get("responses")

        func_parameters = [
            inspect.Parameter(
                name="self",
                kind=inspect.Parameter.POSITIONAL_ONLY,
            )
        ]

        if path_parameters:
            parameters.extend(path_parameters)

        func_args = ["self"]
        if parameters:
            for param in parameters:
                func_param = self.get_parameter(param, excludes=func_args)
                if not func_param:
                    continue
                func_args.append(func_param.name)
                func_parameters.append(func_param)

        if body and isinstance(body, dict):
            body_parameters = self.get_body_parameters(
                body,
                endpoint_name=func_name,
                excludes=[param.name for param in func_parameters],
            )
            func_parameters.extend(body_parameters)

        return_annotation = self.get_responses_annotation(responses)

        def f() -> return_annotation:
            pass

        f.__name__ = func_name
        f.__qualname__ = f"{self.client_class_name}.{func_name}"
        f.__signature__ = inspect.signature(f).replace(
            parameters=func_parameters,
        )
        return f

    def generate_path_item(
        self,
        method: str,
        path: str,
        operation: dict,
        summary: str = None,
        description: str = None,
        parameters: list = None,
    ):
        api_kwargs = []
        for key in ["tags", "summary", "description", "deprecated", "security"]:
            val = operation.get(key) or locals().get(key)
            if val is not None:
                api_kwargs.append(f"{key}={repr(operation[key])}")
        api_kwargs_str = ", ".join(api_kwargs)
        decorator = f"@api.{method}({repr(path)}%s)" % (
            (", " + api_kwargs_str) if api_kwargs else ""
        )
        func = self.get_operation_function(operation, path_parameters=parameters)
        func_content = self.get_code_parser(func)()
        # todo: get schemas
        return decorator + "\n" + func_content + "\n"

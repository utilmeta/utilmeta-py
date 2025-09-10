from utype.parser.base import BaseParser
from utype.parser.field import ParserField
from utype.utils.datastructures import unprovided
from utype import Field
from typing import List, Union, Type, Dict
import inspect
from functools import partial
from contextvars import ContextVar


class ContextPropertySwitch(Exception):
    pass


class ParserProperty:
    def __init__(self, prop: Union[Type["Property"], "Property"], field: ParserField):
        self.prop = prop
        self.field = field
        self.get = partial(self.prop.getter, field=self.field)
        self.set = partial(self.prop.setter, field=self.field)
        self.delete = partial(self.prop.deleter, field=self.field)

    @property
    def name(self):
        return self.field.name

    @property
    def attname(self):
        return self.field.attname

    # @property
    # def get(self):
    #     return partial(self.prop.getter, field=self.field)
    #
    # @property
    # def set(self):
    #     return partial(self.prop.setter, field=self.field)
    #
    # @property
    # def delete(self):
    #     return partial(self.prop.deleter, field=self.field)


class Property(Field):
    __instance_cls__ = ParserProperty
    __in__ = None
    __key__ = None
    __type__ = None
    __ident__ = None
    __exclusive__ = False
    __private__ = False
    __no_default__ = None

    @classmethod
    def getter(cls, obj, field: ParserField = None):
        return obj

    @classmethod
    def setter(cls, obj, value, field: ParserField = None):
        return

    @classmethod
    def deleter(cls, obj, field: ParserField = None):
        return

    def init(self, field: ParserField):
        return self.__instance_cls__(self, field)


class ContextProperty(Property):
    def __init__(self, context_var: ContextVar, **kwargs):
        self.context_var = context_var
        super().__init__(**kwargs)

    def getter(self, obj, field: ParserField = None):
        return self.context_var.get()

    def setter(self, obj, value, field: ParserField = None):
        self.context_var.set(value)


class DuplicateContextProperty(ValueError):
    def __init__(self, msg="", ident: str = None):
        super().__init__(msg)
        self.ident = ident


class ContextWrapper:
    """
    A universal context parser, often used to process Request context
    """

    context_cls = object
    default_property = None

    def __init__(
        self,
        parser: BaseParser,
        default_properties: dict = None,
        excluded_names: List[str] = None,
    ):
        properties = {}
        attrs = {}
        ident_props = {}
        for key, val in parser.fields.items():
            if excluded_names and key in excluded_names:
                continue
            if isinstance(val.field, Property):
                prop = val.field
            elif default_properties and key in default_properties:
                prop = default_properties[key]()
            else:
                prop = None
                # detect property from type input including Union and Optional
                for origin in val.input_origins:
                    prop_field = getattr(origin, "__field__", None)
                    if prop_field:
                        if isinstance(prop_field, Property):
                            prop = prop_field
                            break
                        elif inspect.isclass(prop_field) and issubclass(
                            prop_field, Property
                        ):
                            prop = prop_field()
                            break
                if not prop:
                    if self.default_property:
                        # fallback to default
                        prop = self.default_property()
                    else:
                        continue

            if prop.__ident__:
                if prop.__ident__ in ident_props:
                    if prop.__exclusive__:
                        raise DuplicateContextProperty(
                            f'duplicated {repr(prop.__ident__)} properties',
                            ident=prop.__ident__
                        )
                ident_props.setdefault(str(prop.__ident__), []).append(prop)

            properties[key] = attrs[val.attname] = self.init_prop(prop, val)

        self.properties: Dict[str, ParserProperty] = properties
        self.ident_props: Dict[str, List[Property]] = ident_props
        self.attrs: Dict[str, ParserProperty] = attrs
        self.parser = parser

    def init_prop(self, prop, val) -> ParserProperty:  # noqa, to be inherit
        return prop.init(val)

    def _switch_failed_prop(self, mp: dict, prop: Property):
        if not prop.__ident__ or prop.__exclusive__:
            return False
        props = self._handle_prop_parsed(mp, prop)
        if props:
            # [other_props]
            return True
        origin_props = self.ident_props.get(prop.__ident__)
        if origin_props and len(origin_props) > 1:
            return True
        return False

    @classmethod
    def _handle_prop_parsed(cls, mp: dict, prop: Property):
        if not prop.__ident__:
            return False
        props = mp.get(prop.__ident__)
        if isinstance(props, list) and prop in props:
            props.remove(prop)
            return props
        return False

    def parse_context(self, context: object) -> dict:
        if not isinstance(context, self.context_cls):
            # should raise TypeError
            return {}
        params = {}
        mp = {k: list(v) for k, v in self.ident_props.items()}
        for key, prop in self.properties.items():
            try:
                value = prop.get(context)
            except ContextPropertySwitch as e:
                if not self._switch_failed_prop(mp, prop.prop):
                    raise
                value = None
            else:
                self._handle_prop_parsed(mp, prop.prop)
            if not unprovided(value):
                params[key] = value
        return params

    async def async_parse_context(self, context: object) -> dict:
        if not isinstance(context, self.context_cls):
            # should raise TypeError
            return {}
        params = {}
        mp = {k: list(v) for k, v in self.ident_props.items()}
        for key, prop in self.properties.items():
            try:
                value = prop.get(context)
                if inspect.isawaitable(value):
                    value = await value
            except ContextPropertySwitch:
                if not self._switch_failed_prop(mp, prop.prop):
                    raise
                value = None
            else:
                self._handle_prop_parsed(mp, prop.prop)
            if not unprovided(value):
                params[key] = value
        return params

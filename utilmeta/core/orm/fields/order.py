import warnings
from utype import Field
from utype.parser.field import ParserField
from utype.types import *

# from utilmeta.util.error import Error

if TYPE_CHECKING:
    from ..backends.base import ModelAdaptor, ModelFieldAdaptor


class Random:
    pass


class Order:
    def __init__(
        self,
        field=None,
        *,
        asc: bool = True,
        desc: bool = True,
        document: str = None,
        distinct: bool = False,
        nulls_first: bool = False,  # in asc() / desc()
        nulls_last: bool = False,
        notnull: bool = False,
    ):

        if not asc and not desc:
            raise ValueError(f"Order({repr(field)}) must specify asc or desc")

        if notnull:
            if nulls_first or nulls_last:
                raise ValueError(
                    f"Order({repr(field)}) that set "
                    f"notnull=True cannot config nulls_first or nulls_last"
                )
        self.asc = asc
        self.desc = desc
        self.distinct = distinct
        self.document = document
        self.field = field
        self.nulls_first = nulls_first
        self.nulls_last = nulls_last
        self.notnull = notnull


class ParserOrderBy(ParserField):
    field: "OrderBy"

    def __init__(self, model: "ModelAdaptor" = None, **kwargs):
        super().__init__(**kwargs)
        from ..backends.base import ModelAdaptor, ModelFieldAdaptor

        self.model: Optional[ModelAdaptor] = None
        self.orders: Dict[str, Tuple[Order, ModelFieldAdaptor, int]] = {}
        self.desc_prefix: str = "-"

        if isinstance(model, ModelAdaptor) and isinstance(self.field, OrderBy):
            self.model = model
            self.desc_prefix = self.field.desc_prefix

            orders = {}
            for key, order in self.field.orders.items():
                field_name = order.field or key
                field = model.get_field(field_name, allow_addon=True)
                name = key if isinstance(key, str) else field.query_name
                if not name:
                    raise ValueError(f"Order field: {key} must have a valid name")
                if field.is_exp:
                    model.check_expressions(field.field)
                else:
                    model.check_order(field.query_name)
                    if model.include_many_relates(field_name):
                        warnings.warn(
                            f"Order for {model} field <{field_name}> contains multiple value, "
                            f"make sure that is what your expected"
                        )

                if order.asc:
                    orders.setdefault(name, (order, field, 1))
                if order.desc:
                    orders.setdefault(self.desc_prefix + name, (order, field, -1))

            self.orders = orders
            self.type = enum_array(
                list(orders),
                item_type=str,
                # name=f'{self.model.ident}.{self.name}.enum',
                unique=True,
            )

    # def parse_value(self, value, context):
    #     value = super().parse_value(value, context=context)
    #     if isinstance(context, QueryContext):
    #         orders = []
    #         for o in value:
    #             if o in self.orders:
    #                 order, flag = self.orders[o]
    #                 context.orders.append((o, order, flag))
    #         return orders
    #     return value

    @property
    def schema_annotations(self):
        data = dict(self.field.schema_annotations or {})
        orders = {}
        for key, order in self.field.orders.items():
            order: Order
            field_name = order.field or key
            name = key
            if not isinstance(name, str):
                field = self.model.get_field(field_name, allow_addon=True)
                name = field_name = field.query_name
            orders[name] = dict(
                document=order.document,
                field=str(field_name),
                asc=order.asc,
                desc=order.desc,
                nulls_first=order.nulls_first,
                nulls_last=order.nulls_last,
            )
        data.update(orders=orders)
        return data


class OrderBy(Field):
    parser_field_cls = ParserOrderBy

    def __init__(
        self,
        orders: Union[list, Dict[Any, Order]],
        *,
        # orders can be a list of model fields, or a dict of order configuration
        # key: str = None,
        # max_length: int = None,
        desc_prefix: str = "-",
        ignore_invalids: bool = True,
        ignore_conflicts: bool = True,  # like if asc and desc is provided at the same time
        required: bool = False,
        description: str = None,
        single: bool = False,
        **kwargs,
    ):
        if isinstance(orders, list):
            orders = {o: Order() for o in orders}

        order_docs = []
        for key, order in orders.items():
            if order.document:
                order_docs.append(f"{key}: {order.document}")
        order_doc = "\n".join(order_docs)
        if description:
            description += "\n" + order_doc
        else:
            description = order_doc

        super().__init__(**kwargs, description=description, required=required)

        self.orders = orders
        self.desc_prefix = desc_prefix
        self.ignore_invalids = ignore_invalids
        self.ignore_conflicts = ignore_conflicts
        self.single = single

    @property
    def schema_annotations(self):
        return {
            "class": "order_by",
        }

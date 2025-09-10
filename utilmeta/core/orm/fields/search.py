from .filter import Filter, ParserFilter
from typing import List, TYPE_CHECKING, Optional
from utype.types import Literal
import re

if TYPE_CHECKING:
    from ..backends.base import ModelAdaptor, ModelFieldAdaptor


def split_by_delimiters(text, delimiters: List[str]):
    if not text:
        return []

    if not delimiters:
        return [text]

    pattern = '|'.join(re.escape(delimiter) for delimiter in delimiters)
    result = re.split(pattern, text)
    result = [item for item in result if item != '']

    return result


class Search(Filter):
    # () field match () keyword
    ALL_ALL = 'all_all'         # (field_1: kw_1 & field_n: kw_1) & (field_n: kw_1 & field_n: kw_n)
    UNION_ALL = 'union_all'     # (field_1: kw_1 | field_n: kw_1) & (field_n: kw_1 | field_n: kw_n)
    ANY_ALL = 'any_all'         # (field_1: kw_1 & field_1: kw_n) | (field_n: kw_1 & field_n: kw_n)
    ANY_ANY = 'any_any'         # (field_1: kw_1 | field_1: kw_n) | (field_n: kw_1 | field_n: kw_n)
    FULL_TEXT = 'full_text'

    class Field:
        def __init__(
            self,
            field,
            case_sensitive: bool = None,
            full_text: bool = None,
            weight: str = None,
            match_keyword: Literal['any', 'all'] = None
        ):

            self.field = field
            self.model_field: Optional['ModelFieldAdaptor'] = None
            self.full_text = full_text
            self.weight = weight
            self.case_sensitive = case_sensitive
            self.match_keyword = match_keyword

        def setup(self, model: 'ModelAdaptor'):
            self.model_field = model.get_field(
                self.field, silently=False
            )

        def get_django_q(self, s: str):
            from django.db import models
            if self.model_field:
                lookups = []
                if self.full_text:
                    lookups.append('search')
                if not self.case_sensitive:
                    lookups.append('icontains')
                lookups.append('contains')
                lookup = ''
                for lkp in lookups:
                    if self.model_field.get_lookup(lkp):
                        lookup = lkp
                        break
                field = self.model_field.query_name or self.model_field.name
                if lookup:
                    field = field + '__' + lookup
                return models.Q(**{field: s})
            return models.Q()

        def get_django_vector(self):
            from django.contrib.postgres.search import SearchVector
            if self.model_field:
                field = self.model_field.query_name or self.model_field.name
                return SearchVector(field, weight=self.weight)
            return None

    def __init__(
        self,
        *search_fields,
        # field | str | SearchVector
        case_sensitive: bool = False,
        # lookup
        # 1. search (if lookup is available)
        # 2. icontains: case_sensitive=False
        # 2. contains: case_sensitive=True
        keyword_delimiters: List[str] = (' ', ',', ';', '|'),
        match_mode: Literal[ALL_ALL, UNION_ALL, ANY_ALL, ANY_ANY, FULL_TEXT] = ANY_ALL,
        min_rank: float = None,
        # distinct: bool = False,
        allow_empty: bool = False,
        # do distinct if query has carry the search field
        **kwargs
    ):
        # search fields:
        # int / float
        # str
        # dict / list
        super().__init__(**kwargs)

        fields = []
        for field in search_fields:
            if isinstance(field, self.Field):
                fields.append(field)
            else:
                fields.append(self.Field(
                    field,
                    case_sensitive=case_sensitive,
                    full_text=match_mode == self.FULL_TEXT,
                ))

        self.search_fields = fields
        self.case_sensitive = case_sensitive
        self.keyword_delimiters = keyword_delimiters
        self.match_mode = match_mode
        self.min_rank = min_rank
        # self.distinct = distinct
        self.allow_empty = allow_empty
        # icontains
        # contains

    @property
    def schema_annotations(self):
        return {"class": "search"}

    def get_search_query(self, model: "ModelAdaptor", field_name: str = None):
        if model.backend_name == 'django':
            from django.db import models
            from django.apps.registry import apps

            if self.match_mode == self.FULL_TEXT:
                if not apps.is_installed('django.contrib.postgres'):
                    raise ValueError(f"orm.Search(match_mode='full_text') requires 'django.contrib.postgres'"
                                     f" installed as app in django")

            def django_search_query(s: str):
                if not s:
                    return models.Q()

                keywords = split_by_delimiters(s, self.keyword_delimiters)

                if self.match_mode == self.ALL_ALL:
                    q = models.Q()
                    for keyword in keywords:
                        for field in self.search_fields:
                            q &= field.get_django_q(keyword)
                    return q

                elif self.match_mode == self.UNION_ALL:
                    q = models.Q()
                    for keyword in keywords:
                        kw_q = models.Q()
                        for field in self.search_fields:
                            kw_q |= field.get_django_q(keyword)
                        q &= kw_q
                    return q

                elif self.match_mode == self.ANY_ALL:
                    q = models.Q()
                    for field in self.search_fields:
                        field_q = models.Q()
                        for keyword in keywords:
                            field_q &= field.get_django_q(keyword)
                        q |= field_q
                    return q

                elif self.match_mode == self.ANY_ANY:
                    q = models.Q()
                    for keyword in keywords:
                        for field in self.search_fields:
                            q |= field.get_django_q(keyword)
                    return q

                elif self.match_mode == self.FULL_TEXT:
                    if field_name:
                        return models.Q({field_name + '__gte': self.min_rank or 0})
                return models.Q()

            return django_search_query
        return None

    def get_rank_expression(self, value: str):
        if self.match_mode == self.FULL_TEXT:
            search_vector = None
            for field in self.search_fields:
                vector = field.get_django_vector()
                if not search_vector:
                    search_vector = vector
                else:
                    search_vector += vector
            if search_vector:
                from django.contrib.postgres.search import SearchQuery, SearchRank
                return SearchRank(search_vector, query=SearchQuery(value))
        return None


class ParserSearch(ParserFilter):
    field: "Search"
    field_cls = Search

    def __init__(self,
                 model: "ModelAdaptor" = None,
                 field: Search = None,
                 attname: str = None,
                 **kwargs
                 ):
        self.model = model
        if isinstance(field, Search):
            self.query = field.get_search_query(model, field_name=attname)
            for sf in field.search_fields:
                sf.setup(model)

        super().__init__(
            model,
            field=field,
            attname=attname,
            **kwargs
        )

    @property
    def order(self):
        if isinstance(self.field, Search):
            if self.field.match_mode == Search.FULL_TEXT:
                return '-' + self.attname
        return None

    @property
    def field_name(self):
        return None

    def get_expression(self, value: str):
        if isinstance(self.field, Search):
            if self.model.backend_name == 'django':
                return self.field.get_rank_expression(value)
        return None


Search.parser_field_cls = ParserSearch

from ..base import ModelQueryAdaptor
from sqlalchemy.orm.query import Query


class SQLAlchemyQueryAdaptor(ModelQueryAdaptor):
    queryset_cls = Query
    queryset: Query

    @property
    def session(self):
        return self.queryset.session

    def filter(self, *args, **kwargs) -> "SQLAlchemyQueryAdaptor":
        pass

    def exists(self) -> bool:
        return self.session.query(self.queryset.exists()).scalar()

    def count(self) -> int:
        return self.queryset.count()

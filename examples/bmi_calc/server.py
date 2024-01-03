from utilmeta.core import api
import utype
from utilmeta.core.api.specs.openapi import OpenAPI
from utilmeta import UtilMeta
import flask

service = UtilMeta(
    __name__,
    backend=flask,
    port=8001
)


class BMISchema(utype.Schema):
    value: float = utype.Field(round=2)

    @property
    def level(self) -> int:
        for i, l in enumerate([18.5, 25, 30]):
            if self.value < l:
                return i
        return 3

    # @property
    # @utype.Field(enum=BMI_CLASSES)
    # def classification(self) -> str:
    #     return BMI_CLASSES[self.level]


class RootAPI(api.API):
    docs: OpenAPI.as_api('openapi.json')  # new

    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)
            ) -> BMISchema:
        return BMISchema(value=weight / height ** 2)


service.mount(RootAPI, route='/api')
app = service.application()     # for wsgi/asgi server

if __name__ == '__main__':
    service.run()

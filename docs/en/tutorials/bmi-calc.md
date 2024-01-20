# BMI Calculation API

Our introductory tutorial is to write a simple BMI calculation API, which calculates the corresponding BMI value according to the input height and weight.
## 1. Create project

We can create a project directly using

```
meta setup demo-bmi
```

Then you will be prompted to enter the description, host and other information, you can choose to skip, after that, you will get the following file structure

```
/bmi
    server.py
    meta.ini
```

!!! abstract ""
	`server.py` is your file with backend code, while `meta.ini` is a config file to store the project meta-data


## 2. Basic implementation

Open `server.py`, we can see that there is already a class named `RootAPI`

```python
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'
```

Here you can see the simplest UtilMeta API, which uses a `@api.get` decorator to indicate that it is a GET method. The decorator does not specify a path, so the path of the API is the name of the function (`/hello`).

We write the BMI calculation API as follows
```python
class RootAPI(api.API):  
    @api.get  
    def bmi(self, weight: float, height: float):  
         return round(weight / height ** 2, 1)
```

The parameters `weight` and `height` in the `bmi` function will become query parameters by default, which can be calculated in the function and returned directly. UtilMeta will wrap the return value to a HTTP response

We can run this file directly to start the API service.
```shell
python server.py
```

When you see the following info, it means that the startup is successful
```
Running on http://127.0.0.1:8000
Press CTRL+C to quit
```

Then we can use our browser to open [http://127.0.0.1:8000/api/bmi?weight=70&height=1.85](http://127.0.0.1:8000/api/bmi?weight=70&height=1.85) to call the API, and we can see that the API returns
```json
20.5
```

This example is simple enough, but it also has some areas that can be optimized, such as

* The limitation of the requested parameter value was not verified. An error will occur if the parameter `height` is 0. and there is no meaning if the parameter is negative.
* The number is returned directly as a result, and the normal practice is to use a JSON to return it.

## 3. Add params & response

Combined with the optimizations mentioned above, let’s make some improvements to the API.

First, we use `utype.Param` to add a declaration of validation rules for input parameters, as shown in

```python
import utype

class RootAPI(api.API):
    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)):
        return round(weight / height ** 2, 2)
```

In the above function, we declared that the `weight` parameter needs to be greater than 0 and less than or equal to 1000, and `height` the parameter needs to be greater than 0 and less than or equal to 4. If the input data does not conform to these rules, UtilMeta will automatically process and return a `400 BadRequest` response.

!!! abstract "utype"
	UtilMeta is based on `utype` to declare and parse params, you can discover more usage of validation ruls in [this doc](https://utype.io/references/rule/)

For the return result, we can use a JSON to return the BMI value and classification. In order to make the response also integrated into the API document, we can use `utype.Schema` to define the format of the response, such as
```python
from utilmeta.core import api
import utype

class BMISchema(utype.Schema):
    value: float = utype.Field(round=2)

    @property
    def level(self) -> int:
        for i, l in enumerate([18.5, 25, 30]):
            if self.value < l:
                return i
        return 3

class RootAPI(api.API):
    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)
            ) -> BMISchema:
        return BMISchema(value=weight / height ** 2)
```

In `BMISchema`, we declare the `level` property, using `value` to calculate the corresponding BMI level, which will also be output as a field. The `BMISchema` instance returned by the API will be directly processed by UtilMeta into a JSON format response to the client.

When we restart the project and visit [http://127.0.0.1:8000/api/bmi?weight=70&height=1.85](http://127.0.0.1:8000/api/bmi?weight=70&height=1.85) again, we can see the following return result
```json
{"value": 20.45, "level": 1}
```

### Auto-generated OpenAPI docs

UtilMeta can automatically generate API documentation for you based on the interface declaration you write. We just need to mount the API that generates the documentation on the RootAPI to access it.

you can mount an API to return the OpenAPI docs in json format, like
```python
from utilmeta.core.api.specs.openapi import OpenAPI

class RootAPI(api.API):
    docs: OpenAPI.as_api('openapi.json')  # new

    @api.get
    def bmi(self,
            weight: float = utype.Param(gt=0, le=1000),
            height: float = utype.Param(gt=0, le=4)
            ) -> BMISchema:
        return BMISchema(value=weight / height ** 2)
```

The `as_api()` parameter of the function can specify a local file address to store the generated OpenAPI JSON file.

Let’s restart the project and visit [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) to see the OpenAPI documentation in JSON format.

We can load this JSON document using any API debugger that implements the OpenAPI standard (such as [ Swagger Editor ](https://editor.swagger.io/)) and see that the input and response parameters of the API we wrote have been fully recorded in the API document.

![ BMI API Doc ](https://utilmeta.com/assets/image/bmi-api-doc.png)
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

## 4. Connect API

Once your UtilMeta service is developed, you can connect it to view a debugable API document, The `--ops` argument we added in setup command inserted a UtilMeta Operations config automatically, we can see it in `server.py` 

```python
from utilmeta.ops.config import Operations

service.use(Operations(
    route='ops',
    database=Database(
        name='demo-bmi_utilmeta_ops',
        engine='sqlite3',
    ),
))
```

When the service is running, you can see the following output:

```
UtilMeta OperationsAPI loaded at http://127.0.0.1:8000/api/ops, connect your APIs at https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8000/api/ops
```

You can click [this link](https://ops.utilmeta.com/localhost?local_node=http://127.0.0.1:8000/api/ops) directly to open UtilMeta Platform and connect to your local service, or run this command in your project directory

```
meta connect
```

You will see a browser tab prompted up and connected to the APIs you just created

<img src="https://utilmeta.com/assets/image/demo-bmi-connect-local.png" href="https://ops.utilmeta.com" target="_blank" width="600"/>

Click **API** will lead us to the BMI calculation API, We can click **Debug** to send a request 

<img src="https://utilmeta.com/assets/image/demo-bmi-api-debug.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
Click **Log** will direct you to view the API logs we just triggered, you can cliick the log row to view the detailed info. 
<img src="https://utilmeta.com/assets/image/demo-bmi-logs.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>

!!! tip
	For the performance of real-time requests, logs will be collected in the background of the process and stored regularly. If you don't see them immediately, you can wait and refresh them. For more information of Operations system you can refer to [Connect API and Operations](../../guide/ops)

## Source Code

the source code of this tutorial can be found at [github](https://github.com/utilmeta/utilmeta-py/blob/main/examples/bmi_calc/server.py)

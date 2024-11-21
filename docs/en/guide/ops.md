# Connect API & Operations

UtilMeta framework has a built-in API service management system, which can easily observe and manage local and online API services, and provide a series of operation and maintenance management functions such as data, interface, log, monitoring, testing, alarm, etc. This document will introduce the configuration and connection mode of UtilMeta Operations operation and maintenance management system in detail.

## Configuration

The configuration used by the API service management system is `utilmeta.ops.Operations` to import it and use `service.use` it in the service, as shown in
```python hl_lines="20"
from utilmeta import UtilMeta
from utilmeta.core import api
import starlette

@api.CORS(allow_origin='*')
class RootAPI(api.API):
    @api.get
    def hello(self):
        return 'world'

service = UtilMeta(
    __name__,
    name='demo',
    backend=starlette,
    api=RootAPI,
    route='/api'
)

from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
))

app = service.application()  # wsgi app

if __name__ == '__main__':
    service.run()
```

!!! note

The main parameters of the Operations configuration item include

*  `route`: Required. Specify the route for mounting the standard interface OperationsAPI of the management system. This route is relative to the root API of your service. For example, your root API is `http://mysite.com/api` mounted to. Setting `route=’ops‘` will mount the Operations API to the

*  `database`: Required. Set the database for the management system to store logs, monitoring and other operation and maintenance data. You can specify a SQLite database as in the above example. You can also specify a `postgresql` database in the production environment.

* Specify a base API address `base_url` for your API service that can be accessed on the network. This address will be used for the generated OpenAPI documentation `server.url`. Address of Operations API after setting
 
**Task and monitoring configuration**

*  `worker_cycle`: Operations system will start an operation and maintenance task thread in each process (worker) after the service is started, which is used to collect and store request logs, monitor service data and alarms, etc. You can use the `worker_cycle` parameter to specify the interval ( `int` description or `timedelata`) for these tasks to run each time. The default is 30 seconds, which means that the request log of each process will be persisted every 30 seconds by default. Database and service instance monitoring and alerting occurs every 30 second

*  `max_backlog`: Set the maximum backlog of the request log. In addition to each `worker_cycle` persistent log of the operation and maintenance task, when the backlog of unstored logs in your process exceeds `max_backlog` the value, it will also trigger log storage. The default is not 100.
*  `secret_names`: The log module of the operation and maintenance management system will store the request and response information for debugging when the request goes wrong (throwing an exception and returning a status code of 400 or above). For data security, you can specify a series of field names that may contain keys or sensitive data. When the log is stored, The request parameter, request body, request header, response body, and response header fields will be used `'******'` instead if the field name is detected to contain any of them. The default `secret_names` is
```python
DEFAULT_SECRET_NAMES = (
    'password',
    'secret',
    'dsn',
    'sessionid',
    'pwd',
    'passphrase',
    'cookie',
    'authorization',
    '_token',
    '_key',
)
```

*  `max_retention_time`: Specify the maximum storage time of all time series data in the operation and maintenance system. Time series data include logs, service monitoring, alarm records and other data. The maximum storage time of all data is specified here. Data exceeding this time will be cleared. For subdivided data categories and status, more specific storage time configuration will be introduced below.

**Manage permissions configuration**

*  `disabled_scope`: Disable administrative privileges. If you do not want an administrative privilege to be used by any administrator user, you can use this option to disable it. The default is blank.
*  `local_scope`: Permission granted by the local management node. Local management refers to observing and managing local services on localhost/127.0.0.1, so the default permission is `('*',)`, that is, All. If you set this value to null or None, Indicates that all local administrative operations will not be allowed

The current permission scope list of the UtilMeta server and the corresponding meanings are as follows:

*  `api.view`: View the API documentation for the service
*  `data.view`: View the data model and table structure (that is, the field names, types, etc. Of the table, excluding the data in the query table)
*  `data.query`: Query the data in the table, and support field query
*  `data.create` Create data, that is, insert data into a table
*  `data.update`: Update data
*  `data.delete`: Delete data
*  `log.view`: Query log
*  `log.delete`: Delete the log
*  `metrics.view`: Query the monitoring data of the service

### Log configuration

The log module of the operation and maintenance management system is responsible for recording and querying the request log. The configuration of the log module allows you to control the storage of the log more carefully.

Parameters in the `log` Operations configuration can be passed to the configuration component of the logging module, such as

```python  hl_lines="8"
from utilmeta.ops import Operations
service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    log=Operations.Log(
	    default_volatile=False,
	    exclude_methods=['head'],
	    exclude_status=[301, 302, 404]
    )
))
```

Log configuration parameters include

*  `default_volatile`: Whether the default is marked as `volatile` (log not saved for a long time)
*  `volatile_maintain`: The save time of the log marked as `volatile`. One `timedelta` is passed in. The default is 7 days.

**Log storage rules**

*  `persist_level`: When the request log reaches a certain level, it will be persisted. The default is WARN.

*  `persist_duration_limit`: How long the request takes to generate a response will be persisted. A number of seconds is passed in. The default is 5 seconds.
* At what level of the `store_data_level` request log will the request body data be stored?
* At what level of the `store_result_level` request log will the response body data be stored?
*  `store_headers_level`: Above what level of the request log will request and response header data be stored

*  `exclude_methods`: Exclude some HTTP methods and do not store logs if there are no errors. Default is `OPTIONS`? `HEAD`?
*  `exclude_status`: Some response codes can be excluded. If there is no error, the log will not be stored. The default is null.
*  `exclude_request_headers`: Some request headers can be excluded. If the request header contains one of these values, the log will not be stored if there is no error. The default is null.
*  `exclude_response_headers`: Some response headers can be excluded. If the response header contains one of these values, the log will not be stored if there is no error. The default is null.

**Log display rules**

*  `hide_ip_address`: For data security or privacy protection, you can choose to turn on this option, and the IP information of the log will not be seen on the UtilMeta platform.
*  `hide_user_id`: For data security or privacy protection, you can choose to enable this option, and the user ID information of the log will not be seen in the UtilMeta platform.

### Monitor configuration

The log module of the operation and maintenance management system will monitor the server, service instance, service process, database, cache and other resources on which the service depends regularly (based on the `worker_cycle` cycle configured by Operations), and store the data in the database configured by Operations.

Parameters in the `monitor` Operations configuration can be passed into the configuration component of the monitoring module, such as

```python  hl_lines="8"
from utilmeta.ops import Operations
from datetime import timedelta

service.use(Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
    ),
    monitor=Operations.Monitor(
	    server_retention=timedelta(days=30)
    )
))
```

Configuration parameters for Monitor include

*  `server_disabled`: Whether to disable the monitoring of server Server. The default is False.
*  `instance_disabled`: Whether to disable the monitoring of service instance Instance. The default is False.
*  `worker_disabled` Whether to disable monitoring of the service process Worker. The default is False.
*  `database_disabled`: Whether to disable the monitoring of Database. The default is False.
*  `cache_disabled`: Whether to disable the monitoring of Cache. The default is False.

!!! Tip “Service Instance | Service Process”

*  `server_retention`: Save time of Server monitoring, incoming `timedelta`, 7 days by default
*  `instance_retention`: Save time of service instance Instance monitoring, passed in `timedelta`, 7 days by default
*  `worker_retention`: Save time of service process Worker monitoring, which is passed in `timedelta` and defaults to 24 hours.
*  `database_retention`: Save time of database monitoring, passed in `timedelta`, 7 days by default
*  `cache_retention`: Save time of Cache monitoring, incoming `timedelta`, 7 days by default

Overdue monitoring data will be cleaned up

### OpenAPI configuration

For the interfaces written by UtilMeta framework and the framework interfaces supporting adaptation, the UtilMeta operation and maintenance management system can automatically identify and generate OpenAPI documents to synchronize to the UtilMeta platform, but if the framework you access does not support the automatic generation of interface documents, or if you need to inject additional interface documents, you can do so. Additional OpenAPI documentation can be specified using the `openapi` Operations configuration parameter, which can be in the following format

* A URL to the OpenAPI documentation that can be accessed and downloaded
* The location of a local OpenAPI documentation file
* An OpenAPI JSON/yaml string
* An OpenAPI dictionary
* A list for integrating multiple API documents, where the element can be any of the above

The additional specified OpenAPI documentation will be integrated with the automatically generated interface documentation and synchronized to the UtilMeta platform.

## Connect to UtilMeta Platform

UtilMeta provides a management platform for the observation and management operations of the API service operation and maintenance management system: [ UtilMeta API Service Management Platform ](https://ops.utilmeta.com) you can enter the platform to connect and manage your own UtilMeta service, view API documents, data, logs and monitoring.
### Connect Local Node

If you have introduced the Operations configuration, successfully run the local service, and see the following prompt

```
UtilMeta OperationsAPI loaded at http://127.0.0.1[...], connect your APIs at https://ops.utilmeta.com
```

You are ready to connect to the local node for debugging, just run the following command inside the service directory (the containing `meta.ini` directory

```
meta connect
```

You can see that the window of UtilMeta management platform is opened in the browser, where you can see the API, data table, log and monitoring of your service.
<img src="https://utilmeta.com/assets/image/connect-local-api.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
### Connect Online service

Connecting to the API service deployed online and providing network access address requires you to register an account on the UtilMeta platform. Because the management of online services requires a stricter authorization and authentication mechanism, you need to create a project team on the UtilMeta platform first. When you enter an empty project team, You can see the connection prompt for the UtilMeta platform

<img src="https://utilmeta.com/assets/image/connect-node-hint.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>
If you have followed the above configuration method, you can directly copy the command given by the UtilMeta platform and execute the command inside the project directory (included `meta.ini` directory) in your server. If the command is successfully executed, you will see a URL output from the console.

```
connecting: auto-selecting supervisor...
connect supervisor at: https://api-sh.utilmeta.com/spv
supervisor connected successfully!
please visit [URL] to view and manage your APIs'
```

Click the URL to enter the platform to access the online service you have connected, or click the [I’ve executed successfully] button in the platform to refresh the status after successful execution

## Connect to Python project

The operation and maintenance management system of UtilMeta framework can not only connect to the services of UtilMeta framework, but also connect to the existing Python back-end projects. The currently supported frameworks include

* **Django**: Includes Django REST framework.
* **Flask**: Include APIFlask
* **FastAPI**: Starlette included
* **Sanic**

### Initialize UtilMeta project

Before connecting to any Python project, initialize the UtilMeta settings by simply going to your project folder and typing the following command

```
meta init --app=ref.of.your.app
```

Note that the parameters in `--app` the command need to specify yours ** Reference path for Python WSGI/ASGI application **, for example for the following Django project

```
/django_project
	/django_settings
		wsgi.py
		settings.py
		urls.py
	manage.py
```

Django’s WSGI application is normally located `wsgi.py` in the `application`, and will be executed when we initialize the UtilMeta project in the/Django _ project folder

```
meta init --app=django_settings.wsgi.app
```

For Flask/FastAPI/Sanic projects, you only need to find the reference of the corresponding `Flask()`? `FastAPI()`? `Sanic()` application, and the usage is the same as above.

The actual effect of executing this command is to create a file named `meta.ini` in your current directory with the following content

```ini
[utilmeta]
app = django_settings.wsgi.app
```

The UtilMeta framework relies on this file to identify the UtilMeta project and the address of the project’s core application object.

### Connect to Django

For the Django project, we find the (or `asgi.py`) file containing the WSGI application `wsgi.py` and insert the Operations configuration integration code after the `application = get_wsgi_application()` definition

```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# NEW -----------------------------------
from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'
        # or 'postgres' / 'mysql' / 'oracle'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(application, __name__)
```

We first declare the `Operations` configuration with the same parameters as described above, and then call the method of `integrate` configuring the instance. The first parameter is passed into `__name__` the WSGI/ASGI application, and the second parameter is passed in.

It should be noted that `Operations` the `base_url` configuration parameters need to provide your Django service **Reference access address**, that is, the path defined in your API service will be extended from this address, if it is deployed on the network. Set to a URL that can be reached on the network. For local service, set to `http://127.0.0.1: your port number


After adding the configuration code, if your project is running locally, you can execute the following command to connect to the local service after restarting the project

```
meta connect
```

If your service provides network access, go to [ UtilMeta Management Platform ](https://ops.utilmeta.com), create a project team and follow the prompts

### Connect Flask

For the Flask project, we only need to connect the Operations configuration to the Flask app, as shown in

```python
from flask import Flask

app = Flask(__name__)

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3' # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```

The `base_url` `Operations` configuration parameters need to provide your Flask service ** Reference access address **, that is, the path defined in your API service will be extended from this address. If it is a service deployed on the network, please set it to the URL that can be accessed in the network. If local service, set to

After adding the configuration code, if your project is running locally, you can execute the following command to connect to the local service after restarting the project

```
meta connect
```

If your service provides network access, go to [ UtilMeta Management Platform ](https://ops.utilmeta.com), create a project team and follow the prompts
### Connect to FastAPI

For the FastAPI project, we only need to connect the Operations configuration to the FastAPI app, as shown in

```python
from fastapi import FastAPI

app = FastAPI()

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3'  # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```

The `base_url` `Operations` configuration parameters need to provide your FastAPI service ** Reference access address **, that is, the path defined in your API service will be extended from this address. If it is a service deployed on the network, please set it to the URL that can be accessed in the network. If local service, set to

After adding the configuration code, if your project is running locally, you can execute the following command to connect to the local service after restarting the project

```
meta connect
```

If your service provides network access, go to [ UtilMeta Management Platform ](https://ops.utilmeta.com), create a project team and follow the prompts

### Connect Sanic

For the Sanic project, we only need to connect the Operations configuration to the Sanic app, as shown in

```python
from sanic import Sanic

app = Sanic('mysite')

from utilmeta.ops import Operations
Operations(
    route='ops',
    database=Operations.Database(
        name='operations_db',
        engine='sqlite3' # or 'postgresql' / 'mysql'
    ),
    base_url='https://<YOUR DOMAIN>/api',
    # base_url='http://127.0.0.1:<YOUR_PORT>',   # 本地项目
).integrate(app, __name__)
```


The `base_url` `Operations` configuration parameters need to provide your Sanic service ** Reference access address **, that is, the path defined in your API service will be extended from this address. If it is a service deployed on the network, please set it to the URL that can be accessed in the network. If local service, set to


After adding the configuration code, if your project is running locally, you can execute the following command to connect to the local service after restarting the project

```
meta connect
```

If your service provides network access, go to [ UtilMeta Management Platform ](https://ops.utilmeta.com), create a project team and follow the prompts

## UtilMeta Platform

[ UtilMeta Management Platform ](https://ops.utilmeta.com) is a one-stop API service observation and management platform. This section mainly introduces its functions and usage.

### Overview
In the UtilMeta management platform, each user can create or join multiple ** Project Team (Team) **, each team can connect and manage multiple ** API Service **, and can also add multiple members, giving them different management permissions.

There are two ways to add API services to the project team on the UtilMeta platform:

* Use UtilMeta framework or UtilMeta adaptive framework for development. You can access the platform with one click after adding configuration code.
* For other API services, you can import the OpenAPI interface document

<img src="https://utilmeta.com/assets/image/connect-service-choose.png" href="https://ops.utilmeta.com" target="_blank" width="800"/>

Each API service connected to the UtilMeta platform supports the following features

* Debuggable API Interface Documentation
* Write and execute API unit tests
* View the call and test logs for the API
* Set up Dial Monitoring and Alerting for API (coming soon)

The API service that uses the UtilMeta framework to connect to the platform is called ** UtilMeta node ** the Operations API provided by the operation and maintenance management system of the UtilMeta framework, which enables UtilMeta nodes to have server-side observation and reporting capabilities. Therefore, the UtilMeta node has the following additional capabilities over the normal API services

* Server requests real-time log query
* Data management CRUD (the ORM library supported by the server is required, and Django ORM is supported at present)
* API Real Request Access Statistics and Analysis
* Real-time monitoring of server resource performance and occupancy
* Server Condition Alerts and Notifications (coming soon)

### API

Click the left column **API** to enter the interface management section of the platform
<img src="https://utilmeta.com/assets/image/api-annotation-zh.png" target="_blank" width="800"/>
In the API list on the left, you can search or filter interfaces by using the tag. Click the interface to enter the corresponding interface document. Click the [Debug] button on the right to enter the debugging mode. You can enter parameters and initiate a request. The right side will automatically synchronize the curl, python and JS request codes corresponding to the parameters.

If your API interface includes the key required for authentication, the key can be centrally managed on the UtilMeta platform.

!!! tip

### Data

Click the left column **Data** to enter the data management section of the platform.

<img src="https://utilmeta.com/assets/image/data-annotation-zh.png"  target="_blank" width="800"/>
The model list on the left can be searched or filtered by using the tag. After clicking the model, the table structure and query table data will be displayed on the right. You can add multiple field queries in the field query bar above. Each field in the table also supports positive and negative sorting.

Each data unit in the table can be clicked. Left-click or right-click will expand the tab. If the data is too large to display completely, it can be expanded. Users with permission can also edit or delete the selected data row. Click the [+] button in the upper right corner to create a new data instance

Below the table is the table structure document of the model, which will display the name, type, attribute (primary key, foreign key, unique, etc.) And verification rule of the model field in detail

You can specify a `secret_names` parameter when configuring the Operations system. When the table field name contains `secret_names` any one of the names in, the corresponding result returned by the data query will be hidden ( `'******'`). For the default value, please refer to the above configuration section

### Logs

Click the left column **Logs** to enter the log query section of the platform.

<img src="https://utilmeta.com/assets/image/logs-annotation-zh.png"  target="_blank" width="800"/>
The left side is the filtering and options of the log, and the top can switch the log plate.
* ** Service Logs **: Server real request log
* ** Test Logs **: Debug and test logs initiated on the UtilMeta platform

Filtering options at the bottom left include log levels, response status codes, HTTP methods, and API interfaces, and can be sorted by request time or processing time

Click a single log to expand the log details. The log will record the request and response information, exception call stack and other data in detail.

<img src="https://utilmeta.com/assets/image/logs-detail-annotation-zh.png"  target="_blank" width="600"/>

### Servers

Click the left column ** Servers ** to enter the service monitoring section of the platform.

<img src="https://utilmeta.com/assets/image/servers-annotation-zh.jpg"  target="_blank" width="800"/>
It can monitor the CPU, memory usage, Load Avg, file descriptors and network connections of the server where the API service is located in real time.

The time range option in the upper right corner allows you to select the time of the data query

### Authorization and authentication mechanism

The observation and management operation authorization of UtilMeta management platform is based on the credentials flow of OAuth2 protocol.

The server-side management capabilities provided by the UtilMeta node, such as data management, logging, and monitoring queries, are implemented by directly calling the Operations API of the node. The client (such as browser) of the UtilMeta platform will first request the UtilMeta platform for a OAuth access token containing the corresponding permission. If the platform verifies that the user has the corresponding permission in the team where the API service is located, it will authorize it. Otherwise, it will reject it

<img src="https://utilmeta.com/assets/image/permissions-team-example.png"  target="_blank" width="600"/>

After normal authorization, the client of the UtilMeta management platform will carry the access token to initiate an observation or management request to the Operations API of your server. The Operations API will parse and authenticate the access token and execute the legitimate request.

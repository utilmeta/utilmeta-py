# Release Note

## v2.8.0

Release Date:  2025/9/10

### New features

* API support **Server-Sent Events (SSE)**: [Use SSE in API](../../guide/api-route#server-sent-events)
* Clien support handling Server-Sent Events (SSE) response:  [Handle SSE Response](../../guide/client#server-sent-events)
* `@api` decorator added `timeout` parameter to specifiy the timeout for API function processing time or Client request timeout.
* Added HTTP cache plugin: `api.Cache`: can handle HTTP caching like `Last-Modifed` / `Etag` automatically
* Added search parameter `orm.Search`, support various search mode for multiple model fields: [Search Param](../../guide/schema-query/#search-param)
* `orm.Schema` support defining request context variables (such as current request user / IP) and query request context fields by passing the current request object to `context` param of the serialize methods: [Use context vars in query function](../../guide/schema-query/#relational-query-function)
* `meta gen_openapi` support `--split` parameter that spliting the API document in seperate files by endpoint, convenient for AI tools to parse and read

### Optimized

* Optimize `orm.Field` field parsing and rule merging.
* Client reuse request session  (`httpx.Client` / `aiohttp.Session` / `requests.Session`)  in `with` and `async with` block.

### Fixed

* Fix YAML output format of generated OpenAPI document.

## v2.7.6

Release Date:  2025/6/6

### New features

* UtilMeta service instance supported `adapt(route: str)` method, used to integrate UtilMeta API into existing Python backend projects that requires the UtilMeta service configuration.
* API function suported defining multiple `request.Query` , `request.Headers` and `request.Body` (with different Content-Type alternatives), along with data parsing and OpenAPi document generation,
* `orm.Field` supported value query function, can be used to conveniently and efficiently organize custom query code beyond serialization of relational objects
* `meta gen_openapi` command added `--prefix` argument to specify an API path prefix, and generate document only for the APIs with path startswith this prefix.

### Optimized

* OpenAPI supported extract doc string of API function to description.
* Operations supported `clear_daily`, enable to run the deletion task of the stale data daily.
* `File` object added `content_md5` property to get the MD5 value of the file content (can be used in de-duplicate or cache).

### Fixed

* Fixed the import issue of `aioredis` (redis>=4.2.0rc1+ supported asynchronous internally)

## v2.7.5

Release Date:  2025/3/21

### New features

* ·Operations support `connection_key` to authorize the local and private services, and support connecting to private service directly after `connection_key` and `private_scope` are set.
* Add `meta check` command to check if UtilMeta can load normally (no error)

### Optimized

* Optimized `orm.Field` to support lookup that has conflicted name with field name. 
* Optimized runtime dispatch for all Adaptors (request, response, file, ...) with `__backends_package__` specified.
* Optimized ResponseFile's file name recognition.
* Optimized Session's `save` for database drivin session.
* Optimized Filter's `query` to handle `@classmethod`.
* orm support query and serialize `managed=False` Django model (such as the database view model without primary key)

### Fixed

* Fix Django route mounting problem (`__as__` method)

## v2.7.4

Release Date:  2025/2/10

### Optimized

* Optimized `queryset` handing in `orm.Field`.
* Support multi-layer ORM relational objects update, prevent infinite loop in `Self` reference.

## v2.7.3

Release Date: 2025/1/24

### Optimized

* Support multiple packages in `DjangoSettings` 's `apps_package`
* Optimize orm behaviour for optional model field (`default` specified field)
* Provided more detailed task logs info and control for Operations system.
* Optmize error handling for Operations data management APIs, return 400 for integrity error.
* Optimize `Content-Type` recognition for nested logic request body type.

## v2.7.2

Release Date: 2024/12/26

### Optimized

*  `Client` 's  `fail_silently=False` will throw an error when the response code does not match any response template, improving the certainty of the response result.

### Fix

* Fix the data query problem of the data management function of the Operations system (corresponding to the Data plate of the UtilMeta platform)


## v2.7.1

Release Date: 2024/12/25

### New features

* The `save` / `asave`/ `bulk_save`/ `abulk_save` methods of `orm.Schema` supports `using` parameters, You can pass in the name of the database connection (the default is `default` the model or the configured database) as the database connection for the query

### Optimized

* Optimize the `orm.Schema` solution to the infinite loop nesting problem of the query, and add the `Perference.orm_schema_query_max_depth` setting of limiting the Schema query depth, which is 100 by default
* The FastAPI / Starlette application optimizes the processing logic of server error reporting, and can record the abnormal call stack information thrown by the FastAPI interface in the log.

### Fix

* Fixed some issues with **MySQL** asynchronously connecting to the database
* Fixed some issues with the Retry plugin
* Fixed parsing of parameters in `--` command line tools

### API changes

*  `utilmeta.core.orm.ModelAdaptor`: The method of the model adapter has been changed, and the query method of the model adapter has been added to `ModelQueryAdaptor`.

## v2.7.0

Release Date: 2024/12/19

### New features

* Support the connection to the **Proxy node** to manage the intranet service cluster
* OpenAPI documentation for parsing and synchronize **Django Ninja**
* The current service process PID is specified in `pidfile` of `meta.ini`, add command to restart the service `restart` and `down` to stop the service.

### Optimized

* `Client` Class `base_url` parameters support carrying URL query parameters, which will be parsed as `base_query` requests added to each `Client` class

### Fix

* Fixed an issue where the result type of the response template defined `response` on the API class was missing from the generated OpenAPI documentation

## v2.6.4

Release Date: 2024/11/22

### New features

* Support direct connection and management of local services
* Support for managing ASGI applications for Django
* Operations system supports the connection and data storage of monitoring and observation database, and supports the down-sampling query of time series data

### Optimized item

* Optimize the mount logic of the Operations API to support **Lazy mount** for increased robustness
* Support for checking and following database dependencies before service startup
* Optimize the `secret_names` data processing logic in the Operations system and increase the detection of nested structures
* Support `tags` in the `@api`decorator for incorporating parameters declared into the generated OpenAPI documentation
* Template configuration for the optimization `setup` command
* Tuning the `must_create` parameter Logic of a Database Session 

### Fix

* Fix connection closing issue for Async API service using Operations system

### Compatibility

* Django support down to version 3.0 (can support managing projects with Django > = 3.0)

### API changes

* `utilmeta.core.cache.Cache`: Changes to asynchronous API functions to no longer use functions with the same name as synchronous functions (such as `get`, `update`), but instead use functions withe prefixed `a`, such as `aget`, `aupdate`. The original usage remains, but will be removed in subsequent versions.

## v2.6.0

Release Date: 2024/11/11

### New features

* Add a built-in [Operations and management system](../../guide/ops), capable of real-time observation and management of API services
* Support `Perference` configuration and adjust some feature parameters of UtilMeta framework
* Support for mounting of [Declarative Web Client](../../guide/client), automatic generation of hooks and client code
* Supports the creation and update of relationship fields and relationship objects in `orm.Schema`

### Optimized

* Refactoring optimizes the implementation of the API plug-in system so that the execution order logic of the API plug-in is the same as that of the decorator.
* Optimize `orm.Query` logic for `distinct` by adding configurable `__distinct__` parameters
* Optimization supports type hint resolution for local variables ( `locals()`)
* The new `request` parameters and properties of the `Error` error object can access the current API request, which is more convenient for the processing of the error handling plug-in.
* Methods that support the Response object

### Fix

* Fix calling of asynchronous plug-ins
* Fix filename logic in `filename` sending and processing `multipart/form-data` data
* Optimize the handling of files in the response

### Compatibility

* Fix abnormal behavior of SQLite on windows and lower Python (3.9)

## v2.5.8

Release Date: 2024/9/21

### Optimized

* Support for yaml profiles
* Support automatic installation of dependencies required to run the server `backend`

### Fix

* Fixed some issues with openapi documentation generation

## v2.5.6
Release Date: 2024/8/16

### Fix

* Fixed compatibility issues related to JWT authentication

## v2.5.5
Release Date: 2024/7/20

### Fix

* Fixed issues related to OpenAPI documentation generation

## v2.5.2
Release Date: 4/24/24

## v2.4
Release Date: 1/29/2024

### New features

* Basic [Declarative Web client](../../guide/client) features are supported

## v2.3
Released Date: 2024/1/24

### API changes

* Adjusted the login function `login` parameters and JWT authentication component parameters for user authentication

## v2.2
Released Date: 2024/1/20

### Optimized

* Optimize authentication and API usage related to Session

## v.2.1
Released Date: 2023/12/18

### New features

* The first release of the V2 version of the framework, providing declarative API and ORM features

## v1
Period: 2019/11 ~ 2023/11

Older versions of the UtilMeta framework are no longer supported
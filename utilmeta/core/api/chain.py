from typing import OrderedDict, Tuple, Callable
from utilmeta.conf import Preference
import inspect
from functools import wraps
from utilmeta.utils import Error, PluginTarget, PluginEvent, exceptions
from utilmeta.core.request import Request
from .plugins.base import process_request, process_response, handle_error
from .endpoint import Endpoint


class BaseChainBuilder:
    def __init__(self, *targets: PluginTarget):
        self.targets = targets
        self.pref = Preference.get()

    def chain_plugins(
        self,
        *events: PluginEvent,
        required: bool = False,
        reverse: bool = False,
        asynchronous: bool = None,
    ) -> Tuple[Callable, ...]:
        targets = self.targets
        _classes = set()
        for target in reversed(targets) if reverse else targets:
            if not isinstance(target, PluginTarget):
                continue

            plugins: OrderedDict = target._plugins

            if not plugins or not isinstance(plugins, dict):
                continue

            for plugin_cls, plugin in (
                reversed(plugins.items()) if reverse else plugins.items()
            ):
                if plugin_cls in _classes:
                    # in case for more than 1 plugin target
                    continue

                handlers = [
                    event.get(plugin, target=target, asynchronous=asynchronous)
                    for event in events
                ]

                if not any(handlers):
                    continue

                _classes.add(plugin_cls)
                yield tuple(handlers)

        if required and not _classes:
            yield tuple(None for _ in events)

    @classmethod
    def process(cls, obj, handler: Callable):
        if handler:
            try:
                res = handler(obj)
            except NotImplementedError:
                return obj
            if res is None:
                return obj
            return res
        return obj

    @classmethod
    async def async_process(cls, obj, handler: Callable):
        if handler:
            try:
                res = handler(obj)
                if inspect.isawaitable(res):
                    res = await res
            except NotImplementedError:
                return obj
            if res is None:
                return obj
            return res
        return obj


class APIChainBuilder(BaseChainBuilder):
    def __init__(self, api, endpoint: Endpoint = None):
        from utilmeta.core.api import API

        if not isinstance(api, API):
            raise TypeError(f"Invalid API: {api}")
        super().__init__(endpoint or api)
        self.api = api
        self.endpoint = endpoint

    @property
    def idempotent(self):
        if self.endpoint:
            return self.endpoint.idempotent
        return None

    async def async_api_handler(
        self,
        api,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
    ):
        retry_index = 0
        while True:
            try:
                api.request.adaptor.update_context(
                    retry_index=retry_index, idempotent=self.idempotent
                )
                req = api.request
                if request_handler:
                    req = await self.async_process(api.request, request_handler)
                if isinstance(req, Request):
                    api.request = req
                    response = handler(api)
                    if inspect.isawaitable(response):
                        response = await response
                else:
                    response = req
                if response_handler:
                    res = await self.async_process(
                        api._make_response(response, force=True), response_handler
                    )
                else:
                    # successfully get response without response handler
                    # no matter what is it
                    res = response
                    break
            except Exception as e:
                err = Error(e, request=api.request)
                if error_handler:
                    err = await self.async_process(err, error_handler)
                if isinstance(err, Error):
                    raise err.throw()
                res = err
            if isinstance(res, Request):
                api.request = res
            else:
                break
            retry_index += 1
            if retry_index >= self.pref.api_max_retry_loops:
                raise exceptions.MaxRetriesExceed(
                    max_retries=self.pref.api_max_retry_loops
                )
        return res

    def api_handler(
        self,
        api,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
    ):
        retry_index = 0
        while True:
            try:
                api.request.adaptor.update_context(
                    retry_index=retry_index, idempotent=self.idempotent
                )
                req = api.request
                if request_handler:
                    req = self.process(api.request, request_handler)
                if isinstance(req, Request):
                    api.request = req
                    response = handler(api)
                else:
                    response = req
                if response_handler:
                    res = self.process(
                        api._make_response(response, force=True), response_handler
                    )
                else:
                    # successfully get response without response handler
                    # no matter what is it
                    res = response
                    break
            except Exception as e:
                err = Error(e, request=api.request)
                if error_handler:
                    err = self.process(err, error_handler)
                if isinstance(err, Error):
                    raise err.throw()
                res = err
            if isinstance(res, Request):
                api.request = res
            else:
                break
            retry_index += 1
            if retry_index >= self.pref.api_max_retry_loops:
                raise exceptions.MaxRetriesExceed(
                    max_retries=self.pref.api_max_retry_loops
                )
        return res

    def chain_api_handler(
        self,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
        asynchronous: bool = None,
    ):
        if not any([request_handler, response_handler, error_handler]):
            return handler

        from utilmeta.core.api import API

        if asynchronous:

            @wraps(handler)
            async def wrapper(api: API = self.api):
                return await self.async_api_handler(
                    api,
                    handler,
                    request_handler=request_handler,
                    response_handler=response_handler,
                    error_handler=error_handler,
                )

        else:

            @wraps(handler)
            def wrapper(api: API = self.api):
                return self.api_handler(
                    api,
                    handler,
                    request_handler=request_handler,
                    response_handler=response_handler,
                    error_handler=error_handler,
                )

        return wrapper

    def build_api_handler(self, handler, asynchronous: bool = None):
        # ---
        if asynchronous is None:
            asynchronous = inspect.iscoroutinefunction(
                handler
            ) or inspect.isasyncgenfunction(handler)
        for request_handler, response_handler, error_handler in self.chain_plugins(
            process_request,
            process_response,
            handle_error,
            required=False,
            asynchronous=asynchronous,
        ):
            handler = self.chain_api_handler(
                handler,
                request_handler=request_handler,
                response_handler=response_handler,
                error_handler=error_handler,
                asynchronous=asynchronous,
            )
        return handler

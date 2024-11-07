from utilmeta.core.api.chain import BaseChainBuilder
from .endpoint import ClientEndpoint
from typing import Callable
from utilmeta.core.request import Request
from utilmeta.core.response import Response
from utilmeta.core.api.plugins.base import process_request, process_response, handle_error
import inspect
from functools import wraps
from utilmeta.utils import Error, exceptions


class ClientChainBuilder(BaseChainBuilder):
    def __init__(self, client, endpoint: ClientEndpoint):
        from .base import Client
        if not isinstance(client, Client):
            raise TypeError(f'Invalid Client: {client}')
        if not isinstance(endpoint, ClientEndpoint):
            raise TypeError(f'Invalid client endpoint: {endpoint}')

        super().__init__(endpoint, client)
        self.client = client
        self.endpoint = endpoint

    @property
    def idempotent(self):
        if self.endpoint:
            return self.endpoint.idempotent
        return None

    def parse_response(self, resp):
        resp = self.endpoint.parse_response(
            resp,
            fail_silently=self.client.fail_silently
        )
        if resp.cookies:
            # update response cookies
            self.client.cookies.update(resp.cookies)
        return resp

    async def async_client_handler(
        self,
        request: Request,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
    ):
        retry_index = 0
        while True:
            try:
                request.adaptor.update_context(
                    retry_index=retry_index,
                    idempotent=self.idempotent
                )
                req = request
                if request_handler:
                    req = await self.async_process(request, request_handler)
                if isinstance(req, Request):
                    response = handler(request)
                    if inspect.isawaitable(response):
                        response = await response
                else:
                    response: Response = self.parse_response(req)

                res = response
                if response_handler:
                    res = await self.async_process(
                        response,
                        response_handler
                    )
                    if isinstance(res, Request):
                        request = res
                    else:
                        res = self.parse_response(res)
                        break
                else:
                    # successfully get response without response handler
                    # no matter what is it
                    break
            except Exception as e:
                err = Error(e, request=request)
                if error_handler:
                    res = await self.async_process(err, error_handler)
                    if isinstance(res, Error):
                        err = res
                    if isinstance(res, Request):
                        request = res
                        continue
                    elif isinstance(res, Response):
                        break
                raise err.throw()

            retry_index += 1
            if retry_index >= self.pref.client_max_retry_loops:
                raise exceptions.MaxRetriesExceed(max_retries=self.pref.client_max_retry_loops)
        return res

    def client_handler(
        self,
        request: Request,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
    ):
        retry_index = 0
        while True:
            try:
                request.adaptor.update_context(
                    retry_index=retry_index,
                    idempotent=self.idempotent
                )
                req = request
                if request_handler:
                    req = self.process(request, request_handler)
                if isinstance(req, Request):
                    response = handler(request)
                else:
                    response: Response = self.parse_response(req)

                res = response
                if response_handler:
                    res = self.process(
                        response,
                        response_handler
                    )
                    if isinstance(res, Request):
                        request = res
                    else:
                        res = self.parse_response(res)
                        break
                else:
                    # successfully get response without response handler
                    # no matter what is it
                    break
            except Exception as e:
                err = Error(e, request=request)
                if error_handler:
                    res = self.process(err, error_handler)
                    if isinstance(res, Error):
                        err = res
                    if isinstance(res, Request):
                        request = res
                        continue
                    elif isinstance(res, Response):
                        break
                raise err.throw()

            retry_index += 1
            if retry_index >= self.pref.client_max_retry_loops:
                raise exceptions.MaxRetriesExceed(max_retries=self.pref.client_max_retry_loops)
        return res

    def chain_client_handler(
        self,
        handler: Callable,
        request_handler=None,
        response_handler=None,
        error_handler=None,
        asynchronous: bool = None
    ):
        if not any([request_handler, response_handler, error_handler]):
            return handler

        if asynchronous:
            @wraps(handler)
            async def wrapper(request: Request):
                return await self.async_client_handler(
                    request, handler,
                    request_handler=request_handler,
                    response_handler=response_handler,
                    error_handler=error_handler
                )
        else:
            @wraps(handler)
            def wrapper(request: Request):
                return self.client_handler(
                    request, handler,
                    request_handler=request_handler,
                    response_handler=response_handler,
                    error_handler=error_handler
                )
        return wrapper

    def build_client_handler(self, handler, asynchronous: bool = None):
        # ---
        if asynchronous is None:
            asynchronous = inspect.iscoroutinefunction(handler) or inspect.isasyncgenfunction(handler)
        for request_handler, response_handler, error_handler in self.chain_plugins(
            process_request, process_response, handle_error,
            required=False,
            asynchronous=asynchronous,
        ):
            handler = self.chain_client_handler(
                handler,
                request_handler=request_handler,
                response_handler=response_handler,
                error_handler=error_handler,
                asynchronous=asynchronous
            )
        if self.endpoint.client_wrap:
            # most outer
            handler = self.chain_client_handler(
                handler,
                request_handler=self.client.process_request,
                response_handler=self.client.process_response,
                error_handler=self.client.handle_error,
                asynchronous=asynchronous
            )
        return handler

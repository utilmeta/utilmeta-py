from .base import ClientRequestAdaptor
import requests


class RequestsRequestAdaptor(ClientRequestAdaptor):
    backend = requests

    def __call__(
        self,
        timeout: float = None,
        allow_redirects: bool = None,
        proxies: dict = None,
        stream: bool = False,
        clients: dict = None,
        **kwargs
    ):
        from utilmeta.core.response.backends.requests import RequestsResponseAdaptor

        session: requests.Session = (clients or {}).get('requests_session')

        if not isinstance(session, requests.Session):
            session = requests.Session()

            if isinstance(clients, dict):
                # set for cache
                clients['requests_session'] = session

        try:
            resp = session.request(
                method=self.request.method,
                url=self.request.url,
                headers=self.request.headers,
                data=self.request.body,
                timeout=float(timeout) if timeout is not None else None,
                proxies=proxies,
                allow_redirects=allow_redirects,
                stream=stream,
            )
            return RequestsResponseAdaptor(resp)
        except Exception:
            if stream:
                if clients is None:
                    session.close()
            raise
        finally:
            if not stream and clients is None:
                session.close()

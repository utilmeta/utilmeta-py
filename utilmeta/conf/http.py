from .base import Config
from typing import Optional


class Cookie(Config):
    Lax = "Lax"
    Strict = "Strict"

    # ---- class attribute hint
    age: int = 31449600
    domain: Optional[str] = None
    name: str = ""
    path: str = "/"
    secure: bool = False
    # cross_domain: bool = False
    http_only: bool = False
    same_site: Optional[str] = "Lax"

    def __init__(
        self,
        age: int = 31449600,
        domain: Optional[str] = None,
        name: str = "",
        path: str = "/",
        secure: bool = False,
        # cross_domain: bool = False,
        http_only: bool = False,
        same_site: Optional[str] = "Lax",
    ):
        super().__init__(locals())

    def as_django(self, prefix: str = None):
        config = {
            "AGE": self.age,
            "DOMAIN": self.domain,
            "HTTPONLY": self.http_only,
            "NAME": self.name,
            "PATH": self.path,
            "SAMESITE": str(self.same_site),
            "SECURE": self.secure,
        }
        return {
            (f"{prefix}_{key}" if prefix else key): val for key, val in config.items()
        }

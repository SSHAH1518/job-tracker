"""Site handler registry.

A handler knows how to open a specific ATS's application form and (optionally)
add site-specific field selectors. All handlers subclass ``SiteHandler`` and are
matched against the job URL by ``get_handler``.
"""
from __future__ import annotations

from urllib.parse import urlparse

from app.browser.sites.base import SiteHandler
from app.browser.sites.ashby import AshbyHandler
from app.browser.sites.generic import GenericHandler
from app.browser.sites.greenhouse import GreenhouseHandler
from app.browser.sites.lever import LeverHandler

_HANDLERS: list[type[SiteHandler]] = [
    GreenhouseHandler,
    LeverHandler,
    AshbyHandler,
]


def get_handler(url: str) -> SiteHandler:
    host = (urlparse(url).hostname or "").lower()
    for handler_cls in _HANDLERS:
        if any(host == d or host.endswith("." + d) for d in handler_cls.domains):
            return handler_cls()
    return GenericHandler()


__all__ = ["SiteHandler", "get_handler"]

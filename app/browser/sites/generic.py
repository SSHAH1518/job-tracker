from __future__ import annotations

from app.browser.sites.base import SiteHandler


class GenericHandler(SiteHandler):
    """Fallback: rely on the base navigate + 'Apply' click + generic form logic."""

    domains = ()
    name = "generic"

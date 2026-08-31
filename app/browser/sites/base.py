"""Base class for site-specific application handlers."""
from __future__ import annotations

from playwright.async_api import Page

from app.logging_setup import get_logger

log = get_logger(__name__)


class SiteHandler:
    #: hostnames this handler claims (exact or as a suffix)
    domains: tuple[str, ...] = ()
    name: str = "generic"

    async def open_application_form(self, page: Page, job_url: str) -> None:
        """Navigate to the page that actually contains the application form.

        Default: just go to the job URL and click an obvious 'Apply' control if
        the form is not already present.
        """
        await page.goto(job_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        if await page.locator("input, textarea, select").count() >= 3:
            return
        for sel in [
            "a:has-text('Apply')",
            "button:has-text('Apply')",
            "a:has-text('Apply now')",
            "button:has-text('Apply for this job')",
        ]:
            loc = page.locator(sel).first
            try:
                if await loc.count():
                    await loc.click()
                    await page.wait_for_timeout(2000)
                    return
            except Exception:  # noqa: BLE001
                continue

    async def extra_field_values(self, page: Page, profile: dict) -> dict[str, str]:
        """Optional {selector: value} pairs specific to this ATS."""
        return {}

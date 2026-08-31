from __future__ import annotations

from playwright.async_api import Page

from app.browser.sites.base import SiteHandler


class AshbyHandler(SiteHandler):
    domains = ("ashbyhq.com", "jobs.ashbyhq.com")
    name = "ashby"

    async def open_application_form(self, page: Page, job_url: str) -> None:
        await page.goto(job_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        # Ashby is a SPA - the form appears after clicking "Application"
        for sel in [
            "a:has-text('Apply for this Job')",
            "button:has-text('Apply')",
            "a:has-text('Application')",
        ]:
            loc = page.locator(sel).first
            try:
                if await loc.count():
                    await loc.click()
                    await page.wait_for_timeout(2500)
                    return
            except Exception:  # noqa: BLE001
                continue

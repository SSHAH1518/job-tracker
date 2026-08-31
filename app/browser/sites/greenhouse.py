from __future__ import annotations

from playwright.async_api import Page

from app.browser.sites.base import SiteHandler


class GreenhouseHandler(SiteHandler):
    domains = ("greenhouse.io", "boards.greenhouse.io", "job-boards.greenhouse.io")
    name = "greenhouse"

    async def open_application_form(self, page: Page, job_url: str) -> None:
        await page.goto(job_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        # Greenhouse embeds the form on the same page; newer boards use #application
        for sel in ["#application", "form#application_form", "a:has-text('Apply')"]:
            loc = page.locator(sel).first
            try:
                if await loc.count():
                    if sel.startswith("a"):
                        await loc.click()
                        await page.wait_for_timeout(1500)
                    return
            except Exception:  # noqa: BLE001
                pass

    async def extra_field_values(self, page: Page, profile: dict) -> dict[str, str]:
        links = profile.get("personal", {}).get("links", {})
        out: dict[str, str] = {}
        if links.get("linkedin"):
            out["input[name='job_application[linkedin_profile]']"] = links["linkedin"]
        if links.get("github"):
            out["input[name*='github']"] = links["github"]
        return out

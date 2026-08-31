from __future__ import annotations

from playwright.async_api import Page

from app.browser.sites.base import SiteHandler


class LeverHandler(SiteHandler):
    domains = ("lever.co", "jobs.lever.co")
    name = "lever"

    async def open_application_form(self, page: Page, job_url: str) -> None:
        # Lever apply form lives at <job_url>/apply
        target = job_url.rstrip("/")
        if not target.endswith("/apply"):
            target += "/apply"
        await page.goto(target, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

    async def extra_field_values(self, page: Page, profile: dict) -> dict[str, str]:
        links = profile.get("personal", {}).get("links", {})
        out: dict[str, str] = {}
        # Lever uses urls[LinkedIn], urls[GitHub], urls[Portfolio]
        if links.get("linkedin"):
            out["input[name='urls[LinkedIn]']"] = links["linkedin"]
        if links.get("github"):
            out["input[name='urls[GitHub]']"] = links["github"]
        if links.get("portfolio"):
            out["input[name='urls[Portfolio]']"] = links["portfolio"]
        return out

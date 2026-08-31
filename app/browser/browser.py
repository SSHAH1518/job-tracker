"""Playwright browser lifecycle.

Uses a *persistent context* pointed at a profile directory so that sites you log
into manually stay logged in across runs. Never stores passwords - you log in
by hand once, the browser keeps the session cookies.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import AsyncIterator

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.config import settings
from app.logging_setup import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT_MS = 30_000


@dataclass
class BrowserSession:
    playwright: Playwright
    context: BrowserContext
    page: Page

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.context.close()
        with contextlib.suppress(Exception):
            await self.playwright.stop()


async def start_browser(headless: bool | None = None) -> BrowserSession:
    profile_dir = settings.browser_profile_path
    profile_dir.mkdir(parents=True, exist_ok=True)

    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=settings.browser_headless if headless is None else headless,
        args=["--disable-blink-features=AutomationControlled"],
        viewport={"width": 1366, "height": 900},
    )
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page = context.pages[0] if context.pages else await context.new_page()
    log.info("Browser started (profile=%s, headless=%s)", profile_dir, context.browser is None)
    return BrowserSession(playwright=pw, context=context, page=page)


@contextlib.asynccontextmanager
async def browser_session(headless: bool | None = None) -> AsyncIterator[BrowserSession]:
    session = await start_browser(headless=headless)
    try:
        yield session
    finally:
        await session.close()


async def manual_login(url: str, wait_seconds: int = 180) -> None:
    """Open a site and pause so you can log in by hand. The persistent profile
    keeps the session for future automated runs."""
    async with browser_session(headless=False) as s:
        await s.page.goto(url)
        log.info("Log in now. Waiting %ss before closing…", wait_seconds)
        await s.page.wait_for_timeout(wait_seconds * 1000)

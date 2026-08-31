"""Small shared HTTP helpers for the discovery connectors."""
from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup

# A browser-ish UA - several public job APIs 403 a bare python-requests UA.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) job-agent/1.0 (personal job search automation)"
)


def get_json(
    url: str,
    *,
    timeout: int = 20,
    ua: str = DEFAULT_UA,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    json_body: Any | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    h = {"User-Agent": ua, "Accept": "application/json"}
    if headers:
        h.update(headers)
    if method.upper() == "POST":
        resp = requests.post(url, headers=h, json=json_body, params=params, timeout=timeout)
    else:
        resp = requests.get(url, headers=h, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, *, timeout: int = 20, ua: str = DEFAULT_UA) -> str:
    resp = requests.get(url, headers={"User-Agent": ua}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)

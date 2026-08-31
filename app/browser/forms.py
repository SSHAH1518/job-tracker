"""Generic form inspection + deterministic field mapping.

This is site-agnostic. Site handlers in ``sites/`` can call these helpers and
add their own selectors on top.

Flow:
  1. inspect_fields(page)      -> list[FormField]
  2. map_profile_values(...)   -> dict[field_key -> value]  (deterministic only)
  3. fill_fields(page, ...)    -> fills text/select/checkbox/radio
  4. collect_open_questions(...)-> textareas / unknown text inputs needing answers
  5. upload_resume(page, path)
  6. find_missing_required(page)-> list of still-empty required fields
Nothing here clicks a final Submit button.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from playwright.async_api import Locator, Page

from app.logging_setup import get_logger

log = get_logger(__name__)

SUBMIT_PATTERN = re.compile(r"\b(submit|apply now|send application|finish)\b", re.I)


@dataclass
class FormField:
    key: str                      # normalized identity (name/id/label slug)
    label: str
    kind: str                     # text | textarea | select | checkbox | radio | file | email | tel
    required: bool
    selector: str                 # a selector Playwright can resolve
    options: list[str] = field(default_factory=list)
    value: Optional[str] = None


# --- profile -> field synonyms -------------------------------------------------

_PROFILE_SYNONYMS: dict[str, list[str]] = {
    "first_name": ["first name", "given name", "firstname"],
    "last_name": ["last name", "family name", "surname", "lastname"],
    "full_name": ["full name", "name", "your name", "candidate name"],
    "email": ["email", "e-mail", "email address"],
    "phone": ["phone", "mobile", "telephone", "contact number"],
    "linkedin": ["linkedin"],
    "github": ["github"],
    "portfolio": ["portfolio", "website", "personal site"],
    "city": ["city", "current city", "location city"],
    "state": ["state", "province", "region"],
    "country": ["country"],
    "location": ["location", "current location", "where are you based"],
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")


def flatten_profile(profile: dict[str, Any]) -> dict[str, str]:
    p = profile.get("personal", {})
    loc = p.get("location", {})
    links = p.get("links", {})
    out = {
        "first_name": p.get("first_name", ""),
        "last_name": p.get("last_name", ""),
        "full_name": p.get("full_name", ""),
        "email": p.get("email", ""),
        "phone": p.get("phone", ""),
        "linkedin": links.get("linkedin", ""),
        "github": links.get("github", ""),
        "portfolio": links.get("portfolio", ""),
        "city": loc.get("city", ""),
        "state": loc.get("state", ""),
        "country": loc.get("country", ""),
        "location": ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
    }
    return {k: v for k, v in out.items() if v}


# --- inspection --------------------------------------------------------------

_JS_INSPECT = r"""
() => {
  const out = [];
  const seen = new Set();
  const labelFor = (el) => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) return l.innerText.trim();
    }
    const wrap = el.closest('label');
    if (wrap) return wrap.innerText.trim();
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    const ph = el.getAttribute('placeholder');
    if (ph) return ph.trim();
    return (el.name || el.id || '').trim();
  };
  const push = (el, kind, options=[]) => {
    const key = (el.name || el.id || labelFor(el) || '').toLowerCase();
    const sig = kind + '::' + key + '::' + labelFor(el);
    if (!key || seen.has(sig)) return;
    seen.add(sig);
    out.push({
      key, kind,
      label: labelFor(el),
      required: el.required || el.getAttribute('aria-required') === 'true',
      name: el.name || '', id: el.id || '',
      options,
    });
  };
  document.querySelectorAll('input').forEach(el => {
    if (['hidden','submit','button','image','reset'].includes(el.type)) return;
    if (el.type === 'radio' || el.type === 'checkbox') { push(el, el.type); return; }
    if (el.type === 'file') { push(el, 'file'); return; }
    push(el, el.type === 'email' || el.type === 'tel' ? el.type : 'text');
  });
  document.querySelectorAll('textarea').forEach(el => push(el, 'textarea'));
  document.querySelectorAll('select').forEach(el => {
    const options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean);
    push(el, 'select', options);
  });
  return out;
}
"""


async def inspect_fields(page: Page) -> list[FormField]:
    raw = await page.evaluate(_JS_INSPECT)
    fields: list[FormField] = []
    for r in raw:
        selector = None
        if r.get("id"):
            selector = f"#{_css_escape(r['id'])}"
        elif r.get("name"):
            selector = f"[name=\"{r['name']}\"]"
        else:
            continue
        fields.append(
            FormField(
                key=_slug(r["key"] or r["label"]),
                label=r["label"],
                kind=r["kind"],
                required=bool(r["required"]),
                selector=selector,
                options=r.get("options", []),
            )
        )
    log.info("Inspected form: %d fields (%d required)", len(fields),
             sum(f.required for f in fields))
    return fields


def _css_escape(value: str) -> str:
    return re.sub(r'(["\\#.:\[\]()])', r"\\\1", value)


# --- mapping ---------------------------------------------------------------

def map_profile_values(fields: list[FormField], profile: dict[str, Any]) -> dict[str, str]:
    """Return {field.selector: value} for fields we can fill deterministically."""
    flat = flatten_profile(profile)
    mapping: dict[str, str] = {}
    for f in fields:
        if f.kind in {"file", "textarea"}:
            continue
        haystack = f"{f.key} {f.label}".lower()
        for profile_key, synonyms in _PROFILE_SYNONYMS.items():
            if profile_key not in flat:
                continue
            if profile_key.replace("_", " ") in haystack or any(s in haystack for s in synonyms):
                mapping[f.selector] = flat[profile_key]
                break
    return mapping


def collect_open_questions(fields: list[FormField], mapped: dict[str, str]) -> list[FormField]:
    """Textareas and unmapped free-text inputs that need a generated answer."""
    questions = []
    for f in fields:
        if f.selector in mapped:
            continue
        if f.kind == "textarea":
            questions.append(f)
        elif f.kind == "text" and f.required and len(f.label) > 12:
            questions.append(f)
    return questions


# --- filling -------------------------------------------------------------

async def fill_fields(page: Page, values: dict[str, str]) -> int:
    filled = 0
    for selector, value in values.items():
        if not value:
            continue
        loc = page.locator(selector).first
        try:
            if await loc.count() == 0:
                continue
            tag = await loc.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                try:
                    await loc.select_option(label=value)
                except Exception:
                    await loc.select_option(value=value)
            else:
                await loc.fill(value)
            filled += 1
        except Exception as exc:  # noqa: BLE001
            log.debug("Could not fill %s: %s", selector, exc)
    log.info("Filled %d/%d deterministic fields", filled, len(values))
    return filled


async def upload_resume(page: Page, resume_path: str) -> bool:
    file_inputs = page.locator("input[type=file]")
    n = await file_inputs.count()
    for i in range(n):
        inp = file_inputs.nth(i)
        try:
            await inp.set_input_files(resume_path)
            log.info("Uploaded resume to file input #%d: %s", i, resume_path)
            return True
        except Exception as exc:  # noqa: BLE001
            log.debug("resume upload attempt %d failed: %s", i, exc)
    log.warning("No usable file input found for resume upload")
    return False


async def find_missing_required(page: Page) -> list[str]:
    missing = await page.evaluate(
        r"""
        () => {
          const bad = [];
          document.querySelectorAll('input,select,textarea').forEach(el => {
            if (['hidden','submit','button'].includes(el.type)) return;
            const req = el.required || el.getAttribute('aria-required') === 'true';
            if (!req) return;
            let empty = false;
            if (el.type === 'checkbox' || el.type === 'radio') {
              const group = document.getElementsByName(el.name);
              empty = !Array.from(group).some(g => g.checked);
            } else {
              empty = !el.value || !el.value.trim();
            }
            if (empty) bad.push(el.name || el.id || el.getAttribute('aria-label') || '?');
          });
          return [...new Set(bad)];
        }
        """
    )
    return missing


async def locate_submit(page: Page) -> Optional[Locator]:
    """Return the final submit control WITHOUT clicking it (for human hand-off)."""
    for sel in ["button[type=submit]", "input[type=submit]", "button"]:
        loc = page.locator(sel)
        for i in range(min(await loc.count(), 20)):
            btn = loc.nth(i)
            text = ((await btn.inner_text()) or (await btn.get_attribute("value")) or "").strip()
            if SUBMIT_PATTERN.search(text):
                return btn
    return None

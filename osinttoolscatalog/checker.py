from __future__ import annotations

import asyncio
import random
import re
import string
from html import unescape
from typing import Callable
from urllib.parse import quote

import httpx

from osinttoolscatalog.sources import load_sources

USER_AGENT = "OsintToolsCatalog/1.0 (+public-profile-checker; respectful rate limits)"

FOUND = "НАЙДЕН"
NOT_FOUND = "НЕ НАЙДЕН"
UNCLEAR = "НЕЯСНО"
SKIPPED = "ПРОПУЩЕН"

_META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_WANTED_META = {"og:title": "title", "og:description": "description",
                "og:image": "image", "description": "description"}


def control_username() -> str:
    """Заведомо несуществующий ник для проверки на ложные срабатывания."""
    return "zq" + "".join(random.choices(string.ascii_lowercase + string.digits, k=14))


def extract_profile_meta(html: str) -> dict:
    """Достаёт из публичной страницы только open-graph метаданные (заголовок, описание, аватар)."""
    meta: dict = {}
    for tag in _META_TAG.findall(html[:200_000]):
        attrs = {m.group(1).lower(): unescape(m.group(2) or m.group(3) or "")
                 for m in _ATTR.finditer(tag)}
        key = attrs.get("property") or attrs.get("name")
        content = attrs.get("content")
        if key and content and key.lower() in _WANTED_META:
            meta.setdefault(_WANTED_META[key.lower()], content.strip()[:300])
    return meta


def classify(source: dict, response: httpx.Response, requested_url: str) -> str:
    code = response.status_code
    if code in (403, 429) or code >= 500:
        return UNCLEAR          # защита сайта / лимиты: не делаем вывод
    if code in (404, 410):
        return NOT_FOUND
    if not 200 <= code < 300:
        return UNCLEAR

    error_type = source.get("error_type", "status")
    body = response.text[:250_000].lower()

    if error_type == "redirect":
        if str(response.url).rstrip("/") != requested_url.rstrip("/"):
            return NOT_FOUND
    for marker in source.get("not_found_markers", []):
        if marker.lower() in body:
            return NOT_FOUND
    found_markers = source.get("found_markers")
    if found_markers and not any(m.lower() in body for m in found_markers):
        return NOT_FOUND
    return FOUND


async def _check(client: httpx.AsyncClient, sem: asyncio.Semaphore, source: dict,
                 username: str, timeout: float, details: bool) -> dict:
    result = {"name": source["name"], "category": source.get("category", "other"),
              "url": None, "status": UNCLEAR, "http_status": None}

    pattern = source.get("regex")
    if pattern and not re.fullmatch(pattern, username):
        result["status"] = SKIPPED
        result["url"] = source["url"].replace("{username}", username)
        return result

    url = source["url"].format(username=quote(username, safe=""))
    result["url"] = url
    async with sem:
        for attempt in range(2):
            try:
                response = await client.get(url, timeout=timeout)
                break
            except (httpx.TimeoutException, httpx.TransportError, httpx.InvalidURL) as exc:
                if attempt == 1:
                    result["error"] = type(exc).__name__
                    return result
                await asyncio.sleep(0.5)

    result["http_status"] = response.status_code
    result["status"] = classify(source, response, url)
    if details and result["status"] == FOUND:
        profile = extract_profile_meta(response.text)
        if profile:
            result["profile"] = profile
    return result


async def check_username_async(
    username: str,
    sources: list[dict] | None = None,
    timeout: float = 8.0,
    concurrency: int = 30,
    verify: bool = False,
    details: bool = False,
    on_result: Callable[[dict], None] | None = None,
    user_agent: str = USER_AGENT,
) -> list[dict]:
    sources = sources if sources is not None else load_sources()
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent": user_agent},
                                 limits=limits) as client:

        async def one(source: dict) -> dict:
            res = await _check(client, sem, source, username, timeout, details)
            if verify and res["status"] == FOUND:
                # Если сайт «находит» и случайный несуществующий ник — доверять ему нельзя.
                ctrl = await _check(client, sem, source, control_username(), timeout, False)
                if ctrl["status"] == FOUND:
                    res["status"] = UNCLEAR
                    res["note"] = "сайт отвечает как на существующий и на случайный ник"
                    res.pop("profile", None)
            if on_result:
                on_result(res)
            return res

        results = await asyncio.gather(*(one(s) for s in sources))

    order = {s["name"]: i for i, s in enumerate(sources)}
    return sorted(results, key=lambda r: order.get(r["name"], 9999))


def check_username(username: str, **kwargs) -> list[dict]:
    return asyncio.run(check_username_async(username, **kwargs))

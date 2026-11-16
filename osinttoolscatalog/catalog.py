from __future__ import annotations

import asyncio
import json
from importlib.resources import files
from typing import Callable

import httpx

OK, BOT_BLOCK, DEAD, ERROR = "OK", "ЗАЩИТА", "НЕ РАБОТАЕТ", "ОШИБКА"


def load_catalog() -> list[dict]:
    raw = files("osinttoolscatalog").joinpath("data/catalog.json").read_text(encoding="utf-8")
    return json.loads(raw)


def get_category(category_id: int) -> dict | None:
    return next((c for c in load_catalog() if c["id"] == category_id), None)


async def _check_one(client: httpx.AsyncClient, sem: asyncio.Semaphore, tool: dict, timeout: float) -> dict:
    res = {"category": tool.get("category_id"), "name": tool["name"], "url": tool["url"],
           "status": ERROR, "http_status": None}
    async with sem:
        for attempt in range(2):
            try:
                r = await client.get(tool["url"], timeout=timeout)
                break
            except (httpx.TimeoutException, httpx.TransportError, httpx.InvalidURL) as exc:
                if attempt == 1:
                    res["error"] = type(exc).__name__
                    return res
                await asyncio.sleep(0.5)
    res["http_status"] = r.status_code
    if r.status_code < 400:
        res["status"] = OK
    elif r.status_code in (401, 403, 429, 999):
        res["status"] = BOT_BLOCK          # сайт жив, но не пускает автоматические запросы
    elif r.status_code in (404, 410):
        res["status"] = DEAD
    else:
        res["status"] = ERROR
    return res


async def check_links_async(tools: list[dict], timeout: float = 10.0, concurrency: int = 20,
                            on_result: Callable[[dict], None] | None = None) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": "OsintToolsCatalog/1.0 (link-check)"}
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        async def one(t):
            r = await _check_one(client, sem, t, timeout)
            if on_result:
                on_result(r)
            return r
        return await asyncio.gather(*(one(t) for t in tools))


def check_links(tools: list[dict], **kwargs) -> list[dict]:
    return asyncio.run(check_links_async(tools, **kwargs))

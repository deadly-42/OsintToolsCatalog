from __future__ import annotations

import json
from importlib.resources import files


def load_sources(categories: list[str] | None = None) -> list[dict]:
    data = files("osinttoolscatalog").joinpath("data/sources.json").read_text(encoding="utf-8")
    items = json.loads(data)
    if categories:
        wanted = {c.lower() for c in categories}
        items = [i for i in items if i.get("category", "").lower() in wanted]
    return items


def categories() -> list[str]:
    return sorted({i.get("category", "other") for i in load_sources()})

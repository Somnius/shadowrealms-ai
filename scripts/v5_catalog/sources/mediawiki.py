"""MediaWiki API adapter (e.g. vtm.paradoxwikis.com), for cross-checking facts.

Only sites listed in docs/rules/v5/catalog/sources.json with "fetch": true may be fetched;
anything else is refused. Fetches are cached under data/catalog-build/online/<site>/ with the
revision id and fetch date, and spaced by the site's rate limit (paradoxwikis robots.txt:
Crawl-delay 15). The HTTP call is injectable, so tests run on recorded fixtures and never
touch the network. Wiki prose (CC BY-SA) is never copied into the catalog: the adapter
hands parsers text with a locator, the overlap gate checks our strings against the cache.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Callable

from ..parsers.common import slug
from .base import Line

USER_AGENT = "ShadowRealmsAI-catalog-build/1.0 (local fact cross-check, rate-limited)"


def load_sources(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {s["site"]: s for s in data.get("sites", [])}


def http_get_json(url: str) -> dict:  # pragma: no cover - network, never called in tests
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class MediaWikiSource:
    def __init__(self, site: str, sources: dict, cache_dir: Path,
                 fetch_json: Callable[[str], dict] | None = None,
                 sleep: Callable[[float], None] = time.sleep, today: Callable[[], str] | None = None):
        cfg = sources.get(site)
        if not cfg or not cfg.get("fetch"):
            raise PermissionError(f"site {site!r} is not allowed for fetching in sources.json")
        self.site = site
        self.api = cfg["api"]
        self.base = cfg.get("base_url", "")
        self.delay = float(cfg.get("rate_limit_seconds", 15))
        self.cache_dir = cache_dir / site
        self._fetch = fetch_json or http_get_json
        self._sleep = sleep
        self._today = today or (lambda: date.today().isoformat())
        self._last = None

    def _cache_file(self, title: str) -> Path:
        return self.cache_dir / f"{slug(title)}.json"

    def page(self, title: str, refresh: bool = False) -> dict:
        """{title, revision, fetched, url, text} for one page; cached."""
        f = self._cache_file(title)
        if f.exists() and not refresh:
            return json.loads(f.read_text(encoding="utf-8"))
        if self._last is not None:
            self._sleep(self.delay)
        q = urllib.parse.urlencode({
            "action": "query", "prop": "revisions", "rvprop": "ids|content", "rvslots": "main",
            "titles": title, "format": "json", "formatversion": "2",
        })
        data = self._fetch(f"{self.api}?{q}")
        self._last = True
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            raise LookupError(f"{self.site}: page {title!r} not found")
        rev = pages[0]["revisions"][0]
        text = rev.get("slots", {}).get("main", {}).get("content", rev.get("content", ""))
        rec = {"title": pages[0]["title"], "revision": rev.get("revid"), "fetched": self._today(),
               "url": f"{self.base}/{urllib.parse.quote(pages[0]['title'].replace(' ', '_'))}",
               "text": text}
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return rec

    def lines(self, title: str) -> list[Line]:
        rec = self.page(title)
        return [Line(text=t, url=rec["url"], revision=rec["revision"])
                for t in rec["text"].splitlines() if t.strip()]


# --------------------------------------------------------------------------- wikitext helpers

def strip_markup(cell: str) -> str:
    """'[[Dominate#Compel|Compel]]' -> 'Compel'; drops refs, bold/italics and templates."""
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_tables(wikitext: str) -> list[list[list[str]]]:
    """Every {| ... |} table as rows of cells (header cells included), markup stripped."""
    tables = []
    for body in re.findall(r"\{\|(.*?)\n\|\}", wikitext, re.S):
        rows: list[list[str]] = []
        cur: list[str] = []
        for raw in body.split("\n")[1:]:
            line = raw.strip()
            if line.startswith("|-"):
                if cur:
                    rows.append(cur)
                cur = []
                continue
            if line.startswith("|+"):
                continue
            if line.startswith("!") or line.startswith("|"):
                sep = "!!" if line.startswith("!") else "||"
                for cell in line[1:].split(sep):
                    if "|" in cell and not cell.strip().startswith("[["):
                        attrs, _, val = cell.partition("|")
                        cell = val if "=" in attrs else cell
                    cur.append(strip_markup(cell))
            elif cur:
                cur[-1] = f"{cur[-1]} {strip_markup(line)}".strip()
        if cur:
            rows.append(cur)
        tables.append(rows)
    return tables


def sections(wikitext: str, level: int = 2) -> dict:
    """'== Name ==' sections -> {name: body text}."""
    marks = "=" * level
    pat = re.compile(rf"^{marks}\s*([^=].*?)\s*{marks}\s*$", re.M)
    out = {}
    hits = list(pat.finditer(wikitext))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(wikitext)
        out[strip_markup(m.group(1))] = wikitext[m.end():end].strip()
    return out

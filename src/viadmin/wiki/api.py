"""Polite, cached client for the vi.wikipedia.org MediaWiki API.

Every raw API response is cached (gzip JSON) under data/raw/wiki_cache/ keyed by a hash of
the request parameters, so reruns are fully offline. Responses are parsed as JSON data only.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import requests

API_URL = "https://vi.wikipedia.org/w/api.php"
USER_AGENT = "ViAdminShift-research/0.1 (24125014@student.hcmus.edu.vn)"
ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "raw" / "wiki_cache"


class WikiClient:
    def __init__(self, cache_dir: Path = CACHE_DIR, min_interval: float = 0.55,
                 offline: bool = False, max_retries: int = 6) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval  # seconds between live requests (<= ~2 req/s)
        self.offline = offline
        self.max_retries = max_retries
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.live_requests = 0
        self._lock = threading.Lock()

    @staticmethod
    def _key(params: dict[str, Any]) -> str:
        blob = json.dumps(sorted((k, str(v)) for k, v in params.items()), ensure_ascii=False)
        return hashlib.sha1(blob.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json.gz"

    def get(self, **params: Any) -> dict:
        params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
        key = self._key({k: v for k, v in params.items() if k != "maxlag"})
        path = self._path(key)
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json.load(f)["response"]
        if self.offline:
            raise RuntimeError(f"offline mode and no cache for {params}")
        data = self._fetch(params)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump({"params": params, "retrieved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "response": data}, f, ensure_ascii=False)
        tmp.replace(path)
        return data

    def _fetch(self, params: dict[str, Any]) -> dict:
        delay = 2.0
        last_err: Exception | None = None
        for _attempt in range(self.max_retries):
            with self._lock:  # global rate limit shared by all worker threads
                wait = self.min_interval - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            try:
                r = self.session.get(API_URL, params=params, timeout=60)
                self.live_requests += 1
                if r.status_code in (429, 500, 502, 503, 504):
                    ra = r.headers.get("Retry-After")
                    time.sleep(float(ra) if ra and ra.isdigit() else delay)
                    delay *= 2
                    last_err = RuntimeError(f"HTTP {r.status_code}")
                    continue
                r.raise_for_status()
                data = r.json()
                err = data.get("error") if isinstance(data, dict) else None
                if err and err.get("code") == "maxlag":
                    time.sleep(delay)
                    delay *= 2
                    last_err = RuntimeError("maxlag")
                    continue
                return data
            except (requests.ConnectionError, requests.Timeout, ValueError) as e:
                last_err = e
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"API request failed after retries: {params}: {last_err}")

    # ---- convenience wrappers -------------------------------------------------
    def resolve_titles(self, titles: list[str]) -> dict[str, dict]:
        """Map each input title to {'title': final title, 'pageid', 'missing', 'disambig'}.

        Follows redirects (and title normalisation)."""
        out: dict[str, dict] = {}
        for i in range(0, len(titles), 50):
            chunk = titles[i:i + 50]
            data = self.get(action="query", titles="|".join(chunk), redirects=1,
                            prop="pageprops", ppprop="disambiguation")
            q = data.get("query", {})
            mapping = {t: t for t in chunk}
            for n in q.get("normalized", []):
                for k, v in mapping.items():
                    if v == n["from"]:
                        mapping[k] = n["to"]
            for rd in q.get("redirects", []):
                for k, v in mapping.items():
                    if v == rd["from"]:
                        mapping[k] = rd["to"]
            pages = {p["title"]: p for p in q.get("pages", [])}
            for t in chunk:
                p = pages.get(mapping[t], {})
                out[t] = {"title": mapping[t], "pageid": p.get("pageid"),
                          "missing": bool(p.get("missing") or p.get("invalid")) or not p,
                          "disambig": "disambiguation" in (p.get("pageprops") or {})}
        return out

    def _one_revision(self, **params: Any) -> tuple[int | None, dict | None]:
        data = self.get(action="query", prop="revisions", rvlimit=1,
                        rvprop="ids|timestamp|size|comment", **params)
        pages = data.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing") or pages[0].get("invalid"):
            return None, None
        revs = pages[0].get("revisions") or []
        return pages[0].get("pageid"), (revs[0] if revs else None)

    def revision_before(self, title: str | None = None, before: str = "",
                        pageid: int | None = None) -> tuple[int | None, dict | None]:
        """(pageid, last revision with timestamp strictly before `before`) — no redirect following."""
        from datetime import datetime, timedelta
        t = datetime.strptime(before, "%Y-%m-%dT%H:%M:%SZ") - timedelta(seconds=1)
        sel = {"pageids": pageid} if pageid else {"titles": title}
        return self._one_revision(rvdir="older", rvstart=t.strftime("%Y-%m-%dT%H:%M:%SZ"), **sel)

    def revisions_before(self, pageid: int, before: str, limit: int = 20) -> list[dict]:
        """Up to `limit` revisions of a page strictly before `before`, newest first."""
        from datetime import datetime, timedelta
        t = datetime.strptime(before, "%Y-%m-%dT%H:%M:%SZ") - timedelta(seconds=1)
        data = self.get(action="query", prop="revisions", pageids=pageid, rvlimit=limit,
                        rvdir="older", rvstart=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        rvprop="ids|timestamp|size|comment|user")
        pages = data.get("query", {}).get("pages", [])
        return (pages[0].get("revisions") or []) if pages else []

    def latest_revision(self, title: str | None = None,
                        pageid: int | None = None) -> tuple[int | None, dict | None]:
        sel = {"pageids": pageid} if pageid else {"titles": title}
        return self._one_revision(**sel)

    def move_log(self, title: str) -> list[dict]:
        data = self.get(action="query", list="logevents", letype="move", letitle=title, lelimit=50)
        return data.get("query", {}).get("logevents", [])

    def merge_log(self, title: str) -> list[dict]:
        """History merges (Special:MergeHistory) *from* this title."""
        data = self.get(action="query", list="logevents", letype="merge", letitle=title, lelimit=50)
        return data.get("query", {}).get("logevents", [])

    def parse_revision(self, revid: int) -> dict:
        """Rendered HTML of an exact revision. Returns {'title','revid','text'(html),'sections'}."""
        data = self.get(action="parse", oldid=revid, prop="text|sections|displaytitle",
                        disablelimitreport=1, disableeditsection=1)
        if "error" in data:
            raise RuntimeError(f"parse error for {revid}: {data['error']}")
        return data["parse"]

    def wikitext_revision(self, revid: int) -> str:
        data = self.get(action="query", prop="revisions", revids=revid, rvprop="content",
                        rvslots="main")
        return data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]

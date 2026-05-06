"""LIHKG fetcher — uses the api_v2 JSON endpoint, not the SPA HTML.

Direct GET on lihkg.com returns only the SPA shell (~3.9 KB, no posts).
The /api_v2/thread/{id}/page/{N} endpoint returns structured JSON when called
with X-LI-DEVICE: android — Cloudflare allows this path through.
"""

import json
import re
from typing import List

from .. import http_fetch
from .base import ForumPage, Post


PLATFORM = "lihkg"
_THREAD_RE = re.compile(r"^https?://lihkg\.com/thread/(\d+)(?:/page/(\d+))?", re.IGNORECASE)


def parse_url(url: str):
    """Return (thread_id, page_num) or None if not an LIHKG thread URL."""
    m = _THREAD_RE.match(url)
    if not m:
        return None
    return (m.group(1), int(m.group(2)) if m.group(2) else 1)


def base_thread_url(thread_id: str) -> str:
    """Canonical thread URL (no /page/N) for source_threads.thread_url."""
    return f"https://lihkg.com/thread/{thread_id}"


def page_url(thread_id: str, page_num: int) -> str:
    return f"https://lihkg.com/thread/{thread_id}/page/{page_num}"


def _strip_html(html: str) -> str:
    """Best-effort tag strip — LIHKG msg HTML is simple (br, img, a, span)."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # collapse runs of >2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # decode common HTML entities
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    return text.strip()


def fetch_page(thread_id: str, page_num: int = 1, *, use_cache: bool = True) -> ForumPage:
    api_url = f"https://lihkg.com/api_v2/thread/{thread_id}/page/{page_num}?order=reply_time"
    body, from_cache = http_fetch.fetch(
        api_url,
        headers={
            "Referer": "https://lihkg.com/",
            "X-LI-DEVICE": "android",
            "X-LI-DEVICE-TYPE": "android",
            "Accept": "application/json",
        },
        cache_scope=PLATFORM,
        cache_key=f"{thread_id}/p{page_num}",
        use_cache=use_cache,
    )
    data = json.loads(body)
    if not data.get("success"):
        raise RuntimeError(f"LIHKG api returned success=0: {body[:200]!r}")
    resp = data["response"]
    raw_posts = resp.get("item_data", []) or []

    posts: List[Post] = []
    for p in raw_posts:
        msg = p.get("msg") or ""
        cleaned = _strip_html(msg)
        if not cleaned:
            continue
        posts.append(Post(
            post_num=int(p.get("msg_num") or 0),
            raw_text=cleaned,
            author=p.get("user_nickname") or (p.get("user", {}) or {}).get("nickname"),
            posted_at=str(p.get("reply_time", "")) or None,
        ))
    return ForumPage(
        platform=PLATFORM,
        thread_id=str(thread_id),
        page_num=page_num,
        total_pages=resp.get("total_page"),
        title=resp.get("title"),
        posts=posts,
        canonical_url=page_url(thread_id, page_num),
        from_cache=from_cache,
    )

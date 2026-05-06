"""Baby Kingdom (baby-kingdom.com) fetcher — Discuz-based forum.

URL forms accepted:
  https://www.baby-kingdom.com/forum.php?mod=viewthread&tid={tid}&page={N}
  https://www.baby-kingdom.com/thread-{tid}-{page}-1.html  (Discuz rewrite)

We always fetch via the canonical forum.php URL; both forms parse cleanly.

Page structure (Discuz):
  <td class="t_f">  → post body (verbatim joke text)
  <i class="authi"> → author label
  <div class="pg">  → pagination wrapper with page=N anchors

Note: Baby Kingdom returns HTTP 200 even for out-of-range pages, re-showing
page 1. We rely on `total_pages` detection from the pagination wrapper to
stop the pipeline cleanly; if only page 1 is referenced, total_pages = 1.
"""

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import http_fetch
from .base import ForumPage, Post


PLATFORM = "babykingdom"

_FORUM_PHP_RE = re.compile(
    r"^https?://(?:www\.)?baby-kingdom\.com/forum\.php\?[^#]*\btid=(\d+)"
    r"(?:[^#]*\bpage=(\d+))?",
    re.IGNORECASE,
)
_REWRITE_RE = re.compile(
    r"^https?://(?:www\.)?baby-kingdom\.com/thread-(\d+)-(\d+)-\d+\.html",
    re.IGNORECASE,
)


def parse_url(url: str):
    """Return (thread_id, page_num) or None if not a Baby Kingdom thread URL."""
    m = _FORUM_PHP_RE.match(url)
    if m:
        return (m.group(1), int(m.group(2)) if m.group(2) else 1)
    m = _REWRITE_RE.match(url)
    if m:
        return (m.group(1), int(m.group(2)))
    return None


def base_thread_url(thread_id: str) -> str:
    return f"https://www.baby-kingdom.com/forum.php?mod=viewthread&tid={thread_id}"


def page_url(thread_id: str, page_num: int) -> str:
    return (
        f"https://www.baby-kingdom.com/forum.php?mod=viewthread"
        f"&tid={thread_id}&page={page_num}"
    )


def _detect_total_pages(soup: BeautifulSoup) -> Optional[int]:
    """Find max page number from the Discuz <div class='pg'> wrapper."""
    pg = soup.find("div", class_="pg") or soup.find(class_="pgs")
    candidates = []
    if pg:
        for a in pg.find_all("a"):
            href = a.get("href") or ""
            m = re.search(r"page=(\d+)", href)
            if m:
                candidates.append(int(m.group(1)))
            # Discuz "末頁" anchor sometimes uses page-tid format
            m = re.search(r"thread-\d+-(\d+)-\d+\.html", href)
            if m:
                candidates.append(int(m.group(1)))
    # Fallback — search any anchor in the page
    if not candidates:
        for a in soup.find_all("a"):
            href = a.get("href") or ""
            m = re.search(r"page=(\d+)", href)
            if m:
                candidates.append(int(m.group(1)))
    if not candidates:
        return 1  # single-page thread
    return max(candidates)


def _extract_posts(soup: BeautifulSoup) -> List[Post]:
    """Each post body lives in <td class='t_f'> or <div class='t_f'>.

    We pair it with the nearest preceding <i class='authi'> for the author.
    """
    posts: List[Post] = []
    seen = 0
    for body in soup.find_all(class_="t_f"):
        raw = body.get_text("\n", strip=True)
        # collapse extreme blank-line runs
        raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
        if not raw:
            continue
        # author: nearest 'authi' walking up to common post container
        author = None
        plc = body.find_parent(class_="plc") or body.find_parent("table")
        if plc:
            au = plc.find(class_="authi")
            if au:
                author = au.get_text(strip=True) or None
        seen += 1
        posts.append(Post(post_num=seen, raw_text=raw, author=author))
    return posts


def fetch_page(thread_id: str, page_num: int = 1, *, use_cache: bool = True) -> ForumPage:
    url = page_url(thread_id, page_num)
    body, from_cache = http_fetch.fetch(
        url,
        cache_scope=PLATFORM,
        cache_key=f"{thread_id}/p{page_num}",
        use_cache=use_cache,
    )
    soup = BeautifulSoup(body, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    return ForumPage(
        platform=PLATFORM,
        thread_id=str(thread_id),
        page_num=page_num,
        total_pages=_detect_total_pages(soup),
        title=title,
        posts=_extract_posts(soup),
        canonical_url=url,
        from_cache=from_cache,
    )

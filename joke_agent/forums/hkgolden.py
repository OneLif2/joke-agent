"""HKGolden fetcher — uses md.hkgolden.com (mobile site) for plain HTML.

The desktop forum.hkgolden.com is JS-heavy and brittle to scrape; the mobile
site at md.hkgolden.com/view.aspx?message=...&page=... returns full HTML
that's already in the user's existing source_ref data.
"""

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import http_fetch
from .base import ForumPage, Post


PLATFORM = "hkgolden"

# Accept all the HKGolden URL shapes found in existing source_threads data:
#   md.hkgolden.com/view.aspx?message=NNN&page=N
#   md.hkgolden.com/view_amp.aspx?message=NNN&page=N
#   forum.hkgolden.com/thread/NNN/page/N
#   forum.hkgolden.com/amp/NNN
# All are normalised to the md.hkgolden.com/view.aspx fetch URL.
_MD_RE = re.compile(
    r"^https?://(?:m|md|www)?\.?hkgolden\.com/view(?:_amp)?\.aspx\?[^#]*message=(\d+)(?:[^#]*page=(\d+))?",
    re.IGNORECASE,
)
_FORUM_RE = re.compile(
    r"^https?://forum\.hkgolden\.com/(?:thread|amp)/(\d+)(?:/page/(\d+))?",
    re.IGNORECASE,
)


def parse_url(url: str):
    """Return (thread_id, page_num) or None if not an HKGolden URL."""
    m = _MD_RE.match(url) or _FORUM_RE.match(url)
    if not m:
        return None
    return (m.group(1), int(m.group(2)) if m.group(2) else 1)


def base_thread_url(thread_id: str) -> str:
    """Canonical thread URL — md.hkgolden.com matches what we actually fetch."""
    return f"https://md.hkgolden.com/view.aspx?message={thread_id}"


def page_url(thread_id: str, page_num: int) -> str:
    return f"https://md.hkgolden.com/view.aspx?message={thread_id}&page={page_num}"


def _detect_total_pages(soup: BeautifulSoup) -> Optional[int]:
    """Find the total page count on md.hkgolden.com.

    Mobile site renders the indicator as 'CURRENT / TOTAL' (e.g. '1 / 8') in
    a pagination element, separate from any 'next page' anchor (which only
    points at page N+1, so anchor scanning under-counts). We pick the largest
    plausible TOTAL among all such patterns.
    """
    candidates = []
    text = soup.get_text(" ", strip=True)
    for m in re.finditer(r"(?<!\d)(\d{1,3})\s*[/／]\s*(\d{1,3})(?!\d)", text):
        cur, tot = int(m.group(1)), int(m.group(2))
        if 1 <= cur <= tot <= 999:
            candidates.append(tot)

    if candidates:
        return max(candidates)

    max_page = 0
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        pm = re.search(r"page=(\d+)", href)
        if pm:
            n = int(pm.group(1))
            if n > max_page:
                max_page = n
    return max_page or None


def _extract_posts(soup: BeautifulSoup) -> List[Post]:
    """HKGolden mobile renders each reply in a <div class='post'> block.

    Within it, the body sits in <div class='post-content2'>; <div class='post-content1'>
    is the same body but prefixed with the author label. We use post-content2 to keep
    raw_text clean of author noise.
    """
    posts: List[Post] = []
    seen_count = 0
    for block in soup.find_all("div", class_="post"):
        body_div = block.find("div", class_="post-content2") or block.find("div", class_="post-content1")
        if not body_div:
            continue
        raw = body_div.get_text("\n", strip=True)
        # squash >2 blank lines
        raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
        if not raw:
            continue
        seen_count += 1
        # author often appears in a sibling element with class 'post-author' or 'user'
        author_el = block.find(attrs={"class": re.compile(r"author|user|name", re.I)})
        author = author_el.get_text(strip=True) if author_el else None
        posts.append(Post(post_num=seen_count, raw_text=raw, author=author))
    return posts


def fetch_page(thread_id: str, page_num: int = 1, *, use_cache: bool = True) -> ForumPage:
    url = f"https://md.hkgolden.com/view.aspx?message={thread_id}&page={page_num}"
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
        canonical_url=page_url(thread_id, page_num),
        from_cache=from_cache,
    )

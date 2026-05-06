"""Auto-pick the next thread page to crawl.

Order of preference:
  1. source_threads rows with status='in_progress', lowest reviewed_pages
  2. source_threads rows with status='pending', oldest first
  3. Seed defaults from goal.md if the table is empty / nothing usable

Returns the SPECIFIC page URL to feed into pipeline.gather() — i.e. with
/page/{N} or &page={N} pointing at reviewed_pages + 1.
"""

import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from .forums import router as forum_router


# Mirrors goal.md §3 Source URL Examples
SEED_THREADS = [
    ("lihkg", "https://lihkg.com/thread/596076"),
    ("lihkg", "https://lihkg.com/thread/34189"),
    ("hkgolden", "https://md.hkgolden.com/view.aspx?message=5191089"),
    ("babykingdom", "https://www.baby-kingdom.com/forum.php?mod=viewthread&tid=662629"),
]


@dataclass
class ThreadPick:
    platform: str
    thread_id: str
    base_thread_url: str
    next_page: int           # the page to crawl next
    total_pages: Optional[int]
    reviewed_pages: int
    status: str
    discovered_via: str = ""

    @property
    def page_url(self) -> str:
        return forum_router.page_url(self.platform, self.thread_id, self.next_page)


def _row_to_pick(row: sqlite3.Row) -> Optional[ThreadPick]:
    parsed = forum_router.parse(row["thread_url"])
    if not parsed:
        return None
    platform, thread_id, _ = parsed
    reviewed = row["reviewed_pages"] or 0
    return ThreadPick(
        platform=platform,
        thread_id=thread_id,
        base_thread_url=row["thread_url"],
        next_page=reviewed + 1,
        total_pages=row["total_pages"],
        reviewed_pages=reviewed,
        status=row["status"],
    )


SUPPORTED_PLATFORMS = ("lihkg", "hkgolden", "babykingdom")


def seed_defaults(conn: sqlite3.Connection, *, platform: Optional[str] = None) -> int:
    """Insert SEED_THREADS into source_threads. Returns count actually inserted.

    If platform is given, only seeds rows for that platform.
    """
    inserted = 0
    for plat, base in SEED_THREADS:
        if platform and plat != platform:
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO source_threads (thread_url, platform, "
            "discovered_via, status) VALUES (?, ?, 'seed', 'pending')",
            (base, plat),
        )
        inserted += cur.rowcount
    return inserted


def auto_pick(
    conn: sqlite3.Connection,
    *,
    platform: Optional[str] = None,
    seed_if_empty: bool = True,
) -> Optional[ThreadPick]:
    """Pick the next thread to crawl, optionally restricted to a platform."""
    if platform and platform not in SUPPORTED_PLATFORMS:
        raise ValueError(
            f"Unknown platform {platform!r} — supported: {SUPPORTED_PLATFORMS}"
        )
    pick = _query_pick(conn, platform=platform)
    if pick:
        return pick
    if seed_if_empty:
        seeded = seed_defaults(conn, platform=platform)
        if seeded > 0:
            return _query_pick(conn, platform=platform)
    return None


def _query_pick(
    conn: sqlite3.Connection,
    *,
    platform: Optional[str] = None,
) -> Optional[ThreadPick]:
    """Run the priority query. Skips threads whose URL we can't parse."""
    sql = (
        "SELECT id, thread_url, platform, reviewed_pages, total_pages, status "
        "FROM source_threads "
        "WHERE status != 'exhausted'"
    )
    params: list = []
    if platform:
        sql += " AND platform = ?"
        params.append(platform)
    sql += (
        " ORDER BY CASE status "
        "          WHEN 'in_progress' THEN 0 "
        "          WHEN 'pending'     THEN 1 "
        "          ELSE                    2 "
        "      END, reviewed_pages ASC, id ASC"
    )
    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        pick = _row_to_pick(r)
        if pick is not None:
            return pick
    return None


def list_active(
    conn: sqlite3.Connection,
    *,
    platform: Optional[str] = None,
) -> List[ThreadPick]:
    """For diagnostics — every non-exhausted, parsable thread."""
    sql = (
        "SELECT id, thread_url, platform, reviewed_pages, total_pages, status "
        "FROM source_threads WHERE status != 'exhausted'"
    )
    params: list = []
    if platform:
        sql += " AND platform = ?"
        params.append(platform)
    sql += " ORDER BY reviewed_pages ASC"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        pick = _row_to_pick(r)
        if pick:
            out.append(pick)
    return out

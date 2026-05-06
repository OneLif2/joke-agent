"""Atomic save: jokes + joke_sources INSERT, markdown append, source_threads update.

All in one DB transaction. Any failure -> ROLLBACK -> markdown unchanged.

The markdown append happens BEFORE COMMIT but is buffered: we write to a
temp staging buffer first, and only append to the file after the SQL
transaction commits. That way if the DB INSERT fails, we don't leave
orphan markdown rows; if the FILE append fails, we don't leave DB rows
without a markdown record (we re-raise and the user can retry).
"""

import os
import sqlite3
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import JOKE_MD_PATH, JOKE_SOURCE_MD_PATH
from . import db as db_mod


@dataclass
class Candidate:
    """One joke candidate ready to save (or be reviewed)."""
    raw_text: str            # the verbatim block from the LLM extractor
    canonical_text: str
    fingerprint: str
    platform: str
    thread_id: str
    page_num: int
    source_url: str          # specific page URL (lihkg.com/.../page/N or md.hkgolden.com/...&page=N)
    source_post_nums: List[int] = field(default_factory=list)
    proposed_tags: List[str] = field(default_factory=list)
    today: str = ""          # source_date

    @property
    def display_text(self) -> str:
        return self.raw_text


@dataclass
class SaveResult:
    saved: List[Tuple[str, Candidate]]   # (joke_id, candidate)
    pages_advanced: List[Tuple[str, str, int]]  # (platform, thread_id, new_reviewed_pages)


def _format_md_block(joke_id: str, c: Candidate, tags: List[str]) -> str:
    tags_line = ", ".join(tags) if tags else "(untagged)"
    return (
        f"\n## {joke_id}\n\n"
        f"- **Source:** {c.source_url}\n"
        f"- **Tags:** {tags_line}\n"
        f"- **Date added:** {c.today}\n"
        f"\n```\n{c.display_text}\n```\n"
    )


def _format_source_md_block(joke_id: str, c: Candidate) -> str:
    posts = ",".join(str(n) for n in c.source_post_nums) if c.source_post_nums else "?"
    return (
        f"\n## {joke_id}\n\n"
        f"- **Platform:** {c.platform}\n"
        f"- **Thread ID:** {c.thread_id}\n"
        f"- **Page:** {c.page_num}\n"
        f"- **Source post(s):** {posts}\n"
        f"- **URL:** {c.source_url}\n"
        f"- **Imported at:** {c.today}\n"
    )


def save(
    conn: sqlite3.Connection,
    candidates: List[Candidate],
    *,
    advance_pages: Optional[List[Tuple[str, str, int, Optional[int]]]] = None,
    md_path: str = JOKE_MD_PATH,
    md_source_path: str = JOKE_SOURCE_MD_PATH,
) -> SaveResult:
    """Atomic save of all candidates.

    advance_pages: list of (platform, thread_id, new_reviewed_pages, total_pages_or_None)
      -- to UPDATE source_threads after saving. Pass [] to skip.
    """
    if not candidates:
        return SaveResult(saved=[], pages_advanced=[])

    # Stage markdown content as strings; only write to disk after SQL commits.
    md_blocks: List[str] = []
    src_md_blocks: List[str] = []

    saved: List[Tuple[str, Candidate]] = []
    pages_advanced: List[Tuple[str, str, int]] = []

    # Pre-flight: re-check fingerprints inside the transaction to catch races.
    with db_mod.transaction(conn):
        for c in candidates:
            if db_mod.fingerprint_exists(conn, c.fingerprint):
                continue  # silently skip if added by a concurrent session

            joke_id = db_mod.next_joke_id(conn)
            now = db_mod.now_iso()
            today = c.today or db_mod.today_iso_date()
            tags_csv = ",".join(c.proposed_tags) if c.proposed_tags else ""

            conn.execute(
                "INSERT INTO jokes (id, canonical_text, display_text, fingerprint, "
                "source_type, source_ref, source_date, tags, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    joke_id, c.canonical_text, c.display_text, c.fingerprint,
                    c.platform, c.source_url, today, tags_csv, now, now,
                ),
            )
            conn.execute(
                "INSERT INTO joke_sources (joke_id, source_type, source_ref, "
                "raw_text, source_date, imported_at) VALUES (?, ?, ?, ?, ?, ?)",
                (joke_id, c.platform, c.source_url, c.raw_text, today, now),
            )
            saved.append((joke_id, c))
            md_blocks.append(_format_md_block(joke_id, c, c.proposed_tags))
            src_md_blocks.append(_format_source_md_block(joke_id, c))

        if advance_pages:
            for platform, thread_id, new_reviewed, total_pages in advance_pages:
                base_url = _base_thread_url(platform, thread_id)
                # INSERT OR IGNORE to handle first-sight threads
                conn.execute(
                    "INSERT OR IGNORE INTO source_threads (thread_url, platform, "
                    "discovered_via, reviewed_pages, status) "
                    "VALUES (?, ?, 'agent_run', 0, 'pending')",
                    (base_url, platform),
                )
                if total_pages is not None:
                    conn.execute(
                        "UPDATE source_threads SET total_pages = ? "
                        "WHERE thread_url = ? AND (total_pages IS NULL OR total_pages != ?)",
                        (total_pages, base_url, total_pages),
                    )
                # advance reviewed_pages, set in_progress, update timestamps
                conn.execute(
                    "UPDATE source_threads SET reviewed_pages = ?, "
                    "last_fetched_at = ?, status = CASE WHEN total_pages IS NOT NULL "
                    "AND ? >= total_pages THEN 'exhausted' ELSE 'in_progress' END, "
                    "updated_at = ? "
                    "WHERE thread_url = ?",
                    (new_reviewed, db_mod.now_iso(), new_reviewed, db_mod.now_iso(), base_url),
                )
                pages_advanced.append((platform, thread_id, new_reviewed))

    # Transaction committed. Now write markdown files.
    if md_blocks:
        _append(md_path, "".join(md_blocks))
    if src_md_blocks:
        _append(md_source_path, "".join(src_md_blocks))

    return SaveResult(saved=saved, pages_advanced=pages_advanced)


def _append(path: str, body: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(body)


def _base_thread_url(platform: str, thread_id: str) -> str:
    # Avoid circular import by inlining the platform branches
    if platform == "lihkg":
        return f"https://lihkg.com/thread/{thread_id}"
    if platform == "hkgolden":
        return f"https://md.hkgolden.com/view.aspx?message={thread_id}"
    if platform == "babykingdom":
        return f"https://www.baby-kingdom.com/forum.php?mod=viewthread&tid={thread_id}"
    raise ValueError(f"Unknown platform: {platform}")

"""Rebuild joke.md and joke_source.md from the DB (the source of truth).

Walks every row in `jokes` and (for joke_source.md) `joke_sources`, writing
fresh markdown in the same format as `writer.py` uses for live appends.
Preserves originals as .bak-<timestamp> files before overwriting.
"""

import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from . import JOKE_MD_PATH, JOKE_SOURCE_MD_PATH


@dataclass
class RebuildResult:
    joke_md_written: int        # joke entries serialised
    joke_md_path: str
    joke_md_backup: Optional[str]
    source_md_written: int      # source records serialised
    source_md_path: str
    source_md_backup: Optional[str]
    missing_sources: List[str]  # joke_ids that have NO joke_sources row
    db_joke_count: int


def _now_tag() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y%m%dT%H%M%S")


def _backup(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    backup = f"{path}.bak-{_now_tag()}"
    shutil.copy2(path, backup)
    return backup


def _format_joke_block(row: sqlite3.Row) -> str:
    tags = (row["tags"] or "").strip()
    tags_pretty = ", ".join(t.strip() for t in tags.split(",") if t.strip()) if tags else "_(untagged)_"
    src = row["source_ref"] or ""
    plat = row["source_type"] or "?"
    src_line = f"{src} ({plat})" if src else f"({plat})"
    src_date = row["source_date"] or "?"
    added = (row["created_at"] or "")[:10] or "?"
    status = row["status"] or "active"

    body = row["display_text"] or ""

    lines = [
        "",
        f"## {row['id']}",
        "",
        f"- **Tags:** {tags_pretty}",
        f"- **Source:** {src_line}",
        f"- **Source date:** {src_date}",
        f"- **Added:** {added}",
    ]
    if status != "active":
        lines.append(f"- **Status:** {status}")
    lines.extend([
        "",
        "```",
        body,
        "```",
        "",
    ])
    return "\n".join(lines)


def _format_source_block(row: sqlite3.Row) -> str:
    src = row["source_ref"] or "?"
    plat = row["source_type"] or "?"
    raw = row["raw_text"] or ""
    src_date = row["source_date"] or "?"
    imp = row["imported_at"] or "?"

    lines = [
        "",
        f"## {row['joke_id']}",
        "",
        f"- **Platform:** {plat}",
        f"- **URL:** {src}",
        f"- **Source date:** {src_date}",
        f"- **Imported at:** {imp}",
        "",
        "```",
        raw,
        "```",
        "",
    ]
    return "\n".join(lines)


def _build_joke_md_header(total: int) -> str:
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S %z")
    return (
        "# 😆 Joke DB Export\n"
        "\n"
        f"Source of truth: `state/jokes.db`. Regenerate with `python3 -m joke_agent rebuild-md`.\n"
        f"\n"
        f"- **Total jokes:** {total}\n"
        f"- **Regenerated:** {today}\n"
        "\n"
        "---\n"
    )


def _build_source_md_header(joke_total: int, source_total: int, missing: int) -> str:
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S %z")
    return (
        "# Joke Sources — Verbatim Import Audit Log\n"
        "\n"
        f"Source of truth: `state/jokes.db.joke_sources`. "
        "Regenerate with `python3 -m joke_agent rebuild-md`.\n"
        f"\n"
        f"- **Joke records covered:** {source_total} of {joke_total} jokes "
        f"({missing} have no joke_sources row in DB)\n"
        f"- **Regenerated:** {today}\n"
        "\n"
        "---\n"
    )


def rebuild(
    conn: sqlite3.Connection,
    *,
    joke_md_path: str = JOKE_MD_PATH,
    source_md_path: str = JOKE_SOURCE_MD_PATH,
) -> RebuildResult:
    joke_rows = conn.execute(
        "SELECT * FROM jokes ORDER BY CAST(SUBSTR(id, 2) AS INTEGER)"
    ).fetchall()

    # joke.md ─────────────────────────────────────────────────
    joke_md_backup = _backup(joke_md_path)
    os.makedirs(os.path.dirname(joke_md_path), exist_ok=True)
    with open(joke_md_path, "w", encoding="utf-8") as f:
        f.write(_build_joke_md_header(len(joke_rows)))
        for row in joke_rows:
            f.write(_format_joke_block(row))

    # joke_source.md ───────────────────────────────────────────
    src_rows = conn.execute(
        "SELECT s.* FROM joke_sources s "
        "JOIN jokes j ON s.joke_id = j.id "
        "ORDER BY CAST(SUBSTR(j.id, 2) AS INTEGER), s.imported_at"
    ).fetchall()
    sources_by_joke = {}
    for r in src_rows:
        sources_by_joke.setdefault(r["joke_id"], []).append(r)

    missing_sources = [r["id"] for r in joke_rows if r["id"] not in sources_by_joke]
    src_total = sum(len(v) for v in sources_by_joke.values())

    source_md_backup = _backup(source_md_path)
    os.makedirs(os.path.dirname(source_md_path), exist_ok=True)
    with open(source_md_path, "w", encoding="utf-8") as f:
        f.write(_build_source_md_header(len(joke_rows), len(sources_by_joke), len(missing_sources)))
        if missing_sources:
            f.write("\n## Jokes missing joke_sources rows\n\n")
            for jid in missing_sources:
                f.write(f"- {jid}\n")
            f.write("\n---\n")
        for r in joke_rows:
            for sr in sources_by_joke.get(r["id"], []):
                f.write(_format_source_block(sr))

    return RebuildResult(
        joke_md_written=len(joke_rows),
        joke_md_path=joke_md_path,
        joke_md_backup=joke_md_backup,
        source_md_written=src_total,
        source_md_path=source_md_path,
        source_md_backup=source_md_backup,
        missing_sources=missing_sources,
        db_joke_count=len(joke_rows),
    )

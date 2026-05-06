"""SQLite layer for jokes.db — connection, schema verification, helpers."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Dict, Iterator, List, Optional, Tuple

from . import DB_PATH


REQUIRED_TABLES: Dict[str, List[str]] = {
    "jokes": [
        "id", "canonical_text", "display_text", "fingerprint",
        "source_type", "source_ref", "source_date", "tags", "status",
        "created_at", "updated_at",
    ],
    "joke_sources": [
        "id", "joke_id", "source_type", "source_ref",
        "raw_text", "source_date", "imported_at",
    ],
    "source_threads": [
        "id", "thread_url", "platform", "discovered_via",
        "total_pages", "reviewed_pages", "status",
        "last_fetched_at", "notes", "created_at", "updated_at",
    ],
    "tag_taxonomy": ["tag", "description", "created_at"],
    "meta": ["key", "value"],
}

LEGACY_TABLES = {"groups", "joke_sends"}


def connect(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r["name"] for r in rows]


def verify_schema(conn: sqlite3.Connection) -> Tuple[bool, List[str]]:
    """Return (ok, problems). ok=True iff every required table+column is present."""
    problems: List[str] = []
    existing = set(list_tables(conn))

    for table, cols in REQUIRED_TABLES.items():
        if table not in existing:
            problems.append(f"missing table: {table}")
            continue
        actual_cols = set(table_columns(conn, table))
        for col in cols:
            if col not in actual_cols:
                problems.append(f"{table}: missing column '{col}'")

    legacy_present = sorted(LEGACY_TABLES & existing)
    if legacy_present:
        problems.append(
            f"legacy tables still present (out of scope per goal.md): {', '.join(legacy_present)}"
        )

    return (not problems, problems)


def now_iso() -> str:
    """ISO 8601 timestamp with HK timezone (+08:00) — matches existing rows."""
    tz = timezone(timedelta(hours=8))
    s = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")
    return s[:-2] + ":" + s[-2:]


def today_iso_date() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).date().isoformat()


def next_joke_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(id, 2) AS INTEGER)) AS max_id FROM jokes"
    ).fetchone()
    n = (row["max_id"] or 0) + 1
    return f"J{n:06d}"


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def valid_tags(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute("SELECT tag FROM tag_taxonomy ORDER BY tag").fetchall()
    return [r["tag"] for r in rows]


def fingerprint_exists(conn: sqlite3.Connection, fingerprint: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM jokes WHERE fingerprint = ? LIMIT 1", (fingerprint,)
    ).fetchone()
    return row is not None


def joke_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM jokes").fetchone()["n"]


def stats(conn: sqlite3.Connection) -> Dict[str, int]:
    return {
        "jokes": joke_count(conn),
        "joke_sources": conn.execute("SELECT COUNT(*) AS n FROM joke_sources").fetchone()["n"],
        "source_threads": conn.execute("SELECT COUNT(*) AS n FROM source_threads").fetchone()["n"],
        "tags": len(valid_tags(conn)),
        "untagged_jokes": conn.execute(
            "SELECT COUNT(*) AS n FROM jokes WHERE tags = '' OR tags IS NULL"
        ).fetchone()["n"],
        "exhausted_threads": conn.execute(
            "SELECT COUNT(*) AS n FROM source_threads WHERE status = 'exhausted'"
        ).fetchone()["n"],
    }

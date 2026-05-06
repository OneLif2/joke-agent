"""Renumber joke IDs to be continuous (J000001..J0000NN, no gaps).

Strategy:
  - Sort by numeric portion of current ID (preserves insertion order)
  - Build mapping: old_id -> new_id
  - 2-pass UPDATE through a 'TMP_' prefix to avoid primary-key collisions
  - FK temporarily disabled during the swap; verified with PRAGMA
    foreign_key_check after COMMIT.
  - DB file is backed up before any changes.
"""

import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

from . import DB_PATH


# Tables besides `jokes` that carry a joke_id column we must keep in sync.
# joke_sends is legacy / out-of-scope per goal.md but may still hold rows.
LINKED_TABLES = ("joke_sources", "joke_sends")


@dataclass
class RenumberPlan:
    mapping: Dict[str, str] = field(default_factory=dict)  # old -> new (ordered)
    rename_pairs: List[Tuple[str, str]] = field(default_factory=list)  # subset where old != new
    unchanged: int = 0
    linked_row_counts: Dict[str, int] = field(default_factory=dict)  # per-table


def build_plan(conn: sqlite3.Connection) -> RenumberPlan:
    rows = conn.execute(
        "SELECT id FROM jokes ORDER BY CAST(SUBSTR(id, 2) AS INTEGER)"
    ).fetchall()
    plan = RenumberPlan()
    for i, row in enumerate(rows, start=1):
        old = row["id"]
        new = f"J{i:06d}"
        plan.mapping[old] = new
        if old == new:
            plan.unchanged += 1
        else:
            plan.rename_pairs.append((old, new))

    # Count linked rows that will be touched (across both passes)
    affected_olds = [old for old, _ in plan.rename_pairs]
    for tbl in LINKED_TABLES:
        try:
            if not affected_olds:
                plan.linked_row_counts[tbl] = 0
                continue
            placeholders = ",".join("?" * len(affected_olds))
            n = conn.execute(
                f"SELECT COUNT(*) FROM {tbl} WHERE joke_id IN ({placeholders})",
                affected_olds,
            ).fetchone()[0]
            plan.linked_row_counts[tbl] = n
        except sqlite3.OperationalError:
            # table doesn't exist
            plan.linked_row_counts[tbl] = -1
    return plan


def render_plan(plan: RenumberPlan) -> str:
    lines = [f"Renumber plan ({len(plan.mapping)} jokes):"]
    for old, new in plan.mapping.items():
        if old == new:
            lines.append(f"  {old}    (unchanged)")
        else:
            lines.append(f"  {old} → {new}")
    lines.append("")
    lines.append(f"  unchanged              : {plan.unchanged}")
    lines.append(f"  renamed                : {len(plan.rename_pairs)}")
    for tbl, n in plan.linked_row_counts.items():
        if n >= 0:
            lines.append(f"  {tbl + ' rows to update':23s}: {n}")
        else:
            lines.append(f"  {tbl:23s}: (table not present)")
    return "\n".join(lines)


def backup_db(db_path: str = DB_PATH) -> str:
    tz = timezone(timedelta(hours=8))
    tag = datetime.now(tz).strftime("%Y%m%dT%H%M%S")
    backup = f"{db_path}.bak-renumber-{tag}"
    shutil.copy2(db_path, backup)
    return backup


def _detect_linked_tables(conn: sqlite3.Connection) -> List[str]:
    out = []
    for tbl in LINKED_TABLES:
        try:
            conn.execute(f"SELECT 1 FROM {tbl} LIMIT 1")
            out.append(tbl)
        except sqlite3.OperationalError:
            continue
    return out


def execute(conn: sqlite3.Connection, plan: RenumberPlan) -> None:
    """Atomically rename IDs. Caller is responsible for the DB backup."""
    if not plan.rename_pairs:
        return

    linked = _detect_linked_tables(conn)

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        try:
            # Pass 1: rename old → TMP_<old> (avoids any PK collision)
            for old, _ in plan.rename_pairs:
                tmp = "TMP_" + old
                conn.execute("UPDATE jokes SET id = ? WHERE id = ?", (tmp, old))
                for tbl in linked:
                    conn.execute(
                        f"UPDATE {tbl} SET joke_id = ? WHERE joke_id = ?",
                        (tmp, old),
                    )
            # Pass 2: rename TMP_<old> → new
            for old, new in plan.rename_pairs:
                tmp = "TMP_" + old
                conn.execute("UPDATE jokes SET id = ? WHERE id = ?", (new, tmp))
                for tbl in linked:
                    conn.execute(
                        f"UPDATE {tbl} SET joke_id = ? WHERE joke_id = ?",
                        (new, tmp),
                    )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    # Integrity check
    bad = conn.execute("PRAGMA foreign_key_check").fetchall()
    if bad:
        raise RuntimeError(
            f"foreign_key_check FAILED after renumber: {bad}. "
            f"Restore from backup."
        )

    # Verify no stray TMP_ rows
    stragglers = conn.execute(
        "SELECT id FROM jokes WHERE id LIKE 'TMP_%' UNION ALL "
        + " UNION ALL ".join(
            f"SELECT joke_id FROM {tbl} WHERE joke_id LIKE 'TMP_%'"
            for tbl in linked
        )
    ).fetchall()
    if stragglers:
        raise RuntimeError(f"TMP_ stragglers found after renumber: {stragglers}")

"""Pre-run health checks: bridge reachability + DB schema integrity."""

import os
from dataclasses import dataclass
from typing import List, Optional

from . import DB_PATH, LLM_BASE_URL, LLM_MODEL
from . import db as db_mod
from .llm import LLMClient, LLMError


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str

    def render(self) -> str:
        mark = "OK " if self.ok else "FAIL"
        return f"  [{mark}] {self.name}: {self.detail}"


def check_db(db_path: str = DB_PATH) -> List[CheckResult]:
    results: List[CheckResult] = []
    if not os.path.exists(db_path):
        results.append(CheckResult("db.path", False, f"{db_path} does not exist"))
        return results
    results.append(CheckResult("db.path", True, db_path))

    try:
        conn = db_mod.connect(db_path)
    except Exception as e:
        results.append(CheckResult("db.connect", False, repr(e)))
        return results

    try:
        ok, problems = db_mod.verify_schema(conn)
        if ok:
            results.append(CheckResult("db.schema", True, "all 5 required tables + columns present"))
        else:
            for p in problems:
                results.append(CheckResult("db.schema", False, p))
        stats = db_mod.stats(conn)
        results.append(CheckResult(
            "db.stats",
            True,
            f"jokes={stats['jokes']}, sources={stats['joke_sources']}, "
            f"threads={stats['source_threads']} ({stats['exhausted_threads']} exhausted), "
            f"tags={stats['tags']}, untagged={stats['untagged_jokes']}",
        ))
    finally:
        conn.close()
    return results


def check_bridge(base_url: str = LLM_BASE_URL, model: str = LLM_MODEL) -> List[CheckResult]:
    results: List[CheckResult] = []
    client = LLMClient(base_url=base_url, model=model)

    try:
        models = client.models()
    except LLMError as e:
        results.append(CheckResult(
            "bridge.reachable",
            False,
            f"{base_url} — {e}. Try: systemctl --user restart codex-ollama-bridge",
        ))
        return results
    results.append(CheckResult("bridge.reachable", True, f"{base_url} returned {len(models)} model(s)"))

    if model in models:
        results.append(CheckResult("bridge.model", True, f"{model} is advertised"))
    else:
        sample = ", ".join(models[:5]) + (" ..." if len(models) > 5 else "")
        results.append(CheckResult(
            "bridge.model",
            False,
            f"{model} not in advertised list (got: {sample})",
        ))

    try:
        reply = client.chat(
            [{"role": "user", "content": "Reply with exactly: PING_OK"}],
        )
        if "PING_OK" in reply:
            results.append(CheckResult("bridge.chat", True, f"round-trip OK ({len(reply)} chars)"))
        else:
            results.append(CheckResult(
                "bridge.chat",
                True,
                f"responded but unexpected content: {reply!r}",
            ))
    except LLMError as e:
        results.append(CheckResult("bridge.chat", False, str(e)))
    return results


def check_all() -> Optional[bool]:
    """Run every check; return True if all pass, False otherwise."""
    sections = [
        ("Database", check_db()),
        ("LLM Bridge", check_bridge()),
    ]
    all_ok = True
    for title, checks in sections:
        print(f"== {title} ==")
        for c in checks:
            print(c.render())
            if not c.ok:
                all_ok = False
    print()
    print("OVERALL:", "PASS" if all_ok else "FAIL")
    return all_ok

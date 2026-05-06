"""Command-line entry point for the joke agent.

Phase 1 commands:
  health      — verify DB schema and bridge reachability
  verify-db   — print DB schema status only
  chat        — one-shot LLM call (smoke-test the bridge)
  stats       — print DB row counts

Phase 2 (in progress):
  fetch       — fetch one forum page (LIHKG/HKGolden) and print posts
"""

import argparse
import sys
from typing import List, Optional

from . import LLM_BASE_URL, LLM_MODEL
from . import db as db_mod
from . import health as health_mod
from . import mode as mode_mod
from . import pipeline as pipeline_mod
from . import rebuild_md as rebuild_md_mod
from . import renumber as renumber_mod
from . import review as review_mod
from . import sources as sources_mod
from . import writer as writer_mod
from .forums import router as forum_router
from .http_fetch import FetchError
from .llm import LLMClient, LLMError, LLMQuotaError
from .mode import Mode


def cmd_health(args: argparse.Namespace) -> int:
    ok = health_mod.check_all()
    return 0 if ok else 1


def cmd_verify_db(args: argparse.Namespace) -> int:
    results = health_mod.check_db()
    for r in results:
        print(r.render())
    return 0 if all(r.ok for r in results) else 1


def cmd_chat(args: argparse.Namespace) -> int:
    client = LLMClient(base_url=args.base_url, model=args.model)
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    try:
        reply = client.chat(messages)
    except LLMError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(reply)
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    mode = mode_mod.from_env_or_flag(args.review)
    print(f"[mode={mode}] fetching {args.url}")
    try:
        page = forum_router.fetch(args.url, use_cache=not args.no_cache)
    except (ValueError, FetchError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    cache_tag = "(cached)" if page.from_cache else "(live)"
    print(f"  platform     : {page.platform} {cache_tag}")
    print(f"  thread_id    : {page.thread_id}")
    print(f"  title        : {page.title}")
    print(f"  page_num     : {page.page_num}")
    print(f"  total_pages  : {page.total_pages}")
    print(f"  posts        : {len(page.posts)}")
    print(f"  canonical_url: {page.canonical_url}")

    show_n = args.show
    if show_n > 0 and page.posts:
        print()
        print(f"-- showing first {min(show_n, len(page.posts))} post(s) --")
        for p in page.posts[:show_n]:
            print()
            print(f"  [#{p.post_num}] author={p.author!r}")
            preview = p.raw_text[:300] + ("..." if len(p.raw_text) > 300 else "")
            for line in preview.splitlines():
                print(f"    {line}")
    return 0


def cmd_fetch_jokes(args: argparse.Namespace) -> int:
    mode = mode_mod.from_env_or_flag(args.review)
    conn = db_mod.connect()

    seed_url = args.url
    if not seed_url:
        platform = getattr(args, "platform", None)
        try:
            pick = sources_mod.auto_pick(conn, platform=platform)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            conn.close()
            return 1
        if pick is None:
            scope = f"for platform={platform}" if platform else ""
            print(f"ERROR: no usable source_threads {scope} and seeding failed.",
                  file=sys.stderr)
            conn.close()
            return 1
        seed_url = pick.page_url
        platform_filter = f" [filter: {platform}]" if platform else ""
        print(f"[auto-pick]{platform_filter} {pick.platform}/{pick.thread_id}  "
              f"page {pick.next_page} of {pick.total_pages or '?'}  "
              f"({pick.status}, reviewed={pick.reviewed_pages})")
        print(f"[auto-pick] URL: {seed_url}")

    print(f"[mode={mode}] target={args.count} url={seed_url}")

    llm = LLMClient(base_url=args.base_url, model=args.model)
    try:
        result = pipeline_mod.gather(
            seed_url,
            args.count,
            llm=llm,
            conn=conn,
            max_pages=args.max_pages,
            progress=lambda m: print(f"  [pipeline] {m}"),
            use_cache=not args.no_cache,
        )
    except LLMQuotaError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print(
            "\nOptions while waiting:\n"
            "  1. Wait for the quota reset, then re-run the same command.\n"
            "  2. Use the nvidia-ollama-bridge fallback (gemma-4-31b-it):\n"
            "       python3 -m joke_agent fetch-jokes 5 \\\n"
            "         --base-url http://127.0.0.1:11545/v1 \\\n"
            "         --model google/gemma-4-31b-it",
            file=sys.stderr,
        )
        conn.close()
        return 2
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        conn.close()
        return 1

    n = len(result.candidates)
    print(f"\n[pipeline] gathered {n} candidate(s) across pages "
          f"{result.pages_processed}")

    if n == 0:
        print("No new candidates found — nothing to do.")
        conn.close()
        return 0

    if mode == Mode.TEST:
        to_save = review_mod.review(result.candidates)
        if not to_save:
            print("\nAbandoned. No DB writes; reviewed_pages NOT incremented "
                  "(same pages will be re-crawled next run).")
            conn.close()
            return 0
        print(f"\nSaving {len(to_save)} of {n} candidate(s)…")
    else:
        # LIVE mode — auto-save everything we gathered
        to_save = result.candidates
        print(f"\n[live mode] auto-saving {n} candidate(s)…")

    advance_pages = pipeline_mod.advance_args(result, save_count=len(to_save))
    save_result = writer_mod.save(conn, to_save, advance_pages=advance_pages)
    print(f"\nSaved {len(save_result.saved)} joke(s):")
    for joke_id, c in save_result.saved:
        tags = ",".join(c.proposed_tags)
        print(f"  {joke_id}  [{tags}]  {c.display_text[:60]!r}…")
    if save_result.pages_advanced:
        for plat, tid, n_pages in save_result.pages_advanced:
            print(f"  source_threads: {plat}/{tid} reviewed_pages = {n_pages}")
    conn.close()
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    conn = db_mod.connect()
    try:
        stats = db_mod.stats(conn)
        for k, v in stats.items():
            print(f"  {k:18s} {v}")
        next_id = db_mod.next_joke_id(conn)
        print(f"  {'next_joke_id':18s} {next_id}")
    finally:
        conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="joke_agent", description="Cantonese joke agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("health", help="Run all pre-flight checks")
    sp.set_defaults(func=cmd_health)

    sp = sub.add_parser("verify-db", help="Verify DB schema only")
    sp.set_defaults(func=cmd_verify_db)

    sp = sub.add_parser("stats", help="Print DB row counts")
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("chat", help="One-shot LLM call (smoke test)")
    sp.add_argument("prompt", help="User prompt text")
    sp.add_argument("--system", help="Optional system prompt", default=None)
    sp.add_argument("--base-url", default=LLM_BASE_URL)
    sp.add_argument("--model", default=LLM_MODEL)
    sp.set_defaults(func=cmd_chat)

    sp = sub.add_parser("fetch", help="Fetch one forum page (LIHKG/HKGolden)")
    sp.add_argument("url", help="Forum thread page URL")
    sp.add_argument("--review", action="store_true",
                    help="Test mode (review-before-save) — doesn't affect fetch but is plumbed")
    sp.add_argument("--no-cache", action="store_true", help="Bypass cache; force live fetch")
    sp.add_argument("--show", type=int, default=2, help="Print preview of first N posts (0=none)")
    sp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser(
        "fetch-jokes",
        help="End-to-end: fetch → extract → dedup → tag → (review) → save",
    )
    sp.add_argument("count", type=int, nargs="?", default=5,
                    help="Target number of unique candidate jokes to gather (default 5)")
    sp.add_argument("--url", default=None,
                    help="Forum thread page URL (omit to auto-pick from source_threads)")
    sp.add_argument("--platform", choices=sources_mod.SUPPORTED_PLATFORMS, default=None,
                    help="Restrict auto-pick to one platform (lihkg | hkgolden)")
    sp.add_argument("--review", action="store_true",
                    help="Test mode: review candidates before save (recommended)")
    sp.add_argument("--no-cache", action="store_true", help="Force live forum fetch")
    sp.add_argument("--max-pages", type=int, default=10,
                    help="Max pages to crawl while gathering candidates")
    sp.add_argument("--base-url", default=LLM_BASE_URL)
    sp.add_argument("--model", default=LLM_MODEL)
    sp.set_defaults(func=cmd_fetch_jokes)

    # Shorthand: `python -m joke_agent test [N]` = fetch-jokes N --review (auto-pick source)
    sp = sub.add_parser(
        "test",
        help="One-shot test mode — auto-pick source, fetch, review-before-save",
    )
    sp.add_argument("count", type=int, nargs="?", default=5,
                    help="Target number of candidate jokes (default 5)")
    sp.add_argument("--url", default=None,
                    help="Override auto-pick with an explicit URL")
    sp.add_argument("--platform", choices=sources_mod.SUPPORTED_PLATFORMS, default=None,
                    help="Restrict auto-pick to one platform (lihkg | hkgolden)")
    sp.add_argument("--max-pages", type=int, default=10)
    sp.add_argument("--no-cache", action="store_true")
    sp.add_argument("--base-url", default=LLM_BASE_URL)
    sp.add_argument("--model", default=LLM_MODEL)
    sp.set_defaults(func=_cmd_test_shortcut)

    sp = sub.add_parser(
        "sources",
        help="List currently-active source_threads (auto-pick candidates)",
    )
    sp.add_argument("--platform", choices=sources_mod.SUPPORTED_PLATFORMS, default=None,
                    help="Filter to one platform")
    sp.set_defaults(func=cmd_sources)

    sp = sub.add_parser(
        "rebuild-md",
        help="Rebuild joke.md and joke_source.md from the DB (backs up originals)",
    )
    sp.set_defaults(func=cmd_rebuild_md)

    sp = sub.add_parser(
        "renumber",
        help="Renumber joke IDs to be continuous (J000001..J0000NN, no gaps)",
    )
    sp.add_argument("--dry-run", action="store_true",
                    help="Show the rename plan only, make no changes")
    sp.add_argument("--yes", action="store_true",
                    help="Skip the y/N confirmation prompt")
    sp.add_argument("--no-rebuild-md", action="store_true",
                    help="Skip the joke.md / joke_source.md rebuild step at the end")
    sp.set_defaults(func=cmd_renumber)

    return p


def cmd_renumber(args: argparse.Namespace) -> int:
    conn = db_mod.connect()
    try:
        plan = renumber_mod.build_plan(conn)
        print(renumber_mod.render_plan(plan))

        if not plan.rename_pairs:
            print("\nNothing to renumber — IDs are already continuous.")
            return 0

        if args.dry_run:
            print("\n[dry-run] no changes made.")
            return 0

        if not args.yes:
            try:
                ans = input("\nProceed? [y/N]: ").strip().lower()
            except EOFError:
                ans = ""
            if ans != "y":
                print("Aborted.")
                return 0

        backup = renumber_mod.backup_db()
        print(f"\nDB backup: {backup}")
        renumber_mod.execute(conn, plan)
        print("Renumber complete; foreign_key_check passed.")

        if not args.no_rebuild_md:
            print("\nRebuilding joke.md / joke_source.md ...")
            result = rebuild_md_mod.rebuild(conn)
            print(f"  joke.md         : {result.joke_md_written} entries "
                  f"(backup: {result.joke_md_backup})")
            print(f"  joke_source.md  : {result.source_md_written} rows "
                  f"(backup: {result.source_md_backup})")
        return 0
    finally:
        conn.close()


def _cmd_test_shortcut(args: argparse.Namespace) -> int:
    """`test` is just `fetch-jokes --review` with auto-pick enabled."""
    args.review = True
    return cmd_fetch_jokes(args)


def cmd_rebuild_md(args: argparse.Namespace) -> int:
    conn = db_mod.connect()
    try:
        result = rebuild_md_mod.rebuild(conn)
    finally:
        conn.close()
    print(f"Rebuilt joke.md       → {result.joke_md_path}")
    print(f"  jokes serialised   : {result.joke_md_written}")
    if result.joke_md_backup:
        print(f"  backup            : {result.joke_md_backup}")
    print()
    print(f"Rebuilt joke_source.md → {result.source_md_path}")
    print(f"  source rows         : {result.source_md_written}")
    if result.source_md_backup:
        print(f"  backup             : {result.source_md_backup}")
    if result.missing_sources:
        print(f"\n[warning] {len(result.missing_sources)} joke(s) have no joke_sources row:")
        for jid in result.missing_sources:
            print(f"    {jid}")
        print("  Listed at the top of joke_source.md as well.")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    conn = db_mod.connect()
    platform = getattr(args, "platform", None)
    try:
        picks = sources_mod.list_active(conn, platform=platform)
        if not picks:
            scope = f" matching --platform={platform}" if platform else ""
            print(f"(no active source_threads{scope} — `test` will seed defaults from goal.md)")
            for plat, base in sources_mod.SEED_THREADS:
                if platform and plat != platform:
                    continue
                print(f"  seed: {plat:9s} {base}")
            return 0
        title = f"Active threads ({len(picks)})"
        if platform:
            title += f" — filtered to platform={platform}"
        print(title + ":")
        for p in picks:
            tot = p.total_pages or "?"
            print(f"  {p.platform:9s} {p.base_thread_url[:55]:55s} "
                  f"reviewed={p.reviewed_pages}/{tot}  next_page={p.next_page}  [{p.status}]")
        first = picks[0]
        print()
        print(f"`test` would pick: {first.platform}/{first.thread_id} page {first.next_page}")
        print(f"  → {first.page_url}")
        return 0
    finally:
        conn.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

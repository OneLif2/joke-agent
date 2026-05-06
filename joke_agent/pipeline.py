"""Pipeline: fetch pages → extract jokes → dedup → tag → produce Candidates.

Stops when target_count unique candidates reached, or max_pages crawled,
or thread exhausted.

In TEST mode, the caller takes the returned candidates to a review UI and
later passes them to writer.save() for the chosen subset.
In LIVE mode, the caller can pass everything to writer.save() directly.
"""

import sqlite3
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from . import canonicalize, db as db_mod, extract, fingerprint, tagging
from .forums import router as forum_router
from .forums.base import ForumPage
from .llm import LLMClient
from .writer import Candidate


@dataclass
class GatherResult:
    candidates: List[Candidate]
    pages_processed: List[int]   # absolute page numbers fully run through extraction
    last_page_total: Optional[int]
    platform: str
    thread_id: str


ProgressCallback = Callable[[str], None]


def _noop(msg: str) -> None:
    pass


def gather(
    seed_url: str,
    target_count: int,
    *,
    llm: LLMClient,
    conn: sqlite3.Connection,
    max_pages: int = 30,
    progress: ProgressCallback = _noop,
    use_cache: bool = True,
) -> GatherResult:
    parsed = forum_router.parse(seed_url)
    if not parsed:
        raise ValueError(f"Unsupported URL: {seed_url}")
    platform, thread_id, start_page = parsed

    valid_tags = db_mod.valid_tags(conn)
    if not valid_tags:
        raise RuntimeError("tag_taxonomy is empty — cannot tag candidates")

    candidates: List[Candidate] = []
    pages_processed: List[int] = []
    last_page_total: Optional[int] = None

    cur_page = start_page
    crawled = 0
    today = db_mod.today_iso_date()

    while len(candidates) < target_count and crawled < max_pages:
        progress(f"fetch page {cur_page} of thread {platform}/{thread_id}")
        try:
            page: ForumPage = forum_router.fetch(
                _page_url(platform, thread_id, cur_page),
                use_cache=use_cache,
            )
        except Exception as e:
            progress(f"  fetch failed: {e}")
            break
        last_page_total = page.total_pages or last_page_total
        if not page.posts:
            progress(f"  page {cur_page} has 0 posts — assuming end of thread")
            break

        progress(f"  {len(page.posts)} posts; running LLM boundary detection")
        try:
            blocks = extract.extract_jokes(page.posts, llm)
        except Exception as e:
            progress(f"  boundary detection failed: {e}")
            blocks = []
        progress(f"  LLM returned {len(blocks)} candidate joke(s)")

        for blk in blocks:
            if len(candidates) >= target_count:
                break
            display_text = blk.text
            canonical = canonicalize.normalise(display_text)
            fp = fingerprint.compute(canonical)
            if db_mod.fingerprint_exists(conn, fp):
                progress(f"  skip duplicate (fp={fp[:8]}…) already in DB")
                continue
            if any(c.fingerprint == fp for c in candidates):
                progress(f"  skip duplicate (fp={fp[:8]}…) already in this batch")
                continue

            try:
                tags = tagging.classify(display_text, valid_tags, llm)
            except Exception as e:
                progress(f"  tag classification failed, defaulting to 其他笑話: {e}")
                tags = ["其他笑話"]
            progress(f"  + new candidate (fp={fp[:8]}…, tags={','.join(tags)})")

            candidates.append(Candidate(
                raw_text=display_text,
                canonical_text=canonical,
                fingerprint=fp,
                platform=platform,
                thread_id=thread_id,
                page_num=cur_page,
                source_url=page.canonical_url,
                source_post_nums=blk.source_post_nums,
                proposed_tags=tags,
                today=today,
            ))

        pages_processed.append(cur_page)
        crawled += 1

        if page.total_pages and cur_page >= page.total_pages:
            progress(f"  reached total_pages={page.total_pages}; stopping")
            break
        cur_page += 1

    return GatherResult(
        candidates=candidates,
        pages_processed=pages_processed,
        last_page_total=last_page_total,
        platform=platform,
        thread_id=thread_id,
    )


def _page_url(platform: str, thread_id: str, page_num: int) -> str:
    if platform == "lihkg":
        return f"https://lihkg.com/thread/{thread_id}/page/{page_num}"
    if platform == "hkgolden":
        return f"https://md.hkgolden.com/view.aspx?message={thread_id}&page={page_num}"
    raise ValueError(f"Unknown platform: {platform}")


def advance_args(result: GatherResult, save_count: int) -> List[Tuple[str, str, int, Optional[int]]]:
    """Build the advance_pages argument for writer.save().

    Per goal.md: reviewed_pages only advances when at least one candidate is saved.
    On full abandon (save_count == 0), pages stay so they'll be re-crawled.
    """
    if save_count == 0 or not result.pages_processed:
        return []
    new_reviewed = max(result.pages_processed)
    return [(result.platform, result.thread_id, new_reviewed, result.last_page_total)]

"""LLM-based joke boundary detection.

Given a list of forum posts (Post[]) from one page, return the list of
self-contained joke text blocks contained within them. The LLM decides what
counts as a joke vs. a reply/reaction/off-topic comment.

Critical rule (from goal.md): the returned joke text must be VERBATIM —
no rewriting, no summarising, no fixing typos. We post-validate by checking
that each returned text appears as a substring of the concatenated post text.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .forums.base import Post
from .llm import LLMClient, LLMError, LLMQuotaError


@dataclass
class JokeBlock:
    """A candidate joke extracted from one or more posts on a page."""
    text: str                       # verbatim joke text (display_text)
    source_post_nums: List[int] = field(default_factory=list)


SYSTEM_PROMPT = (
    "You are extracting self-contained jokes from a Cantonese / Traditional "
    "Chinese forum thread page.\n"
    "A 'joke' has a clear setup and punchline. SKIP posts that are:\n"
    "  - reactions or emotes (e.g. ':o)', '哈哈', '正', single emoji)\n"
    "  - replies / commentary on a joke from elsewhere\n"
    "  - off-topic chat, voting, '留名', etc.\n"
    "  - spam, link-only posts, or posts that just quote another post\n"
    "\n"
    "Output STRICT JSON, no prose, no code fences, in this shape:\n"
    '{"jokes": [{"post_nums": [N], "text": "VERBATIM TEXT"}]}\n'
    "\n"
    "Rules:\n"
    "  - 'text' MUST be the verbatim joke text — never rewrite, summarise, "
    "translate, or fix typos. Copy exact characters, including punctuation "
    "and line breaks.\n"
    "  - 'post_nums' lists the source post numbers (the [#N] labels in the "
    "input). If a single joke spans multiple consecutive posts, list them all.\n"
    "  - If a single post contains multiple distinct jokes, return them as "
    "separate entries.\n"
    "  - If no posts contain a self-contained joke, return {\"jokes\": []}.\n"
)


def _format_posts_for_prompt(posts: List[Post]) -> str:
    chunks = []
    for p in posts:
        author = p.author or "unknown"
        chunks.append(f"[#{p.post_num}] (by {author}):\n{p.raw_text}")
    return "\n\n---\n\n".join(chunks)


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove first fence line and trailing ```
        s = re.sub(r"^```(?:json)?\s*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    return s.strip()


def _parse_response(content: str) -> List[JokeBlock]:
    body = _strip_code_fence(content)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        # Try to find a {...} block within the response
        m = re.search(r"\{[\s\S]+\}", body)
        if not m:
            raise
        data = json.loads(m.group(0))
    out: List[JokeBlock] = []
    for entry in data.get("jokes", []):
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        nums = entry.get("post_nums") or []
        try:
            nums = [int(n) for n in nums]
        except (ValueError, TypeError):
            nums = []
        out.append(JokeBlock(text=text, source_post_nums=nums))
    return out


def _verify_verbatim(blocks: List[JokeBlock], posts: List[Post]) -> List[JokeBlock]:
    """Drop any block whose text is not a substring of the page's combined raw text.

    Cheap defence against the LLM rewriting / summarising. Tolerates whitespace
    differences by comparing on collapsed-whitespace versions.
    """
    haystack = "\n\n".join(p.raw_text for p in posts)
    haystack_collapsed = re.sub(r"\s+", "", haystack)
    verified: List[JokeBlock] = []
    for blk in blocks:
        needle = re.sub(r"\s+", "", blk.text)
        if needle and needle in haystack_collapsed:
            verified.append(blk)
    return verified


def extract_jokes(
    posts: List[Post],
    llm: LLMClient,
    *,
    max_chars: int = 16000,
    max_attempts: int = 2,
) -> List[JokeBlock]:
    """Run LLM boundary detection on one page's worth of posts.

    Retries on empty / unparseable responses (the bridge occasionally returns
    an empty completion under load). After max_attempts, raises RuntimeError —
    pipeline.gather() catches it and moves on to the next page.
    """
    if not posts:
        return []

    user_msg = _format_posts_for_prompt(posts)
    if len(user_msg) > max_chars:
        user_msg = user_msg[-max_chars:]

    last_reply = ""
    for attempt in range(1, max_attempts + 1):
        try:
            reply = llm.chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
        except LLMQuotaError:
            # Quota error is fatal — retrying just burns more requests.
            raise
        last_reply = reply
        if not reply.strip():
            continue  # transient empty — retry
        try:
            blocks = _parse_response(reply)
            return _verify_verbatim(blocks, posts)
        except json.JSONDecodeError:
            continue  # malformed — retry once

    snippet = last_reply.strip()[:200] or "(empty)"
    raise RuntimeError(
        f"LLM returned no usable response after {max_attempts} attempts; last reply: {snippet!r}"
    )

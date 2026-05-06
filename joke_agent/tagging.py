"""LLM-based tag classification — assigns tags from tag_taxonomy to a joke."""

import re
from typing import List

from .llm import LLMClient


def _build_prompt(joke_text: str, valid_tags: List[str]) -> List[dict]:
    tag_list = ", ".join(valid_tags)
    system = (
        "You are a joke classifier for a Cantonese / Chinese joke database.\n"
        f"Valid tags (you MUST pick from this list, no others): {tag_list}\n"
        "\n"
        "Assign one or more tags to the joke below.\n"
        "Return ONLY the comma-separated tags. No explanation, no code fences, "
        "no leading or trailing text. If no other tag fits, use 其他笑話.\n"
        "Base the tags on the joke content only — ignore any thread title or "
        "user metadata.\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Joke:\n{joke_text}"},
    ]


def classify(joke_text: str, valid_tags: List[str], llm: LLMClient) -> List[str]:
    """Return a list of tags from valid_tags. Always returns at least one tag
    (defaults to 其他笑話 if the LLM produces none or only invalid ones)."""
    if not valid_tags:
        raise ValueError("classify() needs a non-empty valid_tags list")

    reply = llm.chat(_build_prompt(joke_text, valid_tags))
    return _parse_tags(reply, valid_tags)


def _parse_tags(reply: str, valid_tags: List[str]) -> List[str]:
    valid_set = set(valid_tags)
    # Strip code fences / prose wrappers if any
    body = reply.strip()
    body = re.sub(r"^```[a-z]*\n?", "", body)
    body = re.sub(r"\n?```$", "", body)
    body = body.strip().strip(".。 ")

    # Split on common separators
    raw_tokens = re.split(r"[,，、\n;；]+", body)
    out: List[str] = []
    seen = set()
    for tok in raw_tokens:
        t = tok.strip()
        if t in valid_set and t not in seen:
            out.append(t)
            seen.add(t)

    if not out:
        out = ["其他笑話"]
    return out

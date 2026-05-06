"""Test mode review UI — print candidates, prompt user, return chosen subset."""

import sys
from typing import List

from .writer import Candidate


THICK_LINE = "═" * 65
THIN_LINE  = "─" * 65


def _print_candidate(c: Candidate, idx: int, total: int) -> None:
    print(THICK_LINE)
    print(f"  Candidate {idx} of {total}")
    print(THICK_LINE)
    print(f"  Source     : {c.source_url}")
    print(f"  Platform   : {c.platform}")
    posts = ",".join(str(n) for n in c.source_post_nums) if c.source_post_nums else "(unknown)"
    print(f"  Source post: {posts}")
    print(f"  Tags (LLM) : {', '.join(c.proposed_tags) if c.proposed_tags else '(none)'}")
    print(f"  Fingerprint: {c.fingerprint[:8]}…  (not yet in DB)")
    print(THIN_LINE)
    for line in c.display_text.splitlines() or [c.display_text]:
        print(f"  {line}")
    print(THICK_LINE)


def _prompt(text: str) -> str:
    try:
        return input(text).strip().lower()
    except EOFError:
        return "q"


def review(candidates: List[Candidate]) -> List[Candidate]:
    """Display candidates and return the subset the user wants to save.

    Returns:
      []        on abandon / quit
      same list on save-all
      subset    on per-joke selection
    """
    if not candidates:
        print("No candidates to review.")
        return []

    n = len(candidates)
    for i, c in enumerate(candidates, 1):
        print()
        _print_candidate(c, i, n)

    while True:
        print()
        choice = _prompt(
            f"Decision for {n} candidate(s)? "
            "[a]ll save / [n]one (abandon) / [p]er-joke / [q]uit: "
        )
        if choice in ("a", "all", ""):
            return list(candidates)
        if choice in ("n", "none", "abandon"):
            return []
        if choice in ("q", "quit"):
            return []
        if choice in ("p", "per", "perjoke", "per-joke"):
            kept: List[Candidate] = []
            for i, c in enumerate(candidates, 1):
                ans = _prompt(f"  Candidate {i}: save? [y/n] (q to stop): ")
                if ans == "q":
                    print("  stopping per-joke review; saving what's been chosen so far.")
                    break
                if ans in ("y", "yes"):
                    kept.append(c)
            return kept
        print("  invalid choice — type a, n, p, or q")

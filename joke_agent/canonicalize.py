"""Joke text normalisation — produces canonical_text used for fingerprinting.

Goal: two visually-equivalent jokes (different whitespace, line breaks, trailing
spaces) must map to the same canonical_text. We do NOT mutate the original
display_text — that stays verbatim.
"""

import re
import unicodedata


def normalise(text: str) -> str:
    """Trim whitespace, normalise line breaks and Unicode form."""
    if not text:
        return ""
    # NFC unifies different code-point sequences for the same character
    s = unicodedata.normalize("NFC", text)
    # Normalise line endings
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    # Strip per-line, keep blank-line semantics, then collapse 3+ blanks
    lines = [ln.strip() for ln in s.split("\n")]
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    # Collapse runs of in-line whitespace (including full-width space) to one
    s = re.sub(r"[ \t　]+", " ", s)
    return s.strip()

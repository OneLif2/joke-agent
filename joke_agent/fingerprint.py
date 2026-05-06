"""SHA-256 fingerprint of canonical joke text — used as the dedup key."""

import hashlib


def compute(canonical_text: str) -> str:
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

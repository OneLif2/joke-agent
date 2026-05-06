"""File-based response cache for forum fetches.

Polite to forums (less repeat traffic) and lets dev runs work offline once
something is fetched. TTL controls staleness.
"""

import hashlib
import os
import time
from typing import Optional

from . import CACHE_DIR, CACHE_TTL_SECONDS


def _key_path(scope: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, scope, h)


def get(scope: str, key: str, ttl: int = CACHE_TTL_SECONDS) -> Optional[bytes]:
    path = _key_path(scope, key)
    if not os.path.exists(path):
        return None
    age = time.time() - os.path.getmtime(path)
    if age > ttl:
        return None
    with open(path, "rb") as f:
        return f.read()


def put(scope: str, key: str, body: bytes) -> str:
    path = _key_path(scope, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    return path


def invalidate(scope: str, key: str) -> bool:
    path = _key_path(scope, key)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False

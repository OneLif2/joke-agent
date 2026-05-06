"""Polite HTTP fetcher — UA, timeout, rate-limit, optional cache."""

import time
from typing import Dict, Optional, Tuple

import requests

from . import FETCH_DELAY_SECONDS, USER_AGENT
from . import cache as cache_mod


_last_fetch_at = 0.0


class FetchError(RuntimeError):
    pass


def _polite_pause():
    global _last_fetch_at
    now = time.monotonic()
    elapsed = now - _last_fetch_at
    if elapsed < FETCH_DELAY_SECONDS:
        time.sleep(FETCH_DELAY_SECONDS - elapsed)
    _last_fetch_at = time.monotonic()


def fetch(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
    cache_scope: Optional[str] = None,
    cache_key: Optional[str] = None,
    use_cache: bool = True,
) -> Tuple[bytes, bool]:
    """Fetch a URL. Returns (body_bytes, from_cache).

    cache_scope/key omitted -> no caching for this call.
    """
    if use_cache and cache_scope and cache_key:
        cached = cache_mod.get(cache_scope, cache_key)
        if cached is not None:
            return cached, True

    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)

    _polite_pause()
    try:
        r = requests.get(url, headers=h, timeout=timeout)
    except requests.RequestException as e:
        raise FetchError(f"GET {url}: {type(e).__name__}: {e}") from e

    if r.status_code != 200:
        snippet = r.text[:200].replace("\n", " ")
        raise FetchError(f"GET {url}: HTTP {r.status_code} — {snippet!r}")

    body = r.content
    if cache_scope and cache_key:
        cache_mod.put(cache_scope, cache_key, body)
    return body, False

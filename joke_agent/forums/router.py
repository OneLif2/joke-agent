"""Dispatch a URL to the right forum module."""

from typing import Optional, Tuple

from . import babykingdom, hkgolden, lihkg
from .base import ForumPage


# Order matters: most-specific URL patterns first
_MODULES = (lihkg, hkgolden, babykingdom)


def detect_platform(url: str) -> Optional[str]:
    for mod in _MODULES:
        if mod.parse_url(url):
            return mod.PLATFORM
    return None


def parse(url: str) -> Optional[Tuple[str, str, int]]:
    """Return (platform, thread_id, page_num) or None if unknown."""
    for mod in _MODULES:
        parsed = mod.parse_url(url)
        if parsed:
            return (mod.PLATFORM, parsed[0], parsed[1])
    return None


def _resolve(platform: str):
    for mod in _MODULES:
        if mod.PLATFORM == platform:
            return mod
    raise ValueError(f"No fetcher for platform: {platform}")


def fetch(url: str, *, use_cache: bool = True) -> ForumPage:
    parsed = parse(url)
    if not parsed:
        raise ValueError(f"Unknown forum URL: {url}")
    platform, thread_id, page_num = parsed
    return _resolve(platform).fetch_page(thread_id, page_num, use_cache=use_cache)


def base_thread_url(platform: str, thread_id: str) -> str:
    return _resolve(platform).base_thread_url(thread_id)


def page_url(platform: str, thread_id: str, page_num: int) -> str:
    return _resolve(platform).page_url(thread_id, page_num)

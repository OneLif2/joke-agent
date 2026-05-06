"""Dispatch a URL to the right forum module."""

from typing import Optional, Tuple

from . import hkgolden, lihkg
from .base import ForumPage


def detect_platform(url: str) -> Optional[str]:
    if lihkg.parse_url(url):
        return lihkg.PLATFORM
    if hkgolden.parse_url(url):
        return hkgolden.PLATFORM
    return None


def parse(url: str) -> Optional[Tuple[str, str, int]]:
    """Return (platform, thread_id, page_num) or None if unknown."""
    parsed = lihkg.parse_url(url)
    if parsed:
        return (lihkg.PLATFORM, parsed[0], parsed[1])
    parsed = hkgolden.parse_url(url)
    if parsed:
        return (hkgolden.PLATFORM, parsed[0], parsed[1])
    return None


def fetch(url: str, *, use_cache: bool = True) -> ForumPage:
    parsed = parse(url)
    if not parsed:
        raise ValueError(f"Unknown forum URL: {url}")
    platform, thread_id, page_num = parsed
    if platform == lihkg.PLATFORM:
        return lihkg.fetch_page(thread_id, page_num, use_cache=use_cache)
    if platform == hkgolden.PLATFORM:
        return hkgolden.fetch_page(thread_id, page_num, use_cache=use_cache)
    raise ValueError(f"No fetcher for platform: {platform}")


def base_thread_url(platform: str, thread_id: str) -> str:
    if platform == lihkg.PLATFORM:
        return lihkg.base_thread_url(thread_id)
    if platform == hkgolden.PLATFORM:
        return hkgolden.base_thread_url(thread_id)
    raise ValueError(f"Unknown platform: {platform}")


def page_url(platform: str, thread_id: str, page_num: int) -> str:
    if platform == lihkg.PLATFORM:
        return lihkg.page_url(thread_id, page_num)
    if platform == hkgolden.PLATFORM:
        return hkgolden.page_url(thread_id, page_num)
    raise ValueError(f"Unknown platform: {platform}")

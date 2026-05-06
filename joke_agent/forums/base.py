"""Common types for forum platforms."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Post:
    """One raw post from a forum page — pre-LLM, no joke-extraction yet."""
    post_num: int            # 1-indexed position within the thread
    raw_text: str            # verbatim text after HTML strip / whitespace normalisation
    author: Optional[str] = None
    posted_at: Optional[str] = None  # ISO if known


@dataclass
class ForumPage:
    """One fetched page from a forum thread."""
    platform: str            # 'lihkg' | 'hkgolden'
    thread_id: str
    page_num: int            # 1-indexed
    total_pages: Optional[int]
    title: Optional[str]
    posts: List[Post] = field(default_factory=list)
    canonical_url: str = ""  # URL with /page/N for source_ref persistence
    from_cache: bool = False

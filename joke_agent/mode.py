"""Operating mode — Live or Test (review-before-save).

Test mode is the safe default: nothing reaches the DB / markdown without
explicit user approval. Live mode auto-saves.
"""

import enum
import os
from typing import Optional


class Mode(enum.Enum):
    LIVE = "live"
    TEST = "test"

    def __str__(self) -> str:
        return self.value


def from_env_or_flag(review_flag: bool, env: Optional[str] = None) -> Mode:
    """Resolve mode from CLI flag (--review) or env var (JOKE_AGENT_MODE)."""
    if review_flag:
        return Mode.TEST
    val = (env if env is not None else os.environ.get("JOKE_AGENT_MODE", "")).strip().lower()
    if val == "test":
        return Mode.TEST
    return Mode.LIVE

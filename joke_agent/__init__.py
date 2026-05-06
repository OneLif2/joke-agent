"""Cantonese joke fetching agent — see goal.md for the full spec.

All paths and bridge URLs default to the Jetson / Raspberry Pi OpenClaw
layout but are overridable via environment variables — see README.md.
"""

import os

__version__ = "0.1.0"


def _env(name: str, default: str) -> str:
    return os.environ.get(name) or default


# OpenClaw workspace defaults (override with JOKE_AGENT_DB / _JOKE_MD / _SOURCE_MD)
_OPENCLAW_WORKSPACE = _env("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))

DB_PATH = _env("JOKE_AGENT_DB", os.path.join(_OPENCLAW_WORKSPACE, "state", "jokes.db"))
JOKE_MD_PATH = _env("JOKE_AGENT_JOKE_MD", os.path.join(_OPENCLAW_WORKSPACE, "joke.md"))
JOKE_SOURCE_MD_PATH = _env("JOKE_AGENT_SOURCE_MD",
                           os.path.join(_OPENCLAW_WORKSPACE, "joke_source.md"))

# LLM defaults to gemma-4-31b-it via nvidia-ollama-bridge (no quota cap, fast).
# Codex/gpt-5.5 stays available as a fallback for higher-quality runs.
# Override via JOKE_AGENT_LLM_* env vars.
LLM_BASE_URL = _env("JOKE_AGENT_LLM_BASE_URL", "http://127.0.0.1:11545/v1")
LLM_MODEL = _env("JOKE_AGENT_LLM_MODEL", "google/gemma-4-31b-it")
LLM_FALLBACK_BASE_URL = _env("JOKE_AGENT_LLM_FALLBACK_BASE_URL", "http://127.0.0.1:11540/v1")
LLM_FALLBACK_MODEL = _env("JOKE_AGENT_LLM_FALLBACK_MODEL", "openai-codex/gpt-5.5")

CACHE_DIR = _env("JOKE_AGENT_CACHE_DIR", os.path.expanduser("~/.cache/joke_agent"))
CACHE_TTL_SECONDS = int(_env("JOKE_AGENT_CACHE_TTL", str(24 * 3600)))

# Realistic Chrome-on-Android UA, gets us through LIHKG/HKGolden without 403
USER_AGENT = _env(
    "JOKE_AGENT_USER_AGENT",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Mobile Safari/537.36"
)
FETCH_DELAY_SECONDS = float(_env("JOKE_AGENT_FETCH_DELAY", "1.5"))  # politeness pause

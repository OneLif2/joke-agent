"""LLM client — talks to codex-ollama-bridge via OpenAI Chat Completions protocol.

Stdlib only (urllib + json) — no openai package dependency.
"""

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from . import LLM_BASE_URL, LLM_MODEL


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: str = LLM_BASE_URL,
        model: str = LLM_MODEL,
        timeout: float = 120.0,
        api_key: str = "codex-bridge",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    def models(self) -> List[str]:
        req = urllib.request.Request(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                body = json.loads(r.read())
        except urllib.error.URLError as e:
            raise LLMError(f"models() failed: {e}") from e
        return [m["id"] for m in body.get("data", [])]

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        payload: Dict = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise LLMError(f"chat HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"chat connection error: {e.reason}") from e

        choices = body.get("choices") or []
        if not choices:
            raise LLMError(f"chat returned no choices: {body!r}")
        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise LLMError(f"chat returned no content: {body!r}")
        return content

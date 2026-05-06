"""LLM client — talks to codex-ollama-bridge via OpenAI Chat Completions protocol.

Stdlib only (urllib + json) — no openai package dependency.
"""

import json
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from . import LLM_BASE_URL, LLM_MODEL


class LLMError(RuntimeError):
    """Generic LLM client failure. status_code is set when the underlying
    HTTP response carried one."""

    def __init__(self, message: str, *, status_code: Optional[int] = None,
                 body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class LLMQuotaError(LLMError):
    """429 with usage_limit_reached — retrying is pointless until reset."""

    def __init__(self, message: str, *, resets_at: Optional[int] = None,
                 resets_in_seconds: Optional[int] = None,
                 plan_type: Optional[str] = None, body: str = ""):
        super().__init__(message, status_code=429, body=body)
        self.resets_at = resets_at
        self.resets_in_seconds = resets_in_seconds
        self.plan_type = plan_type


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
            # Detect upstream quota exhaustion specifically
            if e.code == 429 and "usage_limit_reached" in detail:
                err = self._parse_quota_error(detail)
                raise err from e
            raise LLMError(f"chat HTTP {e.code}: {detail}",
                           status_code=e.code, body=detail) from e
        except urllib.error.URLError as e:
            raise LLMError(f"chat connection error: {e.reason}") from e

        choices = body.get("choices") or []
        if not choices:
            raise LLMError(f"chat returned no choices: {body!r}")
        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise LLMError(f"chat returned no content: {body!r}")
        return content

    @staticmethod
    def _parse_quota_error(detail: str) -> "LLMQuotaError":
        """Extract resets_at / plan_type from the upstream JSON error body."""
        try:
            err = (json.loads(detail) or {}).get("error", {}) or {}
        except Exception:
            err = {}
        resets_at = err.get("resets_at")
        resets_in = err.get("resets_in_seconds")
        plan = err.get("plan_type")
        msg = (err.get("message") or "usage limit reached")
        if resets_in is not None:
            mins = resets_in // 60
            secs = resets_in % 60
            human = f"{mins}m{secs:02d}s"
            msg = f"LLM quota exhausted ({plan or 'unknown'} plan) — resets in {human}"
        return LLMQuotaError(
            msg,
            resets_at=resets_at,
            resets_in_seconds=resets_in,
            plan_type=plan,
            body=detail,
        )

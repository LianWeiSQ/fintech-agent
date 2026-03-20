from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from .config import ModelRoute


class LiteLLMClient:
    def __init__(self, route: ModelRoute) -> None:
        self.route = route
        self._completion = None
        try:
            from litellm import completion

            self._completion = completion
        except ImportError:
            self._completion = None

    @property
    def available(self) -> bool:
        return (
            self._completion is not None
            and bool(self.route.model)
            and bool(self._resolved_api_key())
        )

    def _resolved_api_key(self) -> str:
        if not self.route.api_key_env:
            return ""
        return os.getenv(self.route.api_key_env, "")

    def _resolved_base_url(self) -> str:
        return self.route.base_url or ""

    def _completion_kwargs(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.route.model,
            "temperature": self.route.temperature,
            "max_tokens": self.route.max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        api_key = self._resolved_api_key()
        base_url = self._resolved_base_url()
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url
        return kwargs

    def complete_text(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self.available:
            return None
        try:
            response = self._completion(**self._completion_kwargs(system_prompt, user_prompt))
            return response["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def translate(self, text: str, target_language: str = "????") -> str:
        if not text:
            return text
        result = self.complete_text(
            system_prompt="You are a financial translator. Keep facts precise.",
            user_prompt=(
                f"Translate the following market news into {target_language}. "
                "Do not add facts. Keep names, numbers, and dates intact.\n\n"
                f"{text}"
            ),
        )
        return result or text

    def summarize_json(self, prompt: str) -> dict[str, Any] | None:
        result = self.complete_text(
            system_prompt="Return valid JSON only.",
            user_prompt=prompt,
        )
        if not result:
            return None
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None

    def snapshot(self) -> dict[str, Any]:
        snapshot = asdict(self.route)
        snapshot["resolved_base_url"] = self._resolved_base_url()
        snapshot["api_key_configured"] = bool(self._resolved_api_key())
        return snapshot

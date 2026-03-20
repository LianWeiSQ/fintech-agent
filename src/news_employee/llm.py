from __future__ import annotations

import json
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
        return self._completion is not None and bool(self.route.model)

    def complete_text(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self.available:
            return None
        try:
            response = self._completion(
                model=self.route.model,
                temperature=self.route.temperature,
                max_tokens=self.route.max_output_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def translate(self, text: str, target_language: str = "简体中文") -> str:
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
        return asdict(self.route)

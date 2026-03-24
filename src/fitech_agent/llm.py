from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from .config import ModelRoute

RESPONSES_PROVIDER_ALIASES = {"codex", "openai_responses", "openai-responses"}
SUPPORTED_REASONING_EFFORTS = {"minimal", "low", "medium", "high", "xhigh"}
SUPPORTED_BACKENDS = {"auto", "litellm", "openai_responses"}


@dataclass(slots=True)
class LLMCompletionResult:
    text: str | None
    error: str | None
    backend: str
    model: str
    base_url: str


class LiteLLMClient:
    def __init__(self, route: ModelRoute) -> None:
        self.route = route
        self._completion = None
        self._openai_client_cls = None
        try:
            from litellm import completion

            self._completion = completion
        except ImportError:
            self._completion = None
        try:
            from openai import OpenAI

            self._openai_client_cls = OpenAI
        except ImportError:
            self._openai_client_cls = None

    @property
    def available(self) -> bool:
        return self._availability_error() is None

    def _resolved_provider(self) -> str:
        return self.route.provider.strip().lower().replace("-", "_")

    def _configured_backend(self) -> str:
        raw = (self.route.backend or os.getenv("OPENAI_BACKEND", "")).strip().lower()
        return raw.replace("-", "_")

    def _configured_model(self) -> str:
        return (self.route.model or os.getenv("OPENAI_MODEL", "")).strip()

    def _resolved_native_model(self) -> str:
        configured = self._configured_model()
        if not configured:
            return ""
        if configured.startswith("openai/"):
            return configured.split("/", 1)[1]
        return configured

    def _resolved_litellm_model(self) -> str:
        configured = self._configured_model()
        if not configured:
            return ""
        if "/" in configured:
            return configured
        if self._resolved_provider() == "openai":
            return f"openai/{configured}"
        if self.route.model:
            return configured
        return f"openai/{configured}"

    def _resolved_backend(self) -> str:
        configured_backend = self._configured_backend()
        if configured_backend in SUPPORTED_BACKENDS and configured_backend != "auto":
            return configured_backend
        native_model = self._resolved_native_model().lower()
        provider = self._resolved_provider()
        if provider in RESPONSES_PROVIDER_ALIASES:
            return "openai_responses"
        if "codex" in native_model:
            return "openai_responses"
        return "litellm"

    def _should_use_openai_responses(self) -> bool:
        return self._resolved_backend() == "openai_responses"

    def _resolved_model(self) -> str:
        if self._should_use_openai_responses():
            return self._resolved_native_model()
        return self._resolved_litellm_model()

    def _resolved_api_key(self) -> str:
        if self.route.api_key_env:
            configured = os.getenv(self.route.api_key_env, "").strip()
            if configured:
                return configured
        if self._should_use_openai_responses() or self._resolved_provider() == "openai":
            return os.getenv("OPENAI_API_KEY", "").strip()
        return ""

    def _resolved_base_url(self) -> str:
        return os.getenv("OPENAI_BASE_URL", "").strip() or self.route.base_url or ""

    def _resolved_reasoning_effort(self) -> str:
        raw = (self.route.reasoning_effort or os.getenv("OPENAI_REASONING_EFFORT", "")).strip().lower()
        return raw if raw in SUPPORTED_REASONING_EFFORTS else ""

    def _availability_error(self) -> str | None:
        if not self._resolved_model():
            return "model_not_configured"
        if not self._resolved_api_key():
            return "api_key_not_configured"
        if self._should_use_openai_responses():
            if self._openai_client_cls is None:
                return "openai_sdk_unavailable"
            return None
        if self._completion is None:
            return "litellm_unavailable"
        return None

    def _openai_client(self) -> Any | None:
        if self._openai_client_cls is None:
            return None
        kwargs: dict[str, Any] = {"api_key": self._resolved_api_key()}
        base_url = self._resolved_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        return self._openai_client_cls(**kwargs)

    def _completion_kwargs(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._resolved_litellm_model(),
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

    def _responses_kwargs(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._resolved_native_model(),
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": self.route.max_output_tokens,
        }
        effort = self._resolved_reasoning_effort()
        if effort:
            kwargs["reasoning"] = {"effort": effort}
        return kwargs

    def complete_text_result(self, system_prompt: str, user_prompt: str) -> LLMCompletionResult:
        backend = self._resolved_backend()
        model = self._resolved_model()
        base_url = self._resolved_base_url()
        availability_error = self._availability_error()
        if availability_error:
            return LLMCompletionResult(
                text=None,
                error=availability_error,
                backend=backend,
                model=model,
                base_url=base_url,
            )
        try:
            if self._should_use_openai_responses():
                client = self._openai_client()
                if client is None:
                    return LLMCompletionResult(
                        text=None,
                        error="openai_client_not_initialized",
                        backend=backend,
                        model=model,
                        base_url=base_url,
                    )
                response = client.responses.create(**self._responses_kwargs(system_prompt, user_prompt))
                text = getattr(response, "output_text", "")
                normalized = text.strip() if isinstance(text, str) and text.strip() else None
                return LLMCompletionResult(
                    text=normalized,
                    error=None if normalized else "empty_response",
                    backend=backend,
                    model=model,
                    base_url=base_url,
                )
            response = self._completion(**self._completion_kwargs(system_prompt, user_prompt))
            text = response["choices"][0]["message"]["content"].strip()
            normalized = text if text else None
            return LLMCompletionResult(
                text=normalized,
                error=None if normalized else "empty_response",
                backend=backend,
                model=model,
                base_url=base_url,
            )
        except Exception as exc:
            return LLMCompletionResult(
                text=None,
                error=f"{type(exc).__name__}: {exc}",
                backend=backend,
                model=model,
                base_url=base_url,
            )

    def complete_text(self, system_prompt: str, user_prompt: str) -> str | None:
        return self.complete_text_result(system_prompt, user_prompt).text

    def translate(
        self,
        text: str,
        target_language: str = "Chinese",
        system_prompt: str | None = None,
    ) -> str:
        if not text:
            return text
        result = self.complete_text(
            system_prompt=system_prompt
            or "You are a financial translator. Keep facts precise.",
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
        snapshot["resolved_model"] = self._resolved_model()
        snapshot["resolved_native_model"] = self._resolved_native_model()
        snapshot["resolved_base_url"] = self._resolved_base_url()
        snapshot["resolved_reasoning_effort"] = self._resolved_reasoning_effort()
        snapshot["availability_error"] = self._availability_error()
        snapshot["api_key_configured"] = bool(self._resolved_api_key())
        snapshot["backend"] = self._resolved_backend()
        return snapshot

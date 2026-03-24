from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fitech_agent.config import ModelRoute
from fitech_agent.llm import LiteLLMClient


class _FakeResponsesAPI:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object):
        self.last_kwargs = dict(kwargs)
        return type("Response", (), {"output_text": "codex response"})()


class _FakeOpenAIClient:
    last_instance: "_FakeOpenAIClient | None" = None

    def __init__(self, **kwargs: object) -> None:
        self.init_kwargs = dict(kwargs)
        self.responses = _FakeResponsesAPI()
        _FakeOpenAIClient.last_instance = self


class LLMClientTests(unittest.TestCase):
    def test_codex_model_uses_openai_responses_api(self) -> None:
        old_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            client = LiteLLMClient(
                ModelRoute(
                    provider="codex",
                    model="gpt-5-codex",
                    api_key_env="OPENAI_API_KEY",
                    reasoning_effort="medium",
                )
            )
            client._openai_client_cls = _FakeOpenAIClient
            client._completion = None

            result = client.complete_text("system", "user")

            self.assertEqual(result, "codex response")
            instance = _FakeOpenAIClient.last_instance
            assert instance is not None
            self.assertEqual(instance.init_kwargs["api_key"], "test-key")
            self.assertEqual(instance.responses.last_kwargs["model"], "gpt-5-codex")
            self.assertEqual(
                instance.responses.last_kwargs["reasoning"],
                {"effort": "medium"},
            )
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_non_codex_model_keeps_litellm_completion_path(self) -> None:
        old_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            client = LiteLLMClient(
                ModelRoute(
                    provider="openai",
                    model="gpt-4.1-mini",
                    api_key_env="OPENAI_API_KEY",
                )
            )
            captured: dict[str, object] = {}

            def fake_completion(**kwargs: object) -> dict[str, object]:
                captured.update(kwargs)
                return {"choices": [{"message": {"content": "litellm response"}}]}

            client._completion = fake_completion
            client._openai_client_cls = _FakeOpenAIClient

            result = client.complete_text("system", "user")

            self.assertEqual(result, "litellm response")
            self.assertEqual(captured["model"], "openai/gpt-4.1-mini")
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_backend_can_force_openai_responses_for_future_models(self) -> None:
        old_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            client = LiteLLMClient(
                ModelRoute(
                    provider="openai",
                    backend="openai_responses",
                    model="gpt-5.4",
                    api_key_env="OPENAI_API_KEY",
                )
            )
            client._openai_client_cls = _FakeOpenAIClient
            client._completion = None

            result = client.complete_text("system", "user")

            self.assertEqual(result, "codex response")
            instance = _FakeOpenAIClient.last_instance
            assert instance is not None
            self.assertEqual(instance.responses.last_kwargs["model"], "gpt-5.4")
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

    def test_complete_text_result_reports_missing_api_key(self) -> None:
        old_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            client = LiteLLMClient(
                ModelRoute(
                    provider="custom",
                    backend="openai_responses",
                    model="gpt-5.4",
                    api_key_env="OPENAI_API_KEY",
                )
            )
            client._openai_client_cls = _FakeOpenAIClient

            result = client.complete_text_result("system", "user")

            self.assertIsNone(result.text)
            self.assertEqual(result.error, "api_key_not_configured")
            self.assertEqual(client.snapshot()["availability_error"], "api_key_not_configured")
        finally:
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key

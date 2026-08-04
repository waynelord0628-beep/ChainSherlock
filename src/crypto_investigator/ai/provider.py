import json
from time import perf_counter

import httpx

from crypto_investigator.ai.errors import (
    AIAuthenticationError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from crypto_investigator.ai.models import AIResponse, AIUsage


class OpenAICompatibleProvider:
    provider_name = "openai-compatible"
    supports_json_schema = True
    supports_streaming = False

    def __init__(self, settings):
        self.settings = settings
        self.model_name = settings.model

    def health_check(self) -> bool:
        return bool(self.settings.api_key and self.settings.base_url)

    def generate(self, prompt: str, schema: dict | None = None) -> AIResponse:
        if not self.settings.api_key:
            raise AIAuthenticationError("AI API key is not configured")
        started = perf_counter()
        payload = {
            "model": self.model_name,
            "temperature": 0,
            "max_tokens": self.settings.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "narrative", "schema": schema},
            }
        try:
            response = httpx.post(
                f"{self.settings.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise AITimeoutError("AI provider timed out") from error
        if response.status_code in {401, 403}:
            raise AIAuthenticationError("AI provider authentication failed")
        if response.status_code == 429:
            raise AIRateLimitError("AI provider rate limit reached")
        if response.is_error:
            raise AIProviderError(
                f"AI provider request failed with status {response.status_code}"
            )
        value = response.json()
        usage = value.get("usage", {})
        content = value["choices"][0]["message"]["content"]
        return AIResponse(
            content,
            AIUsage(
                self.provider_name,
                self.model_name,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                int(usage.get("total_tokens", 0)),
                1,
                False,
                perf_counter() - started,
                None,
            ),
        )


class MockAIProvider:
    provider_name = "mock"
    model_name = "mock-v1"
    supports_json_schema = True
    supports_streaming = False

    def __init__(self, response: str | dict):
        self.response = (
            json.dumps(response, ensure_ascii=False)
            if isinstance(response, dict) else response
        )
        self.calls = 0

    def health_check(self) -> bool:
        return True

    def generate(self, prompt: str, schema: dict | None = None) -> AIResponse:
        self.calls += 1
        return AIResponse(
            self.response,
            AIUsage("mock", "mock-v1", len(prompt) // 4, len(self.response) // 4,
                    (len(prompt) + len(self.response)) // 4, 1),
        )

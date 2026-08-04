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
from crypto_investigator.ai.redaction import redact_text


class OpenAICompatibleProvider:
    provider_name = "openai-compatible"
    supports_json_schema = True
    supports_streaming = False
    endpoint_path = "/chat/completions"

    def __init__(self, settings):
        self.settings = settings
        self.model_name = settings.model

    def health_check(self) -> bool:
        return bool(self.settings.api_key and self.settings.base_url)

    @property
    def endpoint(self) -> str:
        return f"{self.settings.base_url.rstrip('/')}{self.endpoint_path}"

    @property
    def endpoint_label(self) -> str:
        return httpx.URL(self.endpoint).path

    def generate(self, prompt: str, schema: dict | None = None) -> AIResponse:
        if not self.settings.api_key:
            raise AIAuthenticationError("AI API key is not configured")
        started = perf_counter()
        payload = {
            "model": self.model_name,
            "max_completion_tokens": self.settings.max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not self.model_name.casefold().startswith("gpt-5"):
            payload["temperature"] = self.settings.temperature
        if schema:
            normalized_schema = self._normalize_schema(schema)
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "narrative",
                    "strict": True,
                    "schema": normalized_schema,
                },
            }
        endpoint = self.endpoint
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json=payload,
                timeout=self.settings.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise AITimeoutError(
                "AI provider timed out",
                safe_details={"endpoint": self.endpoint_label},
            ) from error
        details = self._safe_error_details(response)
        if response.status_code in {401, 403}:
            raise AIAuthenticationError(
                "AI provider authentication failed", safe_details=details
            )
        if response.status_code == 429:
            raise AIRateLimitError(
                "AI provider rate limit reached", safe_details=details
            )
        if response.is_error:
            raise AIProviderError(
                f"AI provider request failed with status {response.status_code}",
                safe_details=details,
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

    @staticmethod
    def _normalize_schema(schema: dict) -> dict:
        normalized = dict(schema)
        normalized.setdefault("type", "object")
        if normalized["type"] == "object":
            normalized.setdefault("properties", {})
            normalized.setdefault("required", list(normalized["properties"]))
            normalized.setdefault("additionalProperties", False)
        return normalized

    def _safe_error_details(self, response: httpx.Response) -> dict:
        error_value = {}
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                error_value = body["error"]
        except (ValueError, TypeError):
            pass
        return {
            "http_status": response.status_code,
            "error": {
                "type": self._safe_scalar(error_value.get("type")),
                "code": self._safe_scalar(error_value.get("code")),
                "param": self._safe_scalar(error_value.get("param")),
                "message": redact_text(error_value.get("message", ""), 500),
            },
            "x_request_id": redact_text(
                response.headers.get("x-request-id", ""), 200
            ),
            "endpoint": self.endpoint_label,
        }

    @staticmethod
    def _safe_scalar(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return redact_text(value, 200) if isinstance(value, str) else value
        return redact_text(str(value), 200)


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

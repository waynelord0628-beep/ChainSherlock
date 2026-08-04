import json
from time import perf_counter

import httpx

from crypto_investigator.ai.errors import (
    AIAuthenticationError,
    AIContentFilterError,
    AIFinishReasonError,
    AIOutputTruncatedError,
    AIProviderError,
    AIRefusalError,
    AIResponseError,
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
        elif self.settings.reasoning_effort:
            payload["reasoning_effort"] = self.settings.reasoning_effort
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
        try:
            value = response.json()
        except ValueError as error:
            raise AIResponseError(
                "AI provider returned a non-JSON success envelope",
                safe_details={
                    "http_status": response.status_code,
                    "x_request_id": redact_text(
                        response.headers.get("x-request-id", ""), 200
                    ),
                    "endpoint": self.endpoint_label,
                },
            ) from error
        if not isinstance(value, dict):
            raise AIResponseError("AI provider success envelope must be an object")
        choices = value.get("choices")
        usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
        metadata = self._success_metadata(response, value, choices, usage)
        if not isinstance(choices, list) or not choices:
            raise AIResponseError(
                "AI provider returned no choices", safe_details=metadata
            )
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        refusal = message.get("refusal")
        finish_reason = choice.get("finish_reason")
        if refusal:
            raise AIRefusalError("AI provider refused the request", safe_details=metadata)
        if finish_reason == "length":
            raise AIOutputTruncatedError(
                "AI output may be truncated by the completion token limit",
                safe_details=metadata,
            )
        if finish_reason == "content_filter":
            raise AIContentFilterError(
                "AI output was blocked by the content filter", safe_details=metadata
            )
        if finish_reason != "stop":
            raise AIFinishReasonError(
                f"AI output ended with unsupported finish reason: {redact_text(finish_reason, 80)}",
                safe_details=metadata,
            )
        content = message.get("content")
        if not isinstance(content, str) or not content:
            raise AIResponseError(
                "AI provider returned empty response content", safe_details=metadata
            )
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
            metadata,
        )

    def _success_metadata(self, response, value, choices, usage):
        first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        return {
            "endpoint": self.endpoint_label,
            "http_status": response.status_code,
            "x_request_id": redact_text(response.headers.get("x-request-id", ""), 200),
            "response_model": redact_text(value.get("model", ""), 200),
            "response_id": redact_text(value.get("id", ""), 200),
            "created": value.get("created") if isinstance(value.get("created"), (int, float)) else None,
            "system_fingerprint": redact_text(value.get("system_fingerprint", ""), 200),
            "choices_count": len(choices) if isinstance(choices, list) else 0,
            "finish_reason": redact_text(first.get("finish_reason", ""), 80),
            "refusal_present": bool(message.get("refusal")),
            "content_present": isinstance(content, str) and bool(content),
            "content_character_count": len(content) if isinstance(content, str) else 0,
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
        }

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

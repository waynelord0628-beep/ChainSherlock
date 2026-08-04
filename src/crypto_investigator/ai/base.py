from typing import Protocol, runtime_checkable

from crypto_investigator.ai.models import AIResponse


@runtime_checkable
class AIProvider(Protocol):
    provider_name: str
    model_name: str
    supports_json_schema: bool
    supports_streaming: bool

    def generate(self, prompt: str, schema: dict | None = None) -> AIResponse: ...
    def health_check(self) -> bool: ...

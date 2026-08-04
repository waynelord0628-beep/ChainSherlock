from crypto_investigator.ai.errors import AIConfigurationError
from crypto_investigator.ai.provider import MockAIProvider, OpenAICompatibleProvider


class AIProviderFactory:
    @staticmethod
    def create(settings, *, mock_response=None):
        if settings.provider == "openai-compatible":
            return OpenAICompatibleProvider(settings)
        if settings.provider == "mock":
            if mock_response is None:
                raise AIConfigurationError("Mock response is required")
            return MockAIProvider(mock_response)
        if settings.provider == "fallback":
            return None
        raise AIConfigurationError(f"Unknown AI provider: {settings.provider}")

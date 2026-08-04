class AIError(Exception):
    pass


class AIConfigurationError(AIError):
    pass


class AIProviderError(AIError):
    def __init__(self, message: str, *, safe_details: dict | None = None):
        super().__init__(message)
        self.safe_details = safe_details or {}


class AIAuthenticationError(AIProviderError):
    pass


class AIRateLimitError(AIProviderError):
    pass


class AITimeoutError(AIProviderError):
    pass


class AIResponseError(AIError):
    pass


class AIParseError(AIResponseError):
    pass


class AISchemaError(AIResponseError):
    pass


class AIValidationError(AIError):
    pass


class AIHallucinationError(AIValidationError):
    pass


class AICitationError(AIValidationError):
    pass


class AINumericMismatchError(AIValidationError):
    pass


class AIInputLimitError(AIError):
    pass


class NarrativeError(AIError):
    pass

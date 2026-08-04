from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.models import ProviderCapability


class ProviderError(Exception):
    def __init__(
        self,
        *,
        provider: str,
        chain: Chain,
        capability: ProviderCapability,
        safe_message: str,
        retryable: bool = False,
        status_code: int | None = None,
        missing_data_category: str | None = None,
    ) -> None:
        self.provider = provider
        self.chain = chain
        self.capability = capability
        self.safe_message = safe_message
        self.retryable = retryable
        self.status_code = status_code
        self.missing_data_category = missing_data_category
        super().__init__(safe_message)

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "chain": self.chain.value,
            "capability": self.capability.value,
            "message": self.safe_message,
            "retryable": self.retryable,
            "status_code": self.status_code,
            "missing_data_category": self.missing_data_category,
        }


class ProviderUnavailableError(ProviderError):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class ProviderPaginationError(ProviderError):
    pass


class UnsupportedCapabilityError(ProviderError):
    pass


class PartialProviderFailure(ProviderError):
    pass

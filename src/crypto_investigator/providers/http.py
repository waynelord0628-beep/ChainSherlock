from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from crypto_investigator.cache.file_cache import FileCache
from crypto_investigator.cache.keys import build_cache_key
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from crypto_investigator.providers.models import ProviderCapability
from crypto_investigator.providers.rate_limit import AsyncRateLimiter


class ProviderHttpClient:
    def __init__(
        self,
        *,
        provider: str,
        chain: Chain,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        total_timeout: float = 60,
        retries: int = 3,
        rate_limiter: AsyncRateLimiter | None = None,
        client: httpx.AsyncClient | None = None,
        cache: FileCache | None = None,
        refresh: bool = False,
    ) -> None:
        self.provider = provider
        self.chain = chain
        self.retries = max(1, retries)
        timeout = httpx.Timeout(
            timeout=total_timeout,
            connect=connect_timeout,
            read=read_timeout,
        )
        self.client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "ChainSherlock/0.1"},
        )
        self.rate_limiter = rate_limiter or AsyncRateLimiter()
        self.cache = cache
        self.refresh = refresh

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        capability: ProviderCapability,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        cache_key = build_cache_key(
            provider=self.provider,
            chain=self.chain,
            capability=capability,
            identifier=url,
            parameters=params,
            page=(params or {}).get("page") or (params or {}).get("fingerprint"),
        )
        if self.cache is not None:
            cached = self.cache.get_or_none(cache_key, refresh=self.refresh)
            if cached is not None:
                return cached
        retryable = (
            ProviderTimeoutError,
            ProviderRateLimitError,
            ProviderUnavailableError,
        )
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retries),
            wait=wait_exponential(multiplier=0.05, min=0.05, max=1),
            retry=retry_if_exception_type(retryable),
            reraise=True,
        ):
            with attempt:
                await self.rate_limiter.acquire()
                try:
                    response = await self.client.request(
                        method, url, params=params, json=json, headers=headers
                    )
                except httpx.TimeoutException as error:
                    raise ProviderTimeoutError(
                        provider=self.provider,
                        chain=self.chain,
                        capability=capability,
                        safe_message="Provider request timed out",
                        retryable=True,
                        missing_data_category=capability.value,
                    ) from error
                except httpx.TransportError as error:
                    raise ProviderUnavailableError(
                        provider=self.provider,
                        chain=self.chain,
                        capability=capability,
                        safe_message="Provider transport unavailable",
                        retryable=True,
                        missing_data_category=capability.value,
                    ) from error
                self._raise_for_status(response, capability)
                try:
                    payload = response.json()
                    if self.cache is not None:
                        self.cache.set(cache_key, payload)
                    return payload
                except ValueError as error:
                    raise ProviderResponseError(
                        provider=self.provider,
                        chain=self.chain,
                        capability=capability,
                        safe_message="Provider returned malformed JSON",
                        status_code=response.status_code,
                        missing_data_category=capability.value,
                    ) from error

    def _raise_for_status(
        self, response: httpx.Response, capability: ProviderCapability
    ) -> None:
        common = {
            "provider": self.provider,
            "chain": self.chain,
            "capability": capability,
            "status_code": response.status_code,
            "missing_data_category": capability.value,
        }
        if response.status_code in (401, 403):
            raise ProviderAuthenticationError(
                **common,
                safe_message="Provider authentication failed",
            )
        if response.status_code == 429:
            raise ProviderRateLimitError(
                **common,
                safe_message="Provider rate limit reached",
                retryable=True,
            )
        if response.status_code >= 500:
            raise ProviderUnavailableError(
                **common,
                safe_message="Provider service unavailable",
                retryable=True,
            )
        if response.status_code >= 400:
            raise ProviderResponseError(
                **common,
                safe_message="Provider rejected the request",
            )

    async def close(self) -> None:
        await self.client.aclose()

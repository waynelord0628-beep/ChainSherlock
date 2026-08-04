import os

from crypto_investigator.cache.file_cache import FileCache
from crypto_investigator.config import Settings
from crypto_investigator.providers.bitcoin.blockstream import BlockstreamProvider
from crypto_investigator.providers.ethereum.blockscout import BlockscoutProvider
from crypto_investigator.providers.ethereum.etherscan import EtherscanProvider
from crypto_investigator.providers.http import ProviderHttpClient
from crypto_investigator.providers.pagination import PaginationLimits
from crypto_investigator.providers.registry import ProviderRegistry
from crypto_investigator.providers.tron.trongrid import TronGridProvider


class ProviderFactory:
    @staticmethod
    def create_registry(
        settings: Settings, *, refresh: bool = False, cache_ttl: int | None = None
    ) -> ProviderRegistry:
        limits = PaginationLimits(
            max_pages=settings.pagination.max_pages,
            max_records=settings.pagination.max_records,
            page_size=settings.pagination.page_size,
        )
        registry = ProviderRegistry()
        providers = (
            EtherscanProvider(
                os.getenv("ETHERSCAN_API_KEY", ""),
                limits=limits,
                client=ProviderFactory._client("etherscan", settings, refresh, cache_ttl),
            ),
            BlockscoutProvider(
                os.getenv("BLOCKSCOUT_API_URL", "https://eth.blockscout.com"),
                client=ProviderFactory._client("blockscout", settings, refresh, cache_ttl),
            ),
            TronGridProvider(
                os.getenv("TRONGRID_API_KEY", ""),
                limits=limits,
                client=ProviderFactory._client("trongrid", settings, refresh, cache_ttl),
            ),
            BlockstreamProvider(
                base_url=os.getenv(
                    "BLOCKSTREAM_API_URL", "https://blockstream.info/api"
                ),
                limits=limits,
                client=ProviderFactory._client("blockstream", settings, refresh, cache_ttl),
            ),
        )
        for provider in providers:
            registry.register(provider)
        return registry

    @staticmethod
    def _client(
        name: str, settings: Settings, refresh: bool, cache_ttl: int | None
    ) -> ProviderHttpClient:
        from crypto_investigator.domain.transaction import Chain

        chains = {
            "etherscan": Chain.ETHEREUM,
            "blockscout": Chain.ETHEREUM,
            "trongrid": Chain.TRON,
            "blockstream": Chain.BITCOIN,
        }
        return ProviderHttpClient(
            provider=name,
            chain=chains[name],
            connect_timeout=settings.http.connect_timeout_seconds,
            read_timeout=settings.http.read_timeout_seconds,
            total_timeout=settings.http.total_timeout_seconds,
            retries=settings.http.retries,
            cache=(
                FileCache(
                    settings.cache.directory,
                    cache_ttl or settings.cache.ttl_seconds,
                )
                if settings.cache.enabled
                else None
            ),
            refresh=refresh,
        )

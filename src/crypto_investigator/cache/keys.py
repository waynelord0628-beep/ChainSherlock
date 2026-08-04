from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.models import ProviderCapability

SENSITIVE_KEYS = {
    "apikey",
    "api_key",
    "x-api-key",
    "tron-pro-api-key",
    "authorization",
}


def _safe_parameters(parameters: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in sorted((parameters or {}).items())
        if str(key).casefold() not in SENSITIVE_KEYS
    }


@dataclass(frozen=True, slots=True)
class CacheKey:
    digest: str


def build_cache_key(
    *,
    provider: str,
    chain: Chain,
    capability: ProviderCapability,
    identifier: str,
    parameters: Mapping[str, Any] | None = None,
    page: str | int | None = None,
) -> CacheKey:
    normalized_identifier = (
        identifier.casefold() if chain is Chain.ETHEREUM else identifier
    )
    payload = {
        "provider": provider,
        "chain": chain.value,
        "capability": capability.value,
        "identifier": normalized_identifier,
        "parameters": _safe_parameters(parameters),
        "page": page,
    }
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return CacheKey(hashlib.sha256(serialized).hexdigest())

from collections.abc import Mapping
from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.normalizers.base import Normalizer
from crypto_investigator.normalizers.bitcoin import BitcoinNormalizer
from crypto_investigator.normalizers.ethereum import EthereumNormalizer
from crypto_investigator.normalizers.tron import TronNormalizer
from crypto_investigator.utils.address_validation import detect_address_chain


class NormalizerFactory:
    _normalizers = {
        Chain.ETHEREUM: EthereumNormalizer,
        Chain.TRON: TronNormalizer,
        Chain.BITCOIN: BitcoinNormalizer,
    }

    @classmethod
    def create(cls, chain: Chain | str) -> Normalizer:
        try:
            normalized_chain = chain if isinstance(chain, Chain) else Chain(chain.casefold())
            return cls._normalizers[normalized_chain]()
        except (KeyError, ValueError) as error:
            raise ValueError(f"Unsupported chain: {chain}") from error

    @classmethod
    def chain_for_record(cls, record: Mapping[str, Any]) -> Chain:
        explicit = record.get("chain")
        if explicit is not None and str(explicit).strip():
            try:
                return Chain(str(explicit).strip().casefold())
            except ValueError as error:
                raise ValueError(f"Unsupported chain: {explicit}") from error

        detected = {
            chain
            for field in ("from_address", "to_address")
            if (value := record.get(field))
            if (chain := detect_address_chain(str(value).strip())) is not None
        }
        if len(detected) == 1:
            return detected.pop()
        if len(detected) > 1:
            raise ValueError("Addresses resolve to conflicting chains")
        raise ValueError("Unable to determine chain from record")

from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.normalizers.base import BaseNormalizer


class EthereumNormalizer(BaseNormalizer):
    chain = Chain.ETHEREUM

    def normalize_address(self, value: Any) -> str | None:
        text = self._optional_text(value)
        return text.lower() if text is not None else None

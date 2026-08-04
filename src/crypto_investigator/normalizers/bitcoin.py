from typing import Any

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.normalizers.base import BaseNormalizer


class BitcoinNormalizer(BaseNormalizer):
    chain = Chain.BITCOIN

    def normalize_address(self, value: Any) -> str | None:
        return self._optional_text(value)

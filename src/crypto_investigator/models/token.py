from pydantic import BaseModel

from crypto_investigator.models.transaction import Chain


class Token(BaseModel):
    chain: Chain
    symbol: str
    contract_address: str | None = None
    decimals: int | None = None


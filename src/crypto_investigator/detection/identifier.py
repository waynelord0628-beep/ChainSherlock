import re
from enum import StrEnum

from pydantic import BaseModel

from crypto_investigator.exceptions import InvalidIdentifierError
from crypto_investigator.models.transaction import Chain

ETH_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
ETH_TX = re.compile(r"^0x[a-fA-F0-9]{64}$")
TRON_ADDRESS = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
BTC_ADDRESS = re.compile(r"^(?:bc1[ac-hj-np-z02-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
BTC_TX = re.compile(r"^[a-fA-F0-9]{64}$")


class IdentifierKind(StrEnum):
    ADDRESS = "address"
    TRANSACTION = "transaction"


class Identifier(BaseModel):
    value: str
    chain: Chain
    kind: IdentifierKind


def detect_identifier(value: str) -> Identifier:
    candidate = value.strip()
    if ETH_ADDRESS.fullmatch(candidate):
        return Identifier(value=candidate.lower(), chain=Chain.ETHEREUM, kind=IdentifierKind.ADDRESS)
    if ETH_TX.fullmatch(candidate):
        return Identifier(value=candidate.lower(), chain=Chain.ETHEREUM, kind=IdentifierKind.TRANSACTION)
    if TRON_ADDRESS.fullmatch(candidate):
        return Identifier(value=candidate, chain=Chain.TRON, kind=IdentifierKind.ADDRESS)
    if BTC_ADDRESS.fullmatch(candidate):
        return Identifier(value=candidate.lower() if candidate.startswith("bc1") else candidate, chain=Chain.BITCOIN, kind=IdentifierKind.ADDRESS)
    if BTC_TX.fullmatch(candidate):
        return Identifier(value=candidate.lower(), chain=Chain.BITCOIN, kind=IdentifierKind.TRANSACTION)
    raise InvalidIdentifierError("Unsupported or invalid identifier")


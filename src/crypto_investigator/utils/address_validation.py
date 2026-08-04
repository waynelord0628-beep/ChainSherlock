import re

from crypto_investigator.domain.transaction import Chain

ETHEREUM_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
TRON_ADDRESS = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
BITCOIN_ADDRESS = re.compile(
    r"^(?:(?i:bc1[ac-hj-np-z02-9]{11,87})|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$",
)


def detect_address_chain(value: str) -> Chain | None:
    if ETHEREUM_ADDRESS.fullmatch(value):
        return Chain.ETHEREUM
    if TRON_ADDRESS.fullmatch(value):
        return Chain.TRON
    if BITCOIN_ADDRESS.fullmatch(value):
        return Chain.BITCOIN
    return None


def is_valid_address(value: str) -> bool:
    return detect_address_chain(value) is not None

import pytest

from crypto_investigator.detection.identifier import IdentifierKind, detect_identifier
from crypto_investigator.exceptions import InvalidIdentifierError
from crypto_investigator.models.transaction import Chain


@pytest.mark.parametrize(
    ("value", "chain", "kind"),
    [
        ("0x0000000000000000000000000000000000000000", Chain.ETHEREUM, IdentifierKind.ADDRESS),
        ("0x" + "a" * 64, Chain.ETHEREUM, IdentifierKind.TRANSACTION),
        ("T" + "a" * 33, Chain.TRON, IdentifierKind.ADDRESS),
        ("bc1q" + "a" * 38, Chain.BITCOIN, IdentifierKind.ADDRESS),
        ("a" * 64, Chain.BITCOIN, IdentifierKind.TRANSACTION),
    ],
)
def test_detect_identifier(value, chain, kind):
    identifier = detect_identifier(value)
    assert (identifier.chain, identifier.kind) == (chain, kind)


def test_detect_identifier_rejects_invalid_value():
    with pytest.raises(InvalidIdentifierError):
        detect_identifier("not-an-identifier")


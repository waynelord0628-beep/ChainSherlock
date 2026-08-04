from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from pydantic import BaseModel

from crypto_investigator.domain import Address, Asset, Chain, InvestigationCase, Transaction


def test_domain_entities_do_not_inherit_from_pydantic():
    assert not issubclass(Transaction, BaseModel)
    assert not issubclass(Address, BaseModel)


def test_domain_transaction_is_immutable():
    transaction = Transaction(
        chain=Chain.ETHEREUM,
        tx_hash="0xabc",
        asset_symbol="ETH",
        amount=Decimal("1.25"),
    )
    with pytest.raises(FrozenInstanceError):
        transaction.tx_hash = "0xdef"


def test_case_aggregates_domain_entities():
    address = Address(chain=Chain.BITCOIN, value="bc1example")
    asset = Asset(chain=Chain.BITCOIN, symbol="BTC", decimals=8)
    case = InvestigationCase(case_id="case-1", title="Example", addresses=(address,))
    assert case.addresses == (address,)
    assert asset.symbol == "BTC"

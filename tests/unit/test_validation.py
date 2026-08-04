from crypto_investigator.importers.validator import DataValidator

ETH_FROM = "0x1111111111111111111111111111111111111111"
ETH_TO = "0x2222222222222222222222222222222222222222"


def valid_record(**changes):
    record = {
        "from_address": ETH_FROM,
        "to_address": ETH_TO,
        "amount": "1.5",
        "asset_symbol": "ETH",
        "timestamp": "2026-01-01T00:00:00Z",
        "tx_hash": "0xabc",
    }
    record.update(changes)
    return record


def test_validator_accepts_valid_record():
    result = DataValidator().validate([valid_record()])
    assert result.is_valid
    assert len(result.valid_records) == 1


def test_validator_rejects_empty_required_value():
    result = DataValidator().validate([valid_record(amount="")])
    assert "empty_value" in {issue.code for issue in result.issues}


def test_validator_rejects_invalid_timestamp():
    result = DataValidator().validate([valid_record(timestamp="not-a-time")])
    assert "invalid_timestamp" in {issue.code for issue in result.issues}


def test_validator_rejects_invalid_amount():
    result = DataValidator().validate([valid_record(amount="one coin")])
    assert "invalid_amount" in {issue.code for issue in result.issues}


def test_validator_rejects_invalid_address():
    result = DataValidator().validate([valid_record(from_address="not-an-address")])
    assert "invalid_address" in {issue.code for issue in result.issues}


def test_validator_rejects_forbidden_base58_characters():
    result = DataValidator().validate(
        [valid_record(from_address="1" + "I" * 25, to_address=None)]
    )
    assert "invalid_address" in {issue.code for issue in result.issues}


def test_validator_detects_duplicate_transaction():
    result = DataValidator().validate([valid_record(), valid_record()])
    assert "duplicate_transaction" in {issue.code for issue in result.issues}
    assert len(result.valid_records) == 1


def test_validator_rejects_csv_formula_injection():
    result = DataValidator().validate([valid_record(asset_symbol="=HYPERLINK('x')")])
    assert "formula_injection" in {issue.code for issue in result.issues}


def test_validator_rejects_excel_formula_injection():
    result = DataValidator().validate([valid_record(tx_hash="@SUM(A1:A2)")])
    assert "formula_injection" in {issue.code for issue in result.issues}

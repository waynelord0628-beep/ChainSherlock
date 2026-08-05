from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from crypto_investigator.application.full_asset_benchmark import (
    TRON_USDT_CONTRACT,
    benchmark_reconciliation,
    build_full_asset_benchmark,
)
from crypto_investigator.reports.presentation import _full_asset_benchmark_sections


TARGET = "generic-target-address"


def record(
    *,
    tx: str,
    asset: str,
    amount: str,
    sender: str,
    receiver: str,
    offset: int,
    contract: str | None = None,
    source_type: str = "token_transfer",
    transaction_type: str = "token_transfer",
    contract_type: str | None = None,
):
    return {
        "tx_hash": tx,
        "timestamp": (
            datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=offset)
        ).isoformat(),
        "from_address": sender,
        "to_address": receiver,
        "asset_symbol": asset,
        "asset_contract": contract,
        "amount_raw": amount,
        "decimals": 6,
        "source_type": source_type,
        "transaction_type": transaction_type,
        "metadata": {"contract_type": contract_type} if contract_type else {},
    }


def statuses():
    return [
        {
            "capability": capability,
            "final_completeness": "complete",
            "truncated": False,
            "fetched_records": count,
            "pagination": {
                "pagination_complete": True,
                "accepted_records": count,
                "rejected_records": 0,
                "deduplicated_records": 0,
            },
        }
        for capability, count in (
            ("address_transactions", 201),
            ("token_transfers", 401),
        )
    ]


def fixture_records():
    return [
        record(
            tx="u1",
            asset="USDT",
            amount="10000000",
            sender="source-a",
            receiver=TARGET,
            offset=0,
            contract=TRON_USDT_CONTRACT,
        ),
        record(
            tx="u2",
            asset="USDT",
            amount="5000000",
            sender="source-b",
            receiver=TARGET,
            offset=1,
            contract=TRON_USDT_CONTRACT,
        ),
        record(
            tx="u3",
            asset="USDT",
            amount="12000000",
            sender=TARGET,
            receiver="destination-a",
            offset=2,
            contract=TRON_USDT_CONTRACT,
        ),
        record(
            tx="u0",
            asset="USDT",
            amount="0",
            sender=TARGET,
            receiver=TRON_USDT_CONTRACT,
            offset=3,
            contract=TRON_USDT_CONTRACT,
        ),
        record(
            tx="trx",
            asset="TRX",
            amount="4028000000",
            sender="okx-candidate",
            receiver=TARGET,
            offset=4,
            source_type="normal_transaction",
            transaction_type="native_transfer",
            contract_type="TransferContract",
        ),
        record(
            tx="trc10",
            asset="1005002",
            amount="8888880000",
            sender="spam-candidate",
            receiver=TARGET,
            offset=5,
            source_type="normal_transaction",
            transaction_type="token_transfer",
            contract_type="TransferAssetContract",
        ),
    ]


def benchmark():
    return build_full_asset_benchmark(
        fixture_records(), statuses(), target_address=TARGET
    )


def test_full_history_requires_both_capabilities_complete():
    assert benchmark()["full_history_complete"] is True


def test_usdt_is_separated_from_trx_and_trc10():
    result = benchmark()
    assert result["usdt"]["transaction_count"] == 4
    assert result["trx"]["transaction_count"] == 1
    assert result["other_asset_record_count"] == 1


def test_zero_value_tether_event_is_not_outgoing_value():
    result = benchmark()["usdt"]
    assert result["zero_value_count"] == 1
    assert result["outgoing_count"] == 1
    assert Decimal(result["outgoing_total"]) == Decimal("12")


def test_net_flow_and_bidirectional_volume_are_exact():
    result = benchmark()["usdt"]
    assert Decimal(result["incoming_total"]) == Decimal("15")
    assert Decimal(result["bidirectional_volume"]) == Decimal("27")
    assert Decimal(result["net_flow"]) == Decimal("3")


def test_source_and_destination_concentration():
    result = benchmark()["usdt"]
    assert Decimal(
        result["source_concentration"]["top_1_share"]
    ) == Decimal("10") / Decimal("15")
    assert result["destination_concentration"]["top_1_share"] == "1"


def test_asset_priority_places_usdt_before_operational_trx():
    roles = benchmark()["asset_priority"]
    assert roles[0]["asset"] == "USDT"
    assert roles[0]["role"] == "principal_value_asset"
    assert roles[1]["role"] == "operational_asset"


def test_first_hop_candidates_only_use_usdt_destinations():
    candidates = benchmark()["first_hop_candidates"]
    assert [item["destination_address"] for item in candidates] == [
        "destination-a"
    ]
    assert "principal_value_asset" in candidates[0]["priority_reasons"]


def test_first_hop_addresses_use_one_consistent_two_line_reference():
    value = benchmark()
    address = value["first_hop_candidates"][0]["destination_address"]
    document = SimpleNamespace(metadata=SimpleNamespace(benchmark=value))
    section = next(
        item
        for item in _full_asset_benchmark_sections(
            document,
            {address: "地址-003"},
        )
        if item.section_id == "first_hop_candidates"
    )
    address_column = section.tables[0].columns.index("完整地址（地址編號）")
    references = tuple(row[address_column] for row in section.tables[0].rows)
    assert references == ("destina\ntion-a（地址-003）",)
    assert all(reference.count("\n") == 1 for reference in references)


def test_unverified_labels_are_not_upgraded_to_confirmed():
    result = benchmark()
    assert result["labels"]["status"] == "unverified"
    assert result["first_hop_candidates"][0]["label_status"] == "unverified"


def test_adjacent_events_do_not_claim_transaction_path():
    limitation = benchmark()["usdt"]["timing"]["limitation"]
    assert "不代表同一筆資金" in limitation


def test_request_pages_are_recorded_without_test_limits():
    usage = benchmark()["provider_usage"]
    assert usage["request_count"] == 5
    assert usage["rate_limit_responses"] == 0


def test_reconciliation_does_not_treat_reference_as_ground_truth():
    value = benchmark_reconciliation(benchmark())
    assert value["reference_supplied"] is False
    assert value["comparisons"] == []

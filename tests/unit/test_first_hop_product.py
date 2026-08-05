from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path

from crypto_investigator.application.first_hop_product import (
    FirstHopGoal,
    build_first_hop_product,
    write_first_hop_product,
)
from crypto_investigator.investigation.investigation_result import LabelRecord
from crypto_investigator.labels.registry import LabelRegistry
from crypto_investigator.planner.goals import GoalType, InvestigationGoal


TARGET = "target-address"


def tx(
    tx_hash,
    asset,
    amount,
    sender,
    receiver,
    *,
    day=1,
    source_type="token_transfer",
    transaction_type="token_transfer",
    contract="token-contract",
):
    return {
        "tx_hash": tx_hash,
        "asset_symbol": asset,
        "asset_contract": contract,
        "amount_raw": str(amount),
        "decimals": 0,
        "from_address": sender,
        "to_address": receiver,
        "timestamp": datetime(2026, 1, day, tzinfo=UTC).isoformat(),
        "source_type": source_type,
        "transaction_type": transaction_type,
    }


def complete_status():
    return (
        {
            "capability": "transactions",
            "final_completeness": "complete",
            "truncated": False,
        },
    )


def product(records, **kwargs):
    return build_first_hop_product(
        records,
        complete_status(),
        target_address=TARGET,
        chain="testchain",
        goal=kwargs.pop(
            "goal",
            FirstHopGoal(required_capabilities=("transactions",)),
        ),
        **kwargs,
    )


def test_token_value_asset_precedes_native_operational_asset():
    records = [
        tx("t1", "USD-X", 1000, "source", TARGET),
        tx("t2", "USD-X", 900, TARGET, "destination"),
        tx(
            "n1",
            "NATIVE",
            20,
            "fee-source",
            TARGET,
            source_type="native",
            transaction_type="native_transfer",
            contract=None,
        ),
    ]
    result = product(records)
    assert result["asset_roles"][0]["asset"] == "USD-X"
    assert result["asset_roles"][0]["role"] == "principal_value_asset"
    assert result["asset_roles"][1]["role"] == "operational_asset"


def test_native_only_case_has_principal_asset():
    result = product(
        [
            tx(
                "n1",
                "COIN",
                12,
                "source",
                TARGET,
                source_type="native",
                transaction_type="native_transfer",
                contract=None,
            )
        ]
    )
    assert result["principal_asset"]["asset"] == "COIN"


def test_required_asset_goal_drives_principal_selection():
    result = product(
        [
            tx("a1", "TOKEN-A", 100, "source-a", TARGET),
            tx("b1", "TOKEN-B", 50, "source-b", TARGET),
        ],
        goal=FirstHopGoal(
            required_assets=("TOKEN-B",),
            required_capabilities=("transactions",),
        ),
    )
    assert result["principal_asset"]["asset"] == "TOKEN-B"


def test_principal_summary_and_concentration_are_exact():
    result = product(
        [
            tx("a1", "VALUE", 75, "source-a", TARGET),
            tx("a2", "VALUE", 25, "source-b", TARGET),
            tx("a3", "VALUE", 80, TARGET, "destination-a"),
        ]
    )["principal_asset"]
    assert result["incoming_total"] == Decimal("100")
    assert result["outgoing_total"] == Decimal("80")
    assert result["net_flow"] == Decimal("20")
    assert result["source_concentration"]["top_1_share"] == "0.75"
    assert result["destination_concentration"]["top_1_share"] == "1"


def test_zero_value_does_not_change_amounts():
    result = product(
        [
            tx("a1", "VALUE", 10, "source", TARGET),
            tx("z1", "VALUE", 0, TARGET, "contract"),
        ]
    )["principal_asset"]
    assert result["zero_value_count"] == 1
    assert result["bidirectional_volume"] == Decimal("10")


def test_first_hop_priority_is_principal_destination_order():
    result = product(
        [
            tx("i1", "VALUE", 100, "source", TARGET),
            tx("o1", "VALUE", 70, TARGET, "destination-a"),
            tx("o2", "VALUE", 20, TARGET, "destination-b"),
        ]
    )
    assert [item["address"] for item in result["first_hop_candidates"]] == [
        "destination-a",
        "destination-b",
    ]
    assert result["first_hop_candidates"][0]["candidate_id"] == "FH-001"
    assert "下車點" not in result["first_hop_candidates"][0]["priority_reasons"]


def test_local_label_keeps_source_and_verification_boundary():
    label = LabelRecord(
        address="destination-a",
        label="Known service",
        category="service",
        source="local-labels.csv",
        chain="testchain",
        confidence="verified",
    )
    result = product(
        [
            tx("i1", "VALUE", 100, "source", TARGET),
            tx("o1", "VALUE", 80, TARGET, "destination-a"),
        ],
        labels=(label,),
    )
    candidate = result["first_hop_candidates"][0]
    assert candidate["label"] == "Known service"
    assert candidate["label_source"] == "local-labels.csv"
    assert candidate["verification_status"] == "verified"


def test_dust_threshold_excludes_from_material_analysis_but_not_record_count():
    result = product(
        [
            tx("i1", "VALUE", "0.001", "dust", TARGET),
            tx("i2", "VALUE", 10, "source", TARGET),
        ],
        goal=FirstHopGoal(
            required_capabilities=("transactions",),
            materiality_thresholds={"VALUE": Decimal("0.01")},
        ),
    )["principal_asset"]
    assert result["transaction_count"] == 2
    assert result["material_transaction_count"] == 1
    assert result["excluded_count"] == 1


def test_partial_provider_is_not_upgraded_to_complete():
    status = (
        {
            "capability": "transactions",
            "final_completeness": "partial",
            "truncated": True,
        },
    )
    result = build_first_hop_product(
        [tx("i1", "VALUE", 10, "source", TARGET)],
        status,
        target_address=TARGET,
        chain="testchain",
        goal=FirstHopGoal(required_capabilities=("transactions",)),
    )
    assert result["retrieval_complete"] is False


def test_small_dataset_does_not_invent_stages():
    result = product([tx("i1", "VALUE", 10, "source", TARGET)])
    assert result["stages"] == []


def test_product_has_no_reference_report_dependency_or_case_address_constant():
    import inspect
    from crypto_investigator.application import first_hop_product

    source = inspect.getsource(first_hop_product)
    assert "reference report" not in source.casefold()
    assert "TUxHyMSw" not in source


def test_deterministic_summary_answers_scope_and_evidence_boundary():
    result = product(
        [
            tx("i1", "VALUE", 100, "source", TARGET),
            tx("o1", "VALUE", 90, TARGET, "destination"),
        ]
    )
    summary = " ".join(result["executive_summary"])
    assert "主要價值資產為 VALUE" in summary
    assert "淨流量 10" in summary
    assert "不能據此確認最終受益人" in summary


def test_follow_up_tasks_are_case_specific():
    result = product(
        [
            tx("i1", "VALUE", 100, "source", TARGET),
            tx("o1", "VALUE", 90, TARGET, "destination"),
        ]
    )
    task = result["follow_up_tasks"][0]
    assert task["address"] == "destination"
    assert task["received_amount"] == "90"
    assert task["expected_question_answered"] == "該第一層去向後續流向何處"


def test_deterministic_chart_artifacts_share_product_source_and_have_hashes(tmp_path):
    result = product(
        [
            tx("i1", "VALUE", 100, "source", TARGET),
            tx("o1", "VALUE", 90, TARGET, "destination"),
        ]
    )
    written = write_first_hop_product(result, tmp_path)
    assert written["charts"]
    for artifact in written["charts"].values():
        assert (tmp_path / artifact["path"]).exists()
        assert len(artifact["sha256"]) == 64


def test_custom_date_range_goal_is_preserved():
    result = product(
        [tx("i1", "VALUE", 100, "source", TARGET)],
        goal=FirstHopGoal(
            scope_type="custom_date_range",
            required_capabilities=("transactions",),
        ),
    )
    assert result["goal"]["scope_type"] == "custom_date_range"


def test_planner_first_hop_goal_serializes_explicit_requirements():
    goal = InvestigationGoal(
        goal_type=GoalType.FIRST_HOP_FUND_FLOW,
        title="第一層資金來源與去向分析",
        target_assets=["VALUE"],
        required_capabilities=["address_transactions", "token_transfers"],
        scope_type="full_history",
        materiality_thresholds={"VALUE": Decimal("1")},
        output_type="first_hop_investigation_report",
        completeness_requirement="complete",
    )
    restored = InvestigationGoal.model_validate_json(goal.model_dump_json())
    assert restored.required_capabilities == [
        "address_transactions",
        "token_transfers",
    ]
    assert restored.materiality_thresholds["VALUE"] == Decimal("1")


def test_label_conflict_prefers_verified_local_record(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(
        """
        [
          {"chain":"testchain","address":"destination","label":"候選",
           "category":"service","verification_status":"unverified_candidate"},
          {"chain":"testchain","address":"destination","label":"人工確認",
           "category":"service","verification_status":"manual_confirmed",
           "source":"case-note","reference":"EV-001"}
        ]
        """,
        encoding="utf-8",
    )
    registry = LabelRegistry.import_file(path)
    assert len(registry.records) == 1
    assert registry.records[0].label == "人工確認"
    assert registry.records[0].verification_status == "manual_confirmed"
    assert registry.records[0].reference == "EV-001"


def test_ten_generic_recorded_product_cases():
    cases = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures"
            / "first_hop"
            / "product_cases.json"
        ).read_text(encoding="utf-8")
    )
    assert len(cases) == 10
    for case in cases:
        status = (
            {
                "capability": "transactions",
                "final_completeness": (
                    "partial" if case.get("partial") else "complete"
                ),
                "truncated": bool(case.get("partial")),
            },
        )
        threshold = case.get("threshold")
        result = build_first_hop_product(
            case["records"],
            status,
            target_address=TARGET,
            chain="testchain",
            goal=FirstHopGoal(
                required_capabilities=("transactions",),
                scope_type=case.get("scope_type", "full_history"),
                materiality_thresholds=(
                    {"VALUE": Decimal(threshold)} if threshold else None
                ),
            ),
        )
        principal = result["principal_asset"]
        assert (principal["asset"] if principal else None) == case["expected_principal"]
        if case.get("expect_stages") is False:
            assert result["stages"] == []

from dataclasses import replace
import json

import pytest

from crypto_investigator.ai.budget import (
    DEFAULT_COMPLETION_TOKENS,
    HARD_MAX_COMPLETION_TOKENS,
    MIN_COMPLETION_TOKENS,
    completion_budget,
)
from crypto_investigator.ai.input_compactor import InputCompactor
from crypto_investigator.ai.prompt_builder import PromptBuilder
from crypto_investigator.ai.schema import narrative_response_schema
from crypto_investigator.ai.fallback import DeterministicFallbackProvider
from crypto_investigator.narratives.export import decode_public_result, encode
from crypto_investigator.narratives.models import NarrativeInput


def source(**changes):
    value = NarrativeInput(
        report_metadata={"transaction_count": 99},
        target_address="TTarget",
        chain="tron",
        analysis_period={"from": "2025-01-01", "to": "2025-12-31"},
        completeness="partial",
        provider_limits=("rate limited",),
        asset_summaries=({"asset": "USDT", "received": "10"},),
        direction_reconciliation={"transaction_count": 99},
        funding_sources=(),
        outgoing_destinations=(),
        funding_transitions=(),
        operation_stages=(),
        dormancy=(),
        holding_time=(),
        transfer_patterns=(),
        concentration_metrics={"hhi": "0.5"},
        counterparty_roles=(),
        label_matches=(),
        observations=(),
        conclusion_facts=(),
        limitations=(),
        evidence_index=(),
        requested_sections=(
            "executive_summary", "funding_narrative", "outgoing_narrative",
            "stage_narrative", "dormancy_narrative", "holding_time_narrative",
            "pattern_narrative", "counterparty_narrative",
            "alternative_explanations", "investigative_leads",
            "limitations", "conclusion",
        ),
    )
    return replace(value, **changes)


@pytest.mark.parametrize(
    "field,limit",
    (
        ("funding_sources", 5),
        ("outgoing_destinations", 5),
        ("funding_transitions", 10),
        ("operation_stages", 10),
        ("observations", 20),
        ("conclusion_facts", 30),
        ("limitations", 15),
        ("evidence_index", 50),
    ),
)
def test_compact_collections_have_deterministic_limits(field, limit):
    rows = tuple(
        (
            f"limitation-{index}"
            if field == "limitations"
            else {
                "address": f"T{index:034}",
                "rank": index,
                "occurred_at": f"2025-01-{(index % 28) + 1:02}",
                "code": f"O{index:03}",
                "fact_code": f"F{index:03}",
                "evidence_id": f"E{index:03}",
            }
        )
        for index in range(limit + 7)
    )
    compact = InputCompactor().compact(source(**{field: rows}), mode="compact")
    assert len(getattr(compact, field)) <= limit
    assert compact.omitted_counts[field] == 7


def test_compact_prompt_excludes_raw_transaction_payloads():
    prompt = PromptBuilder().build(InputCompactor().compact(source(), mode="compact"))
    assert "raw_transactions" not in prompt
    assert "authorization" not in prompt.casefold()


def test_compact_ordering_is_stable():
    rows = tuple({"rank": rank, "address": f"T{rank:034}"} for rank in (3, 1, 2))
    first = InputCompactor().compact(source(funding_sources=rows), mode="compact")
    second = InputCompactor().compact(source(funding_sources=tuple(reversed(rows))), mode="compact")
    assert first.funding_sources == second.funding_sources


@pytest.mark.parametrize("configured", (4000, 5000, 6000, 8000, 9000))
def test_completion_budget_is_bounded(configured):
    budget = completion_budget(source(), configured_tokens=configured)
    assert MIN_COMPLETION_TOKENS <= budget.requested_tokens <= HARD_MAX_COMPLETION_TOKENS


def test_completion_budget_default_is_not_legacy_1800():
    assert completion_budget(source()).requested_tokens >= DEFAULT_COMPLETION_TOKENS


def test_completion_budget_grows_with_grounding_content():
    small = completion_budget(source()).estimated_minimum_tokens
    large = completion_budget(
        source(
            observations=tuple({"code": f"O{i}"} for i in range(20)),
            conclusion_facts=tuple({"fact_code": f"F{i}", "value": i} for i in range(30)),
            evidence_index=tuple({"evidence_id": f"E{i}"} for i in range(50)),
        )
    ).estimated_minimum_tokens
    assert large > small


@pytest.mark.parametrize(
    "path,expected",
    (
        (("properties", "executive_summary", "anyOf", 0, "properties", "paragraphs", "maxItems"), 2),
        (("properties", "claims", "maxItems"), 60),
        (("properties", "claims", "items", "properties", "fact_codes", "maxItems"), 5),
        (("properties", "claims", "items", "properties", "evidence_ids", "maxItems"), 5),
        (("properties", "claims", "items", "properties", "statement", "maxLength"), 280),
        (("properties", "executive_summary", "anyOf", 0, "properties", "paragraphs", "items", "properties", "citation_ids", "minItems"), 1),
        (("properties", "review_status", "enum"), ["not_reviewed", "reviewed", "accepted", "edited", "rejected"]),
    ),
)
def test_schema_contains_bounded_output_contract(path, expected):
    value = narrative_response_schema()
    for part in path:
        value = value[part]
    assert value == expected


def test_schema_does_not_duplicate_section_level_grounding_arrays():
    section = narrative_response_schema()["properties"]["executive_summary"]["anyOf"][0]
    assert not {"fact_refs", "observation_refs", "evidence_refs"} & set(section["properties"])


def test_dynamic_schema_enumerates_only_available_grounding_ids():
    value = source(
        evidence_index=({"evidence_id": "E1"},),
        observations=({"code": "O1"},),
        conclusion_facts=({"fact_code": "F1", "value": 1},),
    )
    schema = narrative_response_schema(value)
    claim = schema["properties"]["claims"]["items"]["properties"]
    paragraph = schema["properties"]["executive_summary"]["anyOf"][0][
        "properties"
    ]["paragraphs"]["items"]["properties"]
    assert paragraph["citation_ids"]["items"]["enum"] == ["E1"]
    assert claim["evidence_ids"]["items"]["enum"] == ["E1"]
    assert claim["observation_ids"]["items"]["enum"] == ["O1"]
    assert claim["fact_codes"]["items"]["enum"] == ["F1"]


def test_prompt_declares_no_table_duplication_and_section_budget():
    prompt = PromptBuilder().build(source())
    assert "Do not reproduce tables" in prompt
    assert "at most 350 Chinese characters" in prompt
    assert "copied exactly from STRUCTURED_FACTS" in prompt


def test_prompt_requires_formal_human_readable_report_language():
    prompt = PromptBuilder().build(source())
    assert "formal forensic case report" in prompt
    assert "Do not expose internal field names" in prompt
    assert "incoming_count becomes 流入交易筆數" in prompt
    assert "median_holding_seconds becomes 中位停留時間" in prompt


def test_prompt_requires_case_timezone_and_no_naive_timezone_assumption():
    prompt = PromptBuilder().build(source())
    assert "YYYY-MM-DD HH:mm:ss（UTC+8）" in prompt
    assert "Never silently assign a timezone to a naive timestamp" in prompt


def test_prompt_requires_final_style_self_check():
    prompt = PromptBuilder().build(source())
    assert "FINAL_STYLE_CHECK" in prompt
    assert "must not contain these tokens" in prompt
    assert "funding_transition_count" in prompt
    assert "Percentages in prose must use a percent sign" in prompt


def test_prompt_keeps_display_hints_out_of_exact_numeric_values():
    prompt = PromptBuilder().build(source())
    assert "DETERMINISTIC_DISPLAY_HINTS are prose-only renderings" in prompt
    assert "Never copy a formatted hint" in prompt
    assert "numeric_values empty" in prompt


def test_compact_snapshot_has_no_secret_or_local_path_fields():
    payload = json.dumps(
        InputCompactor().compact(source(), mode="compact").report_metadata,
        sort_keys=True,
    ).casefold()
    assert "api_key" not in payload
    assert "authorization" not in payload
    assert "c:\\\\" not in payload


def test_compact_evidence_keeps_ids_without_address_collections():
    compact = InputCompactor().compact(
        source(
            evidence_index=(
                {
                    "evidence_id": "E1",
                    "feature": "funding",
                    "source_type": "transaction",
                    "addresses": tuple(f"T{index:034}" for index in range(100)),
                },
            )
        ),
        mode="compact",
    )
    assert compact.evidence_index == (
        {
            "evidence_id": "E1",
            "feature": "funding",
            "source_type": "transaction",
        },
    )


def test_untagged_strict_schema_result_decodes_to_domain_model():
    def untag(value):
        if isinstance(value, dict):
            if "__datetime__" in value:
                return value["__datetime__"]
            if "__enum__" in value:
                return value["__enum__"].split(":", 1)[1]
            if "__tuple__" in value:
                return [untag(item) for item in value["__tuple__"]]
            return {
                key: untag(item)
                for key, item in value.items()
                if key != "__type__"
            }
        if isinstance(value, list):
            return [untag(item) for item in value]
        return value

    expected = DeterministicFallbackProvider().generate(source())
    decoded = decode_public_result(untag(encode(expected)))
    assert decoded.executive_summary.section_id == "executive_summary"
    assert decoded.metadata.provider == "deterministic-fallback"

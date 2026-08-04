from dataclasses import dataclass

from crypto_investigator.narratives.models import NarrativeInput


MIN_COMPLETION_TOKENS = 4_000
DEFAULT_COMPLETION_TOKENS = 5_000
HARD_MAX_COMPLETION_TOKENS = 8_000


@dataclass(frozen=True, slots=True)
class CompletionBudget:
    requested_tokens: int
    estimated_minimum_tokens: int
    hard_cap_tokens: int = HARD_MAX_COMPLETION_TOKENS


def completion_budget(
    source: NarrativeInput,
    *,
    configured_tokens: int = DEFAULT_COMPLETION_TOKENS,
) -> CompletionBudget:
    """Estimate one bounded structured completion without inspecting raw records."""
    sections = len(source.requested_sections) or 12
    facts = len(source.conclusion_facts)
    observations = len(source.observations)
    evidence = len(source.evidence_index)
    language_allowance = 350 if source.language.casefold().startswith("zh") else 0
    estimated = (
        2_800
        + sections * 125
        + facts * 12
        + observations * 10
        + min(evidence, 50) * 4
        + language_allowance
    )
    estimated = max(MIN_COMPLETION_TOKENS, estimated)
    safe_setting = min(max(configured_tokens, MIN_COMPLETION_TOKENS), HARD_MAX_COMPLETION_TOKENS)
    requested = min(max(estimated, DEFAULT_COMPLETION_TOKENS), safe_setting)
    return CompletionBudget(requested, estimated)

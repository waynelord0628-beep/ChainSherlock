import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

from crypto_investigator.narratives.models import (
    NarrativeClaim,
    NarrativeInput,
    NarrativeResult,
    NarrativeValidationResult,
)

BANNED_WORDING = (
    "確定為詐騙",
    "確定是詐騙",
    "洗錢故意",
    "犯罪所得",
    "高風險地址",
    "非法地址",
    "money laundering",
    "criminal proceeds",
)
FIFO_OVERCLAIMS = ("證明收到後立即轉出同一筆資金", "same exact funds")
CONFIRMED_WORDING = ("確認為交易所", "確定是交易所", "confirmed exchange")


def _all_text(result: NarrativeResult) -> str:
    parts = [claim.statement for claim in result.claims]
    for name in result.__dataclass_fields__:
        section = getattr(result, name)
        if hasattr(section, "paragraphs"):
            parts.extend(paragraph.text for paragraph in section.paragraphs)
    return "\n".join(parts)


def _strings(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _strings(item)
    elif value is not None:
        yield str(value)


class NarrativeValidator:
    def validate(self, result: NarrativeResult, source: NarrativeInput) -> NarrativeValidationResult:
        errors: list[str] = []
        text = _all_text(result)
        lowered = text.lower()
        if any(term.lower() in lowered for term in BANNED_WORDING):
            errors.append("banned_wording")
        if any(term.lower() in lowered for term in FIFO_OVERCLAIMS):
            errors.append("fifo_overclaim")
        if any(term.lower() in lowered for term in CONFIRMED_WORDING) and source.counterparty_roles:
            errors.append("candidate_promoted")
        evidence = {str(item.get("evidence_id")) for item in source.evidence_index}
        known_numbers = self._numeric_values(source)
        for claim in result.claims:
            self._validate_claim(claim, evidence, known_numbers, errors)
        citation_ids = {item.citation_id for item in result.citations}
        for section_name in source.requested_sections:
            section = getattr(result, section_name, None)
            if section is None:
                errors.append(f"required_section_missing:{section_name}")
                continue
            if section and section_name != "limitations":
                cited = {cid for para in section.paragraphs for cid in para.citation_ids}
                grounded_claim = any(
                    claim.section in {section_name, section.section_id}
                    and (
                        claim.fact_codes
                        or claim.observation_ids
                        or claim.evidence_ids
                    )
                    for claim in result.claims
                )
                if (
                    (not cited or not cited.issubset(citation_ids))
                    and not grounded_claim
                ):
                    errors.append(f"section_citation:{section_name}")
        if source.completeness.lower() != "complete" and re.search(r"\bcomplete data\b|完整資料", text, re.I):
            errors.append("partial_promoted")
        self._validate_output_budget(result, errors)
        return NarrativeValidationResult(
            valid=not errors,
            errors=tuple(dict.fromkeys(errors)),
            checked_claims=len(result.claims),
        )

    @staticmethod
    def _validate_output_budget(result, errors):
        if len(result.claims) > 60:
            errors.append("output_claim_limit")
        for name in result.__dataclass_fields__:
            section = getattr(result, name)
            if not hasattr(section, "paragraphs"):
                continue
            if len(section.paragraphs) > 2:
                errors.append(f"section_paragraph_limit:{name}")
            claims = [item for item in result.claims if item.section in {name, section.section_id}]
            if len(claims) > 5:
                errors.append(f"section_claim_limit:{name}")
            max_chars = 350 if name == "executive_summary" else 280
            if any(len(item.text) > max_chars for item in section.paragraphs):
                errors.append(f"section_length_limit:{name}")
            for claim in claims:
                if max(
                    len(claim.fact_codes),
                    len(claim.observation_ids),
                    len(claim.evidence_ids),
                ) > 5:
                    errors.append(f"claim_ref_limit:{claim.claim_id}")

    def _validate_claim(self, claim: NarrativeClaim, evidence: set[str], numbers: set[Decimal], errors: list[str]):
        if claim.claim_type == "factual" and not claim.evidence_ids:
            errors.append(f"missing_evidence:{claim.claim_id}")
        if not set(claim.evidence_ids).issubset(evidence):
            errors.append(f"unknown_evidence:{claim.claim_id}")
        for raw in claim.numeric_values:
            try:
                value = Decimal(raw.replace(",", "").replace("%", ""))
            except InvalidOperation:
                errors.append(f"invalid_numeric:{claim.claim_id}")
                continue
            if value not in numbers:
                errors.append(f"numeric_mismatch:{claim.claim_id}:{raw}")

    @staticmethod
    def _numbers(text: str) -> set[Decimal]:
        result = set()
        for raw in re.findall(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?", text):
            try:
                result.add(Decimal(raw.replace(",", "")))
            except InvalidOperation:
                pass
        return result

    @classmethod
    def _numeric_values(cls, value) -> set[Decimal]:
        result: set[Decimal] = set()
        if isinstance(value, bool) or value is None:
            return result
        if isinstance(value, (int, float, Decimal)):
            result.add(Decimal(str(value)))
        elif isinstance(value, str) and re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?%?", value):
            result.add(Decimal(value.replace(",", "").replace("%", "")))
        elif isinstance(value, str):
            result.update(cls._numbers(value))
        elif isinstance(value, dict):
            for item in value.values():
                result.update(cls._numeric_values(item))
        elif isinstance(value, (tuple, list)):
            for item in value:
                result.update(cls._numeric_values(item))
        elif hasattr(value, "__dataclass_fields__"):
            for name in value.__dataclass_fields__:
                if name in {"schema_version"}:
                    continue
                result.update(cls._numeric_values(getattr(value, name)))
        return result

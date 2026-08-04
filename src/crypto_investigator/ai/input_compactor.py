from dataclasses import replace
from typing import Any

from crypto_investigator.ai.errors import AIInputLimitError
from crypto_investigator.ai.redaction import private_identifier, redact_text
from crypto_investigator.narratives.models import NarrativeInput


class InputCompactor:
    def __init__(
        self,
        *,
        top_funding_sources: int = 10,
        top_outgoing_destinations: int = 10,
        top_patterns: int = 20,
        top_observations: int = 30,
        top_roles: int = 20,
        max_evidence_refs: int = 100,
        max_tx_hashes_per_item: int = 5,
        max_input_characters: int = 100_000,
    ):
        limits = locals()
        if any(value < 0 for key, value in limits.items() if key.startswith(("top_", "max_"))):
            raise AIInputLimitError("Compaction limits must be non-negative")
        self.limits = limits

    def compact(self, value: NarrativeInput, privacy_mode: str = "standard") -> NarrativeInput:
        omitted: dict[str, int] = {}

        def bounded(name: str, items: tuple[Any, ...], limit: int, sort_key):
            ordered = tuple(sorted(items, key=sort_key))
            omitted[name] = max(0, len(ordered) - limit)
            return ordered[:limit]

        result = replace(
            value,
            funding_sources=bounded("funding_sources", value.funding_sources, self.limits["top_funding_sources"], lambda x: (x.get("rank", 10**9), x.get("address", ""))),
            outgoing_destinations=bounded("outgoing_destinations", value.outgoing_destinations, self.limits["top_outgoing_destinations"], lambda x: (-float(x.get("amount", x.get("transaction_count", 0))), str(x.get("address", "")))),
            transfer_patterns=bounded("transfer_patterns", value.transfer_patterns, self.limits["top_patterns"], lambda x: (str(x.get("pattern_type", "")), str(x))),
            observations=bounded("observations", value.observations, self.limits["top_observations"], lambda x: (str(x.get("occurred_at", "")), str(x.get("code", "")))),
            counterparty_roles=bounded("counterparty_roles", value.counterparty_roles, self.limits["top_roles"], lambda x: (str(x.get("role", "")), str(x.get("address", "")))),
            evidence_index=bounded("evidence_index", value.evidence_index, self.limits["max_evidence_refs"], lambda x: str(x.get("evidence_id", ""))),
            omitted_counts=omitted,
        )
        result = replace(result, evidence_index=tuple(self._bound_hashes(item) for item in result.evidence_index))
        if privacy_mode == "strict":
            result = self._strict(result)
        if privacy_mode not in {"strict", "standard", "off"}:
            raise AIInputLimitError("Unsupported privacy mode")
        return result

    def _bound_hashes(self, item: dict[str, Any]) -> dict[str, Any]:
        copy = dict(item)
        hashes = tuple(copy.get("tx_hashes", ()))
        copy["tx_hashes"] = hashes[: self.limits["max_tx_hashes_per_item"]]
        copy["tx_hashes_omitted_count"] = max(0, len(hashes) - len(copy["tx_hashes"]))
        return copy

    def _strict(self, value: NarrativeInput) -> NarrativeInput:
        address = private_identifier(value.target_address)

        def scrub(item):
            if isinstance(item, dict):
                return {
                    key: (() if key == "tx_hashes" else private_identifier(str(val)) if key == "address" else scrub(val))
                    for key, val in item.items()
                    if key not in {"notes", "source_reference", "reference"}
                }
            if isinstance(item, tuple):
                return tuple(scrub(part) for part in item)
            if isinstance(item, str):
                return redact_text(item)
            return item

        return replace(
            value,
            target_address=address,
            funding_sources=scrub(value.funding_sources),
            outgoing_destinations=scrub(value.outgoing_destinations),
            evidence_index=scrub(value.evidence_index),
            label_matches=scrub(value.label_matches),
        )

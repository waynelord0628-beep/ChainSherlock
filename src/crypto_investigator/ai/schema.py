from __future__ import annotations


def _nullable(value):
    return {"anyOf": [value, {"type": "null"}]}


def _object(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _reference_item(values):
    result = {"type": "string"}
    if values:
        result["enum"] = sorted(set(values))
    return result


def narrative_response_schema(source=None):
    evidence_ids = tuple(
        str(item.get("evidence_id"))
        for item in getattr(source, "evidence_index", ())
        if item.get("evidence_id")
    )
    fact_codes = tuple(
        str(item.get("fact_code"))
        for item in getattr(source, "conclusion_facts", ())
        if item.get("fact_code")
    )
    observation_ids = tuple(
        str(item.get("code"))
        for item in getattr(source, "observations", ())
        if item.get("code")
    )
    section_ids = tuple(getattr(source, "requested_sections", ()))
    paragraph = _object({
        "text": {"type": "string", "maxLength": 350},
        "citation_ids": {
            "type": "array",
            "items": _reference_item(evidence_ids),
            "minItems": 1,
            "maxItems": 5,
        },
    })
    section = _object({
        "section_id": {"type": "string"},
        "title": {"type": "string"},
        "paragraphs": {"type": "array", "items": paragraph, "maxItems": 2},
    })
    metadata = _object({
        "provider": {"type": "string"},
        "model": {"type": "string"},
        "prompt_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "status": {"type": "string"},
        "fallback_used": {"type": "boolean"},
        "input_sha256": {"type": "string"},
        "schema_version": {"type": "string"},
    })
    claim = _object({
        "claim_id": {"type": "string"},
        "section": _reference_item(section_ids),
        "statement": {"type": "string", "maxLength": 280},
        "claim_type": {"type": "string"},
        "fact_codes": {"type": "array", "items": _reference_item(fact_codes), "maxItems": 5},
        "observation_ids": {"type": "array", "items": _reference_item(observation_ids), "maxItems": 5},
        "evidence_ids": {"type": "array", "items": _reference_item(evidence_ids), "maxItems": 5},
        "numeric_values": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "confidence": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    })
    citation = _object({
        "citation_id": _reference_item(evidence_ids),
        "evidence_id": _reference_item(evidence_ids),
        "section": _reference_item(section_ids),
    })
    warning = _object({"code": {"type": "string"}, "message": {"type": "string"}})
    validation = _object({
        "valid": {"type": "boolean"},
        "errors": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "checked_claims": {"type": "integer"},
    })
    properties = {"metadata": metadata}
    for name in (
        "executive_summary", "target_profile", "funding_narrative",
        "outgoing_narrative", "stage_narrative", "dormancy_narrative",
        "holding_time_narrative", "pattern_narrative",
        "counterparty_narrative", "alternative_explanations",
        "investigative_leads", "limitations", "conclusion",
    ):
        properties[name] = _nullable(section)
    properties.update({
        "claims": {"type": "array", "items": claim, "maxItems": 60},
        "citations": {"type": "array", "items": citation},
        "warnings": {"type": "array", "items": warning},
        "validation": validation,
        "review_status": {
            "type": "string",
            "enum": [
                "not_reviewed", "reviewed", "accepted", "edited", "rejected"
            ],
        },
        "reviewed_by": _nullable({"type": "string"}),
        "reviewed_at": _nullable({"type": "string"}),
        "review_notes": _nullable({"type": "string"}),
    })
    return _object(properties)


def unsupported_schema_keywords(schema):
    unsupported = {"oneOf", "not", "if", "then", "else", "dependentSchemas"}
    found = set()
    if isinstance(schema, dict):
        found.update(unsupported.intersection(schema))
        for value in schema.values():
            found.update(unsupported_schema_keywords(value))
    elif isinstance(schema, list):
        for value in schema:
            found.update(unsupported_schema_keywords(value))
    return found


def validate_strict_schema(schema):
    errors = []
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                errors.append("object_missing_properties")
            else:
                if set(schema.get("required", ())) != set(properties):
                    errors.append("object_required_incomplete")
            if schema.get("additionalProperties") is not False:
                errors.append("object_allows_additional_properties")
        for value in schema.values():
            errors.extend(validate_strict_schema(value))
    elif isinstance(schema, list):
        for value in schema:
            errors.extend(validate_strict_schema(value))
    return tuple(errors)


def estimate_output_tokens(character_count: int) -> int:
    return (max(0, character_count) + 3) // 4

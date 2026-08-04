from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from crypto_investigator.ai.factory import AIProviderFactory
from crypto_investigator.ai.cache import AICache
from crypto_investigator.ai.budget import completion_budget
from crypto_investigator.ai.errors import AITimeoutError
from crypto_investigator.ai.fallback import DeterministicFallbackProvider
from crypto_investigator.ai.input_compactor import InputCompactor
from crypto_investigator.ai.models import AIStatus, AIUsage
from crypto_investigator.ai.prompt_builder import PROMPT_VERSION, PromptBuilder
from crypto_investigator.ai.response_parser import ResponseParser
from crypto_investigator.ai.redaction import redact_text
from crypto_investigator.ai.settings import AISettings
from crypto_investigator.ai.schema import narrative_response_schema
from crypto_investigator.ai.validator import NarrativeValidator
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.narratives.export import (
    NarrativeExporter,
    decode,
    decode_public_result,
    encode,
)


class NarrativeEngine:
    def run(
        self,
        investigation,
        output: Path,
        *,
        settings: AISettings | None = None,
        requested: bool = False,
        language: str = "zh-TW",
        tone: str = "professional",
        sections: tuple[str, ...] = (),
        save_prompt: bool = False,
        mock_response: str | dict | None = None,
        use_cache: bool = True,
        refresh: bool = False,
        prompt_mode: str = "standard",
    ):
        raw_input = NarrativeInputBuilder().build(
            investigation, language=language, tone=tone,
            requested_sections=sections or NarrativeInputBuilder().build(investigation).requested_sections,
        )
        return self.run_input(
            raw_input, output, settings=settings, requested=requested,
            save_prompt=save_prompt, mock_response=mock_response,
            use_cache=use_cache, refresh=refresh, prompt_mode=prompt_mode,
        )

    def run_input(
        self,
        raw_input,
        output: Path,
        *,
        settings: AISettings | None = None,
        requested: bool = False,
        save_prompt: bool = False,
        mock_response: str | dict | None = None,
        use_cache: bool = True,
        refresh: bool = False,
        prompt_mode: str = "standard",
    ):
        settings = settings or AISettings.from_env()
        language = raw_input.language
        source = InputCompactor(max_input_characters=settings.max_input_characters).compact(
            raw_input, settings.privacy_mode, prompt_mode
        )
        budget = completion_budget(
            source, configured_tokens=settings.max_output_tokens
        )
        request_settings = replace(
            settings, max_output_tokens=budget.requested_tokens
        )
        prompt = PromptBuilder().build(source)
        if len(prompt) > settings.max_input_characters:
            source = replace(source, limitations=source.limitations + ("AI 輸入達硬性字元上限，已使用 deterministic fallback。",))
            requested = False
        input_hash = sha256(json.dumps(encode(source), sort_keys=True).encode()).hexdigest()
        output.mkdir(parents=True, exist_ok=True)
        exporter = NarrativeExporter()
        exporter.write(source, output / "narrative_input.json")
        errors: list[dict[str, str]] = []
        usage = AIUsage(settings.provider, settings.model)
        response_metadata = {
            "requested_max_completion_tokens": budget.requested_tokens,
            "estimated_minimum_completion_tokens": budget.estimated_minimum_tokens,
            "completion_hard_cap": budget.hard_cap_tokens,
        }
        result = None
        cache_hit = False
        started = perf_counter()
        if requested and settings.enabled:
            cache = AICache(output / ".ai_cache", settings.cache_ttl_seconds)
            cache_key = cache.key(
                provider=settings.provider, model=settings.model,
                prompt_version=PROMPT_VERSION, input_hash=input_hash,
                language=language, sections=source.requested_sections,
                temperature=settings.temperature, schema_version=source.schema_version,
            )
            cached = None if refresh or not use_cache else cache.get(cache_key)
            if cached:
                try:
                    candidate = decode(cached["narrative"])
                    if NarrativeValidator().validate(candidate, source).valid:
                        result = candidate
                        cache_hit = True
                        usage = AIUsage(settings.provider, settings.model, cache_hit=True)
                except (KeyError, TypeError, ValueError):
                    result = None
            try:
                if result is None:
                    provider = AIProviderFactory.create(
                        request_settings, mock_response=mock_response or "{}"
                    )
                    last_error = None
                    for attempt in range(settings.max_retries + 1):
                        try:
                            response = provider.generate(
                                prompt, schema=narrative_response_schema(source)
                            )
                            usage = response.usage
                            response_metadata = dict(response.raw_metadata)
                            parser = ResponseParser()
                            parsed = parser.parse(response.content)
                            tagged_artifact = "__type__" in parsed
                            candidate = decode_public_result(decode(parsed))
                            if not tagged_artifact:
                                candidate = self._normalize_citations(
                                    candidate, source
                                )
                            response_metadata["parser_warnings"] = tuple(parser.warnings)
                            response_metadata["parser_diagnostics"] = parser.diagnostics
                            candidate = replace(
                                candidate,
                                metadata=replace(
                                    candidate.metadata,
                                    provider=provider.provider_name,
                                    model=provider.model_name,
                                    prompt_version=PROMPT_VERSION,
                                    status="ai_complete",
                                    fallback_used=False,
                                    input_sha256=input_hash,
                                    input_tokens=usage.input_tokens,
                                    output_token_limit=budget.requested_tokens,
                                    output_tokens=usage.output_tokens,
                                    finish_reason=response_metadata.get("finish_reason"),
                                    validation_status="passed",
                                    fallback_reason=None,
                                ),
                            )
                            candidate_validation = NarrativeValidator().validate(
                                candidate, source
                            )
                            if not candidate_validation.valid:
                                raise ValueError(
                                    "AI narrative validation failed: "
                                    + ", ".join(candidate_validation.errors)
                                )
                            fallback_candidate = (
                                DeterministicFallbackProvider().generate(source)
                            )
                            if self._substantive_text(candidate) == self._substantive_text(
                                fallback_candidate
                            ):
                                raise ValueError(
                                    "AI narrative adds no substantive content beyond fallback"
                                )
                            result = candidate
                            last_error = None
                            break
                        except Exception as error:
                            last_error = error
                            details = getattr(error, "safe_details", {})
                            if isinstance(details, dict):
                                response_metadata.update({
                                    key: value for key, value in details.items()
                                    if key != "error"
                                })
                                retained_usage = details.get("usage")
                                if isinstance(retained_usage, dict):
                                    usage = AIUsage(
                                        settings.provider,
                                        settings.model,
                                        int(retained_usage.get("prompt_tokens", 0)),
                                        int(retained_usage.get("completion_tokens", 0)),
                                        int(retained_usage.get("total_tokens", 0)),
                                        1,
                                    )
                            if not isinstance(error, AITimeoutError):
                                break
                    if last_error:
                        raise last_error
                    if use_cache:
                        cache.put(cache_key, {
                            "request_hash": input_hash,
                            "prompt_version": PROMPT_VERSION,
                            "model": settings.model,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "validated": True,
                            "usage": asdict(usage),
                            "narrative": encode(result),
                        })
            except Exception as error:
                record = {
                    "type": type(error).__name__,
                    "message": redact_text(str(error), 500),
                }
                safe_details = getattr(error, "safe_details", None)
                if isinstance(safe_details, dict):
                    record.update(safe_details)
                for key, value in response_metadata.items():
                    record.setdefault(key, value)
                errors.append(record)
        if result is None:
            result = DeterministicFallbackProvider().generate(source)
        validation = NarrativeValidator().validate(result, source)
        if not validation.valid:
            errors.extend({"type": "validation", "message": item} for item in validation.errors)
            result = DeterministicFallbackProvider().generate(source)
            validation = NarrativeValidator().validate(result, source)
        result = replace(result, validation=validation)
        fallback = result.metadata.fallback_used
        if fallback:
            response_metadata.setdefault(
                "fallback_reason", self._fallback_reason(errors, requested, settings.enabled)
            )
            response_metadata["fallback"] = True
        else:
            response_metadata["fallback"] = False
        result = replace(
            result,
            metadata=replace(
                result.metadata,
                input_tokens=usage.input_tokens,
                output_token_limit=budget.requested_tokens,
                output_tokens=usage.output_tokens,
                finish_reason=response_metadata.get("finish_reason"),
                validation_status="passed" if not fallback else "failed",
                fallback_reason=response_metadata.get("fallback_reason"),
            ),
        )
        exporter.write(result, output / "narrative.json")
        self._write(output / "narrative_validation.json", asdict(validation))
        self._write(output / "ai_usage.json", asdict(usage))
        self._write(output / "ai_response_metadata.json", response_metadata)
        self._write(output / "ai_errors.json", errors)
        status = AIStatus(
            enabled=settings.enabled, requested=requested, provider=result.metadata.provider,
            model=result.metadata.model, status="fallback" if fallback else "complete",
            cache_hit=cache_hit, validation_passed=validation.valid, fallback_used=fallback,
            generated_at=datetime.now(timezone.utc), warnings=tuple(item["message"] for item in errors),
        )
        self._write(output / "ai_status.json", asdict(status))
        manifest = {
            "prompt_version": PROMPT_VERSION, "provider": settings.provider,
            "model": settings.model, "settings": {
                "temperature": settings.temperature,
                "max_output_tokens": budget.requested_tokens,
                "configured_max_output_tokens": settings.max_output_tokens,
                "completion_hard_cap": budget.hard_cap_tokens,
                "privacy_mode": settings.privacy_mode,
                "reasoning_effort": settings.reasoning_effort,
            },
            "input_sha256": input_hash, "schema_version": source.schema_version,
            "section_list": list(source.requested_sections),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_characters": len(prompt),
            "prompt_mode": prompt_mode,
            "elapsed_seconds": perf_counter() - started,
        }
        self._write(output / "prompt_manifest.json", manifest)
        if save_prompt:
            (output / "prompt_redacted.txt").write_text(prompt, encoding="utf-8")
        return result

    @staticmethod
    def _write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _substantive_text(result):
        values = []
        for name in result.__dataclass_fields__:
            section = getattr(result, name)
            if hasattr(section, "paragraphs"):
                values.extend(paragraph.text.strip() for paragraph in section.paragraphs)
        values.extend(claim.statement.strip() for claim in result.claims)
        return tuple(values)

    @staticmethod
    def _fallback_reason(errors, requested, enabled):
        if not requested:
            return "not_requested"
        if not enabled:
            return "ai_disabled"
        if not errors:
            return "deterministic_fallback"
        first = errors[0]
        if first.get("finish_reason") == "length":
            return "output_truncated"
        error_type = str(first.get("type", "")).casefold()
        if "parse" in error_type:
            return "truncated_or_invalid_json"
        if "schema" in error_type:
            return "schema_validation_failed"
        return "ai_validation_failed"

    @staticmethod
    def _normalize_citations(result, source):
        """Make public Evidence IDs the single model-facing citation namespace."""
        from crypto_investigator.narratives.models import NarrativeCitation

        known = {
            str(item.get("evidence_id"))
            for item in source.evidence_index
            if item.get("evidence_id")
        }
        citations = {}
        for name in source.requested_sections:
            section = getattr(result, name, None)
            if section is None:
                continue
            for paragraph in section.paragraphs:
                for evidence_id in paragraph.citation_ids:
                    if evidence_id in known:
                        citations[(evidence_id, name)] = NarrativeCitation(
                            evidence_id, evidence_id, name
                        )
        return replace(
            result,
            citations=tuple(
                citations[key] for key in sorted(citations)
            ),
        )

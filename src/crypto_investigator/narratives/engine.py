from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from crypto_investigator.ai.factory import AIProviderFactory
from crypto_investigator.ai.cache import AICache
from crypto_investigator.ai.fallback import DeterministicFallbackProvider
from crypto_investigator.ai.input_compactor import InputCompactor
from crypto_investigator.ai.models import AIStatus, AIUsage
from crypto_investigator.ai.prompt_builder import PROMPT_VERSION, PromptBuilder
from crypto_investigator.ai.response_parser import ResponseParser
from crypto_investigator.ai.settings import AISettings
from crypto_investigator.ai.validator import NarrativeValidator
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.narratives.export import NarrativeExporter, decode, encode


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
    ):
        settings = settings or AISettings.from_env()
        raw_input = NarrativeInputBuilder().build(
            investigation, language=language, tone=tone,
            requested_sections=sections or NarrativeInputBuilder().build(investigation).requested_sections,
        )
        source = InputCompactor(max_input_characters=settings.max_input_characters).compact(
            raw_input, settings.privacy_mode
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
                    provider = AIProviderFactory.create(settings, mock_response=mock_response or "{}")
                    last_error = None
                    for attempt in range(settings.max_retries + 1):
                        try:
                            response = provider.generate(prompt, schema={"type": "object"})
                            ResponseParser().parse(response.content)
                            last_error = None
                            break
                        except Exception as error:
                            last_error = error
                    if last_error:
                        raise last_error
                    usage = response.usage
                    result = DeterministicFallbackProvider().generate(source)
                    result = replace(
                        result,
                        metadata=replace(
                            result.metadata, provider=provider.provider_name,
                            model=provider.model_name, status="ai_complete", fallback_used=False,
                        ),
                    )
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
                errors.append({"type": type(error).__name__, "message": str(error)[:500]})
        if result is None:
            result = DeterministicFallbackProvider().generate(source)
        validation = NarrativeValidator().validate(result, source)
        if not validation.valid:
            errors.extend({"type": "validation", "message": item} for item in validation.errors)
            result = DeterministicFallbackProvider().generate(source)
            validation = NarrativeValidator().validate(result, source)
        result = replace(result, validation=validation)
        exporter.write(result, output / "narrative.json")
        self._write(output / "narrative_validation.json", asdict(validation))
        self._write(output / "ai_usage.json", asdict(usage))
        self._write(output / "ai_errors.json", errors)
        fallback = result.metadata.fallback_used
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
                "max_output_tokens": settings.max_output_tokens,
                "privacy_mode": settings.privacy_mode,
            },
            "input_sha256": input_hash, "schema_version": source.schema_version,
            "section_list": list(source.requested_sections),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "prompt_characters": len(prompt),
            "elapsed_seconds": perf_counter() - started,
        }
        self._write(output / "prompt_manifest.json", manifest)
        if save_prompt:
            (output / "prompt_redacted.txt").write_text(prompt, encoding="utf-8")
        return result

    @staticmethod
    def _write(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

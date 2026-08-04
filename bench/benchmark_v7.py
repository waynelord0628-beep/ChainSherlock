from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter
import tracemalloc

from crypto_investigator.ai.fallback import DeterministicFallbackProvider
from crypto_investigator.ai.input_compactor import InputCompactor
from crypto_investigator.ai.prompt_builder import PromptBuilder
from crypto_investigator.ai.response_parser import ResponseParser
from crypto_investigator.ai.validator import NarrativeValidator
from crypto_investigator.investigation.export import InvestigationExporter
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.narratives.export import encode


def timed(call):
    started = perf_counter()
    value = call()
    return value, perf_counter() - started


def main():
    root = Path(__file__).resolve().parents[1]
    investigation = InvestigationExporter().read(
        root / "examples/v65_tron_validation/investigation.json"
    )
    tracemalloc.start()
    source, build = timed(lambda: NarrativeInputBuilder().build(investigation))
    compact, compaction = timed(lambda: InputCompactor().compact(source))
    prompt, prompt_build = timed(lambda: PromptBuilder().build(compact))
    parsed, response_parse = timed(lambda: ResponseParser().parse("{}"))
    narrative, fallback = timed(lambda: DeterministicFallbackProvider().generate(compact))
    validation, validation_time = timed(lambda: NarrativeValidator().validate(narrative, compact))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    artifact = json.dumps(encode(compact), ensure_ascii=False)
    result = {
        "narrative_input_build_seconds": build,
        "compaction_seconds": compaction,
        "prompt_build_seconds": prompt_build,
        "response_parse_seconds": response_parse,
        "validation_seconds": validation_time,
        "fallback_seconds": fallback,
        "report_integration_seconds": None,
        "peak_memory_bytes": peak,
        "input_artifact_bytes": len(artifact.encode()),
        "prompt_character_count": len(prompt),
        "validation_passed": validation.valid,
        "real_api_latency_excluded": True,
    }
    destination = root / "examples/v7_mock_validation/benchmark.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

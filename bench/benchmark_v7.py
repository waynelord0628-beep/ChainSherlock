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
from crypto_investigator.ai.settings import AISettings
from crypto_investigator.investigation.export import InvestigationExporter
from crypto_investigator.narratives.composer import NarrativeInputBuilder
from crypto_investigator.narratives.export import encode
from crypto_investigator.reports.offline import OfflineReportComposer
from crypto_investigator.reports.export import ReportExportCoordinator


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
    destination = root / "output/v7_benchmark/benchmark.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    standard = InputCompactor().compact(source, mode="standard")
    compact = InputCompactor().compact(source, mode="compact")
    standard_prompt = PromptBuilder().build(standard)
    compact_prompt = PromptBuilder().build(compact)
    comparison = {
        "standard_characters": len(standard_prompt),
        "compact_characters": len(compact_prompt),
        "reduction_ratio": 1 - (len(compact_prompt) / len(standard_prompt)),
        "omitted_counts": compact.omitted_counts,
        "retained_fact_count": len(compact.conclusion_facts),
        "retained_observation_count": len(compact.observations),
        "retained_evidence_count": len(compact.evidence_index),
    }
    (destination.parent / "prompt_size_comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    report_benchmark = {}
    for mode, report_narrative in (
        ("deterministic_fallback", narrative),
        ("mock_ai_validated", __import__("dataclasses").replace(
            narrative,
            metadata=__import__("dataclasses").replace(
                narrative.metadata, provider="mock", model="mock-v1",
                status="ai_complete", fallback_used=False,
            ),
        )),
    ):
        tracemalloc.start()
        document, composition = timed(
            lambda: OfflineReportComposer().compose(
                report_narrative, compact, output_directory=str(destination.parent)
            )
        )
        mode_dir = destination.parent / f"report_benchmark_{mode}"
        format_times = {}
        for format_name in ("markdown", "html", "docx", "pdf"):
            _, format_times[format_name] = timed(
                lambda name=format_name: ReportExportCoordinator().export(
                    document, mode_dir, name
                )
            )
        _, report_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report_benchmark[mode] = {
            "composition_seconds": composition,
            "export_seconds": format_times,
            "peak_memory_bytes": report_peak,
            "output_sizes": {
                path.name: path.stat().st_size
                for path in mode_dir.iterdir()
                if path.is_file()
            },
        }
    (destination.parent / "report_integration_benchmark.json").write_text(
        json.dumps(report_benchmark, indent=2), encoding="utf-8"
    )
    result["report_integration_seconds"] = report_benchmark[
        "deterministic_fallback"
    ]["composition_seconds"]
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

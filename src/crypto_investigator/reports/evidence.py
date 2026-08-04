from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from crypto_investigator.reports.errors import EvidenceError
from crypto_investigator.reports.formatting import safe_relative
from crypto_investigator.reports.models import ReportEvidence


class EvidenceManifest:
    allowed_names = {
        "analysis.json",
        "flow_graph.json",
        "provider_status.json",
        "provider_errors.json",
        "rejected_records.json",
    }

    def collect(
        self,
        paths: tuple[Path, ...],
        *,
        root: Path,
        maximum_entries: int = 5000,
    ) -> tuple[ReportEvidence, ...]:
        evidence = []
        for path in sorted(paths, key=lambda item: str(item))[:maximum_entries]:
            if not path.exists() or not path.is_file():
                continue
            try:
                relative = safe_relative(path, root)
                payload = path.read_bytes()
                stat = path.stat()
            except (OSError, ValueError) as error:
                raise EvidenceError("Unable to collect evidence") from error
            evidence.append(
                ReportEvidence(
                    evidence_id=f"E{len(evidence) + 1}",
                    evidence_type=self._type(path),
                    source=path.name,
                    source_reference=relative,
                    description=f"Evidence file: {path.name}",
                    collected_at=datetime.now(UTC),
                    hash=hashlib.sha256(payload).hexdigest(),
                    metadata={
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime, UTC
                        ).isoformat(),
                    },
                )
            )
        return tuple(evidence)

    def write(self, evidence: tuple[ReportEvidence, ...], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                [
                    {
                        "evidence_id": item.evidence_id,
                        "relative_path": item.source_reference,
                        "sha256": item.hash,
                        "size": item.metadata.get("size"),
                        "modified_at": item.metadata.get("modified_at"),
                        "evidence_type": item.evidence_type,
                    }
                    for item in evidence
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _type(path: Path) -> str:
        if path.suffix.casefold() in {".csv", ".xls", ".xlsx"}:
            return "source_file"
        return path.stem

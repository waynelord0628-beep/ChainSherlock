from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.factory import AnalyzerFactory
from crypto_investigator.analyzers.models import AnalysisResult
from crypto_investigator.domain.transaction import Direction, Transaction


class AnalysisEngine:
    """Run registered analyzers against canonical Domain Transactions."""

    analyzer_names = ("summary", "statistics", "counterparty", "timeline", "flow")

    def analyze(
        self,
        transactions: tuple[Transaction, ...],
        target_address: str | None = None,
    ) -> AnalysisResult:
        context = AnalysisContext(transactions, target_address)
        results = {
            name: AnalyzerFactory.create(name).analyze(context)
            for name in self.analyzer_names
        }
        warnings: list[str] = []
        if target_address is None and any(
            transaction.direction is Direction.UNKNOWN for transaction in transactions
        ):
            warnings.append(
                "Target address was not provided; unknown directions are not included "
                "in directional or counterparty totals."
            )
        missing_timestamp_count = sum(
            1 for transaction in transactions if transaction.timestamp is None
        )
        unconfirmed_count = sum(
            1
            for transaction in transactions
            if transaction.metadata.get("source_record", {})
            .get("source_metadata", {})
            .get("confirmed")
            is False
        )
        if missing_timestamp_count:
            warnings.append(
                f"excluded_unconfirmed_without_timestamp={missing_timestamp_count}"
            )
        return AnalysisResult(
            summary=results["summary"],
            statistics=results["statistics"],
            counterparties=results["counterparty"],
            timeline=results["timeline"],
            flow=results["flow"],
            metadata={
                "transaction_count": len(transactions),
                "target_address": target_address,
                "analyzers": self.analyzer_names,
                "unconfirmed_count": unconfirmed_count,
                "missing_timestamp_count": missing_timestamp_count,
            },
            warnings=tuple(warnings),
        )

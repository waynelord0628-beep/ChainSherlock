from decimal import Decimal

from crypto_investigator.analysis_materiality import (
    DEFAULT_TRX_DUST_THRESHOLD,
    classify_trc10_symbol,
    split_material_transactions,
)
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
        *,
        trx_dust_threshold: Decimal = DEFAULT_TRX_DUST_THRESHOLD,
    ) -> AnalysisResult:
        material, exclusions = split_material_transactions(
            transactions,
            trx_dust_threshold=trx_dust_threshold,
        )
        gross_context = AnalysisContext(transactions, target_address)
        material_context = AnalysisContext(material, target_address)
        results = {
            "summary": AnalyzerFactory.create("summary").analyze(gross_context),
            "statistics": AnalyzerFactory.create("statistics").analyze(gross_context),
            "counterparty": AnalyzerFactory.create("counterparty").analyze(
                material_context
            ),
            "timeline": AnalyzerFactory.create("timeline").analyze(material_context),
            "flow": AnalyzerFactory.create("flow").analyze(material_context),
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
        dust_exclusions = tuple(
            item
            for item in exclusions
            if item.rule == "native_trx_below_materiality_threshold"
        )
        other_asset_exclusions = tuple(
            item
            for item in exclusions
            if item.rule == "trc10_or_other_asset_not_native_trx"
        )
        native_trx = tuple(
            transaction
            for transaction in transactions
            if transaction.asset_symbol == "TRX"
            and transaction.transaction_type.value == "native_transfer"
            and transaction.metadata.get("contract_type") == "TransferContract"
        )
        trc10_summary = {}
        for item in other_asset_exclusions:
            transaction = item.transaction
            symbol = transaction.asset_symbol or "unknown_tron_asset"
            current = trc10_summary.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "transaction_count": 0,
                    "incoming_amount": Decimal(0),
                    "source_addresses": set(),
                },
            )
            current["transaction_count"] += 1
            current["incoming_amount"] += transaction.amount or Decimal(0)
            if transaction.from_address:
                current["source_addresses"].add(transaction.from_address)
        trc10_summary_rows = []
        for symbol, current in sorted(
            trc10_summary.items(),
            key=lambda entry: (-entry[1]["transaction_count"], entry[0]),
        ):
            category, reason, confidence = classify_trc10_symbol(symbol)
            trc10_summary_rows.append(
                {
                    "symbol": symbol,
                    "transaction_count": current["transaction_count"],
                    "incoming_amount": str(current["incoming_amount"]),
                    "source_address_count": len(current["source_addresses"]),
                    "candidate_classification": category,
                    "reason_code": reason,
                    "confidence": confidence,
                    "review_status": "not_reviewed",
                }
            )
        if dust_exclusions:
            warnings.append(
                "micro_trx_excluded_from_behavior_analysis="
                f"{len(dust_exclusions)}"
            )
        return AnalysisResult(
            summary=results["summary"],
            statistics=results["statistics"],
            counterparties=results["counterparty"],
            timeline=results["timeline"],
            flow=results["flow"],
            metadata={
                "transaction_count": len(transactions),
                "analysis_transaction_count": len(material),
                "analysis_record_count": len(material),
                "materiality_excluded_count": len(exclusions),
                "micro_trx_excluded_count": len(dust_exclusions),
                "micro_trx_excluded_amount": str(
                    sum(
                        (
                            item.transaction.amount or Decimal(0)
                            for item in dust_exclusions
                        ),
                        Decimal(0),
                    )
                ),
                "trx_dust_threshold": str(trx_dust_threshold),
                "trc10_other_asset_excluded_count": len(
                    other_asset_exclusions
                ),
                "native_trx_transaction_count": len(native_trx),
                "native_trx_incoming_count": sum(
                    item.direction is Direction.INCOMING
                    or (
                        bool(target_address)
                        and item.to_address.casefold() == target_address.casefold()
                    )
                    for item in native_trx
                ),
                "native_trx_outgoing_count": sum(
                    item.direction is Direction.OUTGOING
                    or (
                        bool(target_address)
                        and item.from_address.casefold() == target_address.casefold()
                    )
                    for item in native_trx
                ),
                "trc10_asset_symbols": tuple(sorted(trc10_summary)),
                "trc10_other_asset_summary": tuple(trc10_summary_rows),
                "materiality_exclusion_rule": (
                    "native TRX below threshold and TransferAssetContract "
                    "are excluded from behavior analysis"
                ),
                "materiality_reversible": True,
                "materiality_review_status": "not_reviewed",
                "target_address": target_address,
                "analyzers": self.analyzer_names,
                "unconfirmed_count": unconfirmed_count,
                "missing_timestamp_count": missing_timestamp_count,
            },
            warnings=tuple(warnings),
        )

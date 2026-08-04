from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.models import (
    AssetStatistics,
    StatisticsResult,
    TransactionAmountRef,
)
from crypto_investigator.domain.transaction import Direction, Transaction
from crypto_investigator.utils.analysis import transaction_direction


class StatisticsAnalyzer:
    name = "statistics"

    def analyze(self, context: AnalysisContext) -> StatisticsResult:
        by_asset: dict[str, list[Transaction]] = defaultdict(list)
        incoming: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        outgoing: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for transaction in context.transactions:
            if transaction.asset_symbol is None or transaction.amount is None:
                continue
            asset = transaction.asset_symbol
            by_asset[asset].append(transaction)
            direction = transaction_direction(transaction, context.target_address)
            if direction is Direction.INCOMING:
                incoming[asset] += transaction.amount
            elif direction is Direction.OUTGOING:
                outgoing[asset] += transaction.amount

        breakdown: dict[str, AssetStatistics] = {}
        maximums: dict[str, TransactionAmountRef] = {}
        minimums: dict[str, TransactionAmountRef] = {}
        averages: dict[str, Decimal] = {}
        medians: dict[str, Decimal] = {}
        for asset, transactions in sorted(by_asset.items()):
            amounts = [transaction.amount for transaction in transactions]
            typed_amounts = [amount for amount in amounts if amount is not None]
            total = sum(typed_amounts, Decimal("0"))
            average = total / len(typed_amounts)
            median_amount = median(typed_amounts)
            max_transaction = max(
                transactions, key=lambda transaction: transaction.amount or Decimal("0")
            )
            min_transaction = min(
                transactions, key=lambda transaction: transaction.amount or Decimal("0")
            )
            breakdown[asset] = AssetStatistics(
                transaction_count=len(typed_amounts),
                total_amount=total,
                average_amount=average,
                median_amount=median_amount,
                max_amount=max(typed_amounts),
                min_amount=min(typed_amounts),
            )
            averages[asset] = average
            medians[asset] = median_amount
            maximums[asset] = TransactionAmountRef(
                max_transaction.tx_hash, max_transaction.amount or Decimal("0")
            )
            minimums[asset] = TransactionAmountRef(
                min_transaction.tx_hash, min_transaction.amount or Decimal("0")
            )

        asset_counts = Counter(
            transaction.asset_symbol
            for transaction in context.transactions
            if transaction.asset_symbol is not None
        )
        top_asset = (
            sorted(asset_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if asset_counts
            else None
        )
        active_days = {
            transaction.timestamp.date()
            for transaction in context.transactions
            if transaction.timestamp is not None
        }
        return StatisticsResult(
            incoming_amount=dict(sorted(incoming.items())),
            outgoing_amount=dict(sorted(outgoing.items())),
            asset_breakdown=breakdown,
            top_asset=top_asset,
            average_amount=averages,
            median_amount=medians,
            max_transaction=maximums,
            min_transaction=minimums,
            transaction_frequency=(
                len(context.transactions) / len(active_days) if active_days else 0.0
            ),
        )

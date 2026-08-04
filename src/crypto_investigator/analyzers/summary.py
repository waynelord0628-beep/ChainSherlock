from collections import Counter

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.models import SummaryResult
from crypto_investigator.domain.transaction import Direction
from crypto_investigator.utils.analysis import counterparty_address, transaction_direction


class SummaryAnalyzer:
    name = "summary"

    def analyze(self, context: AnalysisContext) -> SummaryResult:
        transactions = context.transactions
        timestamps = [tx.timestamp for tx in transactions if tx.timestamp is not None]
        directions = [
            transaction_direction(tx, context.target_address) for tx in transactions
        ]
        counterparties = {
            address
            for tx in transactions
            if (address := counterparty_address(tx, context.target_address)) is not None
        }
        assets = tuple(sorted({tx.asset_symbol for tx in transactions if tx.asset_symbol}))
        asset_counts = Counter(
            tx.asset_symbol for tx in transactions if tx.asset_symbol is not None
        )
        top_asset = (
            sorted(asset_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if asset_counts
            else None
        )
        active_dates = {timestamp.date() for timestamp in timestamps}
        unconfirmed_count = sum(
            1
            for tx in transactions
            if tx.metadata.get("source_record", {})
            .get("source_metadata", {})
            .get("confirmed")
            is False
        )
        return SummaryResult(
            first_seen=min(timestamps) if timestamps else None,
            last_seen=max(timestamps) if timestamps else None,
            transaction_count=len(transactions),
            incoming_count=directions.count(Direction.INCOMING),
            outgoing_count=directions.count(Direction.OUTGOING),
            unique_counterparties=len(counterparties),
            active_days=len(active_dates),
            assets=assets,
            top_asset=top_asset,
            average_daily_transactions=(
                len(transactions) / len(active_dates) if active_dates else 0.0
            ),
            unconfirmed_count=unconfirmed_count,
            missing_timestamp_count=sum(
                1 for transaction in transactions if transaction.timestamp is None
            ),
        )

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from crypto_investigator.analyzers.base import AnalysisContext
from crypto_investigator.analyzers.models import Counterparty
from crypto_investigator.domain.transaction import Direction
from crypto_investigator.utils.analysis import counterparty_address, transaction_direction


@dataclass(slots=True)
class _Accumulator:
    incoming_count: int = 0
    outgoing_count: int = 0
    incoming_amount: dict[str, Decimal] = field(
        default_factory=lambda: defaultdict(lambda: Decimal("0"))
    )
    outgoing_amount: dict[str, Decimal] = field(
        default_factory=lambda: defaultdict(lambda: Decimal("0"))
    )
    timestamps: list[datetime] = field(default_factory=list)


class CounterpartyAnalyzer:
    name = "counterparty"

    def analyze(self, context: AnalysisContext) -> tuple[Counterparty, ...]:
        accumulators: dict[str, _Accumulator] = {}
        for transaction in context.transactions:
            address = counterparty_address(transaction, context.target_address)
            direction = transaction_direction(transaction, context.target_address)
            if address is None or direction not in (
                Direction.INCOMING,
                Direction.OUTGOING,
            ):
                continue
            accumulator = accumulators.setdefault(address, _Accumulator())
            if transaction.timestamp is not None:
                accumulator.timestamps.append(transaction.timestamp)
            asset = transaction.asset_symbol
            amount = transaction.amount
            if direction is Direction.INCOMING:
                accumulator.incoming_count += 1
                if asset is not None and amount is not None:
                    accumulator.incoming_amount[asset] += amount
            else:
                accumulator.outgoing_count += 1
                if asset is not None and amount is not None:
                    accumulator.outgoing_amount[asset] += amount

        counterparties = [
            Counterparty(
                address=address,
                incoming_count=value.incoming_count,
                outgoing_count=value.outgoing_count,
                incoming_amount_by_asset=dict(sorted(value.incoming_amount.items())),
                outgoing_amount_by_asset=dict(sorted(value.outgoing_amount.items())),
                first_seen=min(value.timestamps) if value.timestamps else None,
                last_seen=max(value.timestamps) if value.timestamps else None,
                interaction_count=value.incoming_count + value.outgoing_count,
                direction=self._relationship_direction(value),
            )
            for address, value in accumulators.items()
        ]
        return tuple(
            sorted(
                counterparties,
                key=lambda item: (-item.interaction_count, item.address),
            )
        )

    @staticmethod
    def _relationship_direction(value: _Accumulator) -> Direction:
        if value.incoming_count and value.outgoing_count:
            return Direction.UNKNOWN
        if value.incoming_count:
            return Direction.INCOMING
        if value.outgoing_count:
            return Direction.OUTGOING
        return Direction.UNKNOWN

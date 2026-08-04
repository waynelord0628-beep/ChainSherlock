from decimal import Decimal, localcontext
import math


ZERO = Decimal("0")


def ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal:
    if not denominator:
        return ZERO
    with localcontext() as context:
        context.prec = 28
        return Decimal(numerator) / Decimal(denominator)


def herfindahl(values) -> Decimal:
    total = sum(values)
    return sum((ratio(value, total) ** 2 for value in values), ZERO) if total else ZERO


def gini(values) -> Decimal:
    ordered = sorted(Decimal(value) for value in values)
    total = sum(ordered, ZERO)
    count = len(ordered)
    if not count or not total:
        return ZERO
    weighted = sum((Decimal(index) * value for index, value in enumerate(ordered, 1)), ZERO)
    return (Decimal(2) * weighted) / (Decimal(count) * total) - ratio(count + 1, count)


def entropy(values) -> Decimal:
    total = sum(values)
    if not total:
        return ZERO
    return Decimal(str(-sum(float(ratio(value, total)) * math.log(float(ratio(value, total)), 2) for value in values if value)))


def median(values) -> Decimal | None:
    ordered = sorted(Decimal(value) for value in values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)

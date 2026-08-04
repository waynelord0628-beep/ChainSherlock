from dataclasses import dataclass
from typing import Awaitable, Callable

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.errors import ProviderError, ProviderPaginationError
from crypto_investigator.providers.models import (
    Completeness,
    ProviderCapability,
    ProviderPage,
    ProviderRawRecord,
    ProviderResult,
)


@dataclass(frozen=True, slots=True)
class PaginationLimits:
    max_pages: int = 100
    max_records: int = 100000
    page_size: int = 100


async def paginate(
    *,
    provider: str,
    chain: Chain,
    capability: ProviderCapability,
    fetch_page: Callable[[str | None, int], Awaitable[ProviderPage]],
    limits: PaginationLimits,
) -> ProviderResult:
    records: list[ProviderRawRecord] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    warnings: list[str] = []
    errors: list[Exception] = []
    pages = 0
    truncated = False
    truncation_reason: str | None = None
    available_more = False

    while pages < limits.max_pages and len(records) < limits.max_records:
        try:
            page = await fetch_page(cursor, limits.page_size)
        except ProviderError as error:
            errors.append(error)
            warnings.append("Pagination stopped after a provider error")
            break
        pages += 1
        remaining = limits.max_records - len(records)
        records.extend(page.records[:remaining])
        if len(page.records) > remaining:
            truncated = True
            truncation_reason = "max_records"
            available_more = True
            warnings.append("Maximum record limit reached")
            break
        if not page.records or page.next_cursor is None:
            break
        if page.next_cursor in seen_cursors or page.next_cursor == cursor:
            error = ProviderPaginationError(
                provider=provider,
                chain=chain,
                capability=capability,
                safe_message="Repeated pagination cursor detected",
                missing_data_category=capability.value,
            )
            errors.append(error)
            warnings.append(error.safe_message)
            break
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor

    if pages >= limits.max_pages and cursor is not None:
        warnings.append("Maximum page limit reached")
        truncated = True
        truncation_reason = truncation_reason or "max_pages"
        available_more = True
    if len(records) >= limits.max_records and (available_more or cursor is not None):
        if "Maximum record limit reached" not in warnings:
            warnings.append("Maximum record limit reached")
        truncated = True
        truncation_reason = "max_records"
        available_more = True
    completeness = (
        Completeness.PARTIAL
        if errors or warnings
        else Completeness.COMPLETE if records else Completeness.EMPTY
    )
    return ProviderResult(
        provider=provider,
        chain=chain,
        capability=capability,
        records=tuple(records),
        completeness=completeness,
        warnings=tuple(warnings),
        errors=tuple(errors),
        missing_data=(capability.value,) if errors else (),
        pages_fetched=pages,
        truncated=truncated,
        truncation_reason=truncation_reason,
        fetched_records=len(records),
        available_more=available_more,
    )

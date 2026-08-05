from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable

from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.errors import ProviderError, ProviderPaginationError
from crypto_investigator.providers.models import (
    Completeness,
    ProviderCapability,
    PaginationMetadata,
    PaginationStrategy,
    ProviderPage,
    ProviderOrdering,
    ProviderRawRecord,
    ProviderResult,
)


@dataclass(frozen=True, slots=True)
class PaginationLimits:
    max_pages: int | None = 100
    max_records: int | None = 100000
    page_size: int = 100


async def paginate(
    *,
    provider: str,
    chain: Chain,
    capability: ProviderCapability,
    fetch_page: Callable[[str | None, int], Awaitable[ProviderPage]],
    limits: PaginationLimits,
    ordering: ProviderOrdering = ProviderOrdering.PROVIDER_DEFINED,
    pagination_strategy: PaginationStrategy = PaginationStrategy.PROVIDER_DEFINED,
    stop_before: datetime | None = None,
    stop_after: datetime | None = None,
    start_cursor: str | None = None,
) -> ProviderResult:
    records: list[ProviderRawRecord] = []
    cursor: str | None = start_cursor
    seen_cursors: set[str] = set()
    warnings: list[str] = []
    errors: list[Exception] = []
    pages = 0
    truncated = False
    truncation_reason: str | None = None
    available_more = False

    while (
        (limits.max_pages is None or pages < limits.max_pages)
        and (limits.max_records is None or len(records) < limits.max_records)
    ):
        try:
            page = await fetch_page(cursor, limits.page_size)
        except ProviderError as error:
            errors.append(error)
            warnings.append("Pagination stopped after a provider error")
            available_more = True
            break
        pages += 1
        remaining = (
            None
            if limits.max_records is None
            else limits.max_records - len(records)
        )
        records.extend(page.records if remaining is None else page.records[:remaining])
        if remaining is not None and len(page.records) > remaining:
            truncated = True
            truncation_reason = "max_records"
            available_more = True
            warnings.append("Maximum record limit reached")
            break
        page_timestamps = tuple(
            record.timestamp
            for record in page.records
            if record.timestamp is not None
        )
        scope_end_reached = (
            ordering is ProviderOrdering.NEWEST_FIRST
            and stop_before is not None
            and page_timestamps
            and min(page_timestamps) < stop_before
        ) or (
            ordering is ProviderOrdering.OLDEST_FIRST
            and stop_after is not None
            and page_timestamps
            and max(page_timestamps) > stop_after
        )
        if scope_end_reached:
            cursor = None
            break
        if not page.records or page.next_cursor is None:
            cursor = None
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

    if (
        limits.max_pages is not None
        and pages >= limits.max_pages
        and cursor is not None
    ):
        warnings.append("Maximum page limit reached")
        truncated = True
        truncation_reason = truncation_reason or "max_pages"
        available_more = True
    if (
        limits.max_records is not None
        and len(records) >= limits.max_records
        and (available_more or cursor is not None)
    ):
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
    timestamps = sorted(
        record.timestamp for record in records if record.timestamp is not None
    )
    pagination_complete = (
        not errors and not truncated and not available_more and cursor is None
    )
    metadata = PaginationMetadata(
        provider=provider,
        chain=chain,
        capability=capability,
        ordering=ordering,
        pagination_strategy=pagination_strategy,
        next_cursor=cursor if available_more else None,
        has_more=available_more,
        pagination_complete=pagination_complete,
        fetched_records=len(records),
        accepted_records=len(records),
        earliest_fetched_at=timestamps[0] if timestamps else None,
        latest_fetched_at=timestamps[-1] if timestamps else None,
        truncated=truncated,
        truncation_reason=truncation_reason,
        completeness=completeness,
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
        pagination=metadata,
    )

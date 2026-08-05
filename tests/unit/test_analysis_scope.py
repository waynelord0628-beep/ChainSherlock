from datetime import UTC, datetime, timedelta

import pytest

from crypto_investigator.application.analysis_scope import (
    apply_scope,
    build_time_scope_result,
)
from crypto_investigator.domain.scope import (
    AnalysisScope,
    PaginationPolicy,
    ScopeType,
    in_scope,
)
from crypto_investigator.domain.transaction import Chain
from crypto_investigator.providers.capabilities import (
    capability_policy,
    required_capabilities_complete,
    unresolved_required_errors,
)
from crypto_investigator.providers.models import (
    Completeness,
    PaginationMetadata,
    PaginationStrategy,
    ProviderCapability,
    ProviderOrdering,
    ProviderPage,
    ProviderRawRecord,
    ProviderResult,
)
from crypto_investigator.providers.pagination import PaginationLimits, paginate
from crypto_investigator.providers.errors import ProviderRateLimitError


START = datetime(2026, 1, 1, tzinfo=UTC)


def record(index, *, asset="USDT"):
    return ProviderRawRecord(
        chain=Chain.TRON,
        source_provider="fixture",
        source_type="token",
        tx_hash=f"h{index}",
        timestamp=START + timedelta(days=index),
        asset_symbol=asset,
    )


def provider_result(capability, records, *, complete=True, truncated=False):
    completeness = Completeness.COMPLETE if complete else Completeness.PARTIAL
    return ProviderResult(
        "fixture",
        Chain.TRON,
        capability,
        tuple(records),
        completeness,
        truncated=truncated,
        pagination=PaginationMetadata(
            "fixture",
            Chain.TRON,
            capability,
            pagination_complete=complete and not truncated,
            fetched_records=len(records),
            accepted_records=len(records),
            truncated=truncated,
            completeness=completeness,
        ),
    )


def custom_scope(**changes):
    values = {
        "scope_type": ScopeType.CUSTOM_DATE_RANGE,
        "date_from": START + timedelta(days=1),
        "date_to": START + timedelta(days=3),
        "timezone": "UTC",
        "pagination_policy": PaginationPolicy.TO_PROVIDER_END,
    }
    values.update(changes)
    return AnalysisScope(**values)


def test_full_history_rejects_test_page_limit():
    with pytest.raises(ValueError):
        AnalysisScope(
            scope_type=ScopeType.FULL_HISTORY,
            max_pages=1,
        )


def test_full_history_rejects_bounded_pagination():
    with pytest.raises(ValueError):
        AnalysisScope(
            scope_type=ScopeType.FULL_HISTORY,
            pagination_policy=PaginationPolicy.BOUNDED,
        )


def test_custom_range_requires_both_boundaries():
    with pytest.raises(ValueError):
        AnalysisScope(
            scope_type=ScopeType.CUSTOM_DATE_RANGE,
            date_from=START,
        )


@pytest.mark.parametrize(
    "inclusive_start,inclusive_end,expected",
    (
        (True, True, [1, 2, 3]),
        (False, True, [2, 3]),
        (True, False, [1, 2]),
        (False, False, [2]),
    ),
)
def test_custom_date_range_boundaries(
    inclusive_start, inclusive_end, expected
):
    scope = custom_scope(
        inclusive_start=inclusive_start,
        inclusive_end=inclusive_end,
    )
    accepted, excluded = apply_scope(tuple(record(i) for i in range(5)), scope)
    assert [int(item.tx_hash[1:]) for item in accepted] == expected
    assert excluded == 5 - len(expected)


def test_missing_timestamp_is_excluded_from_custom_range():
    missing = record(1)
    missing = ProviderRawRecord(
        **{
            name: getattr(missing, name)
            for name in missing.__dataclass_fields__
            if name != "timestamp"
        },
        timestamp=None,
    )
    assert not in_scope(missing.timestamp, custom_scope())


def test_timezone_boundary_compares_same_instant():
    scope = AnalysisScope(
        scope_type=ScopeType.CUSTOM_DATE_RANGE,
        date_from=datetime.fromisoformat("2026-01-02T08:00:00+08:00"),
        date_to=datetime.fromisoformat("2026-01-02T09:00:00+08:00"),
        timezone="Asia/Taipei",
    )
    assert in_scope(datetime.fromisoformat("2026-01-02T00:00:00+00:00"), scope)
    assert not in_scope(
        datetime.fromisoformat("2026-01-01T23:59:59+00:00"), scope
    )


def test_quick_preview_is_not_full_history_complete():
    scope = AnalysisScope(
        scope_type=ScopeType.QUICK_PREVIEW,
        pagination_policy=PaginationPolicy.BOUNDED,
        max_pages=1,
        max_records=500,
    )
    results = (
        provider_result(
            ProviderCapability.ADDRESS_TRANSACTIONS, (record(1),)
        ),
        provider_result(ProviderCapability.TOKEN_TRANSFERS, (record(2),)),
    )
    assert build_time_scope_result(scope, results).full_history_complete is False


def test_time_scope_records_first_last_by_asset_and_capability():
    scope = AnalysisScope()
    results = (
        provider_result(
            ProviderCapability.ADDRESS_TRANSACTIONS,
            (record(1, asset="TRX"), record(4, asset="TRX")),
        ),
        provider_result(
            ProviderCapability.TOKEN_TRANSFERS,
            (record(2, asset="USDT"), record(3, asset="USDT")),
        ),
    )
    value = build_time_scope_result(scope, results)
    assert value.overall_first_seen == START + timedelta(days=1)
    assert value.overall_last_seen == START + timedelta(days=4)
    assert value.first_seen_by_asset["USDT"] == START + timedelta(days=2)
    assert (
        value.first_seen_by_capability["token_transfers"]
        == START + timedelta(days=2)
    )
    assert value.full_history_complete is True


def test_required_capability_missing_prevents_complete():
    results = (
        provider_result(
            ProviderCapability.ADDRESS_TRANSACTIONS, (record(1),)
        ),
    )
    assert required_capabilities_complete(Chain.TRON, results) is False


def test_optional_capability_missing_does_not_prevent_complete():
    results = (
        provider_result(
            ProviderCapability.ADDRESS_TRANSACTIONS, (record(1),)
        ),
        provider_result(ProviderCapability.TOKEN_TRANSFERS, (record(2),)),
    )
    assert required_capabilities_complete(Chain.TRON, results) is True
    assert ProviderCapability.BALANCE in capability_policy(
        Chain.TRON
    ).optional_capabilities


def test_fallback_completion_resolves_primary_required_capability_error():
    results = (
        provider_result(
            ProviderCapability.ADDRESS_TRANSACTIONS, (record(1),)
        ),
        provider_result(ProviderCapability.TOKEN_TRANSFERS, (record(2),)),
    )
    errors = (
        type(
            "SafeError",
            (),
            {"capability": ProviderCapability.ADDRESS_TRANSACTIONS},
        )(),
    )
    assert unresolved_required_errors(Chain.TRON, results, errors) == ()


def test_bitcoin_policy_is_not_account_based():
    policy = capability_policy(Chain.BITCOIN)
    assert ProviderCapability.UTXO in policy.required_capabilities
    assert ProviderCapability.TOKEN_TRANSFERS in policy.unsupported_capabilities


@pytest.mark.asyncio
async def test_pagination_to_explicit_end_is_complete():
    pages = [
        ProviderPage((record(1),), "next"),
        ProviderPage((record(2),), None),
    ]

    async def fetch(cursor, size):
        return pages.pop(0)

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=10, max_records=10, page_size=1),
        ordering=ProviderOrdering.NEWEST_FIRST,
        pagination_strategy=PaginationStrategy.FINGERPRINT,
    )
    assert result.pagination.pagination_complete is True
    assert result.pagination.next_cursor is None
    assert result.completeness == Completeness.COMPLETE


@pytest.mark.asyncio
async def test_max_pages_is_partial_and_preserves_next_cursor():
    async def fetch(cursor, size):
        return ProviderPage((record(1),), "next")

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=1, max_records=10, page_size=1),
    )
    assert result.truncated is True
    assert result.truncation_reason == "max_pages"
    assert result.pagination.pagination_complete is False
    assert result.pagination.next_cursor == "next"
    assert result.completeness == Completeness.PARTIAL


@pytest.mark.asyncio
async def test_resume_starts_from_saved_cursor_without_refetching_first_page():
    seen = []

    async def fetch(cursor, size):
        seen.append(cursor)
        return ProviderPage((record(2),), None)

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=1, max_records=10, page_size=1),
        start_cursor="saved-fingerprint",
    )
    assert seen == ["saved-fingerprint"]
    assert result.pagination.pagination_complete is True
    assert result.pagination.next_cursor is None


@pytest.mark.asyncio
async def test_max_records_is_partial():
    async def fetch(cursor, size):
        return ProviderPage((record(1), record(2)), "next")

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=10, max_records=1, page_size=2),
    )
    assert len(result.records) == 1
    assert result.truncation_reason == "max_records"
    assert result.pagination.has_more is True


@pytest.mark.asyncio
async def test_rate_limit_preserves_resume_cursor():
    calls = 0

    async def fetch(cursor, size):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ProviderPage((record(1),), "resume-fingerprint")
        raise ProviderRateLimitError(
            provider="fixture",
            chain=Chain.TRON,
            capability=ProviderCapability.ADDRESS_TRANSACTIONS,
            safe_message="rate limited",
            status_code=429,
            retryable=True,
        )

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=None, max_records=None, page_size=1),
    )
    assert result.pagination.pagination_complete is False
    assert result.pagination.has_more is True
    assert result.pagination.next_cursor == "resume-fingerprint"


@pytest.mark.asyncio
async def test_repeated_cursor_is_partial():
    async def fetch(cursor, size):
        return ProviderPage((record(1),), "same")

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=10, max_records=10, page_size=1),
    )
    assert result.completeness == Completeness.PARTIAL
    assert result.pagination.pagination_complete is False


@pytest.mark.asyncio
async def test_newest_first_custom_scope_stops_after_crossing_start():
    calls = 0

    async def fetch(cursor, size):
        nonlocal calls
        calls += 1
        return ProviderPage(
            (record(5 - calls * 2), record(6 - calls * 2)),
            f"page-{calls}",
        )

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=None, max_records=None, page_size=2),
        ordering=ProviderOrdering.NEWEST_FIRST,
        stop_before=START + timedelta(days=2),
    )
    assert calls == 2
    assert result.pagination.pagination_complete is True


@pytest.mark.asyncio
async def test_oldest_first_custom_scope_stops_after_crossing_end():
    calls = 0

    async def fetch(cursor, size):
        nonlocal calls
        calls += 1
        start = calls * 2 - 2
        return ProviderPage(
            (record(start), record(start + 1)),
            f"page-{calls}",
        )

    result = await paginate(
        provider="fixture",
        chain=Chain.TRON,
        capability=ProviderCapability.ADDRESS_TRANSACTIONS,
        fetch_page=fetch,
        limits=PaginationLimits(max_pages=None, max_records=None, page_size=2),
        ordering=ProviderOrdering.OLDEST_FIRST,
        stop_after=START + timedelta(days=2),
    )
    assert calls == 2
    assert result.pagination.pagination_complete is True

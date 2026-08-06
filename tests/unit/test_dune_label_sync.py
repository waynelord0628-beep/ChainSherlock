import json

import httpx
from typer.testing import CliRunner

from crypto_investigator.cli import app
from crypto_investigator.labels.dune_sync import _parse_datetime
from crypto_investigator.labels import (
    DuneLabelClient,
    DuneSyncError,
    LocalLabelDatabase,
    lookup_dune_deposit_address,
    sync_dune_dataset,
)


def test_dune_utc_suffix_datetime_is_parsed() -> None:
    parsed = _parse_datetime("2025-05-09 09:00:36.830 UTC")

    assert parsed is not None
    assert parsed.isoformat() == "2025-05-09T09:00:36.830000+00:00"


def _transport(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("x-dune-api-key") == "secret"
    if request.url.path.endswith("/sql/execute"):
        payload = json.loads(request.content)
        assert "cex.addresses" in payload["sql"]
        assert "to_hex(address)" in payload["sql"]
        return httpx.Response(200, json={"execution_id": "exec-1"})
    if request.url.path.endswith("/status"):
        return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
    offset = int(request.url.params.get("offset", 0))
    if offset == 0:
        return httpx.Response(
            200,
            json={
                "result": {
                    "rows": [
                        {
                            "blockchain": "tron",
                            "address": "TOne",
                            "cex_name": "OKX",
                            "distinct_name": "Hot Wallet",
                            "added_date": "2026-01-01",
                        }
                    ]
                },
                "next_offset": 1,
            },
        )
    return httpx.Response(
        200,
        json={
            "result": {
                "rows": [
                    {
                        "blockchain": "tron",
                        "address": "TTwo",
                        "cex_name": "MEXC",
                        "distinct_name": "Reserve",
                    }
                ]
            }
        },
    )


def test_dune_sync_paginates_and_builds_offline_database(tmp_path):
    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(_transport),
        poll_interval=0,
        page_size=1,
    )
    result = sync_dune_dataset(
        client=client,
        database=tmp_path / "labels.db",
        dataset="cex",
        chains=("tron",),
    )
    assert result.fetched_rows == 2
    assert result.imported_records == 2
    database = LocalLabelDatabase(result.database)
    assert database.resolve("tron", "TOne").preferred.label == "OKX"
    assert database.resolve("tron", "TTwo").preferred.label == "MEXC"


def test_all_chain_cex_sync_omits_chain_filter(tmp_path):
    captured = {}

    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"execution_id": "all-1"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
        return httpx.Response(200, json={"result": {"rows": []}})

    result = sync_dune_dataset(
        client=DuneLabelClient(
            "secret",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        ),
        database=tmp_path / "all.db",
        dataset="cex",
        chains=("all",),
    )
    assert "WHERE blockchain IN" not in captured["sql"]
    assert result.fetched_rows == 0


def test_hex_addresses_decode_by_chain():
    from crypto_investigator.labels.dune_sync import _display_address

    tron = "TM1zzNDZD2DPASbKcgdVoTYhfmYgtfwx9R"
    assert _display_address("tron", {"address_hex": tron.encode().hex()}) == tron
    assert _display_address(
        "ethereum", {"address_hex": "AA" * 20}
    ) == "0x" + ("aa" * 20)


def test_curated_labels_require_categories(tmp_path):
    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        poll_interval=0,
    )
    try:
        sync_dune_dataset(
            client=client,
            database=tmp_path / "labels.db",
            dataset="labels",
            chains=("all",),
            categories=(),
        )
    except ValueError as error:
        assert "requires at least one category" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_curated_labels_are_imported_by_category(tmp_path):
    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            payload = json.loads(request.content)
            assert "category IN ('institution')" in payload["sql"]
            return httpx.Response(200, json={"execution_id": "labels-1"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "rows": [
                        {
                            "blockchain": "ethereum",
                            "address_hex": "11" * 20,
                            "name": "Example Institution",
                            "category": "institution",
                            "model_name": "institutions",
                        }
                    ]
                }
            },
        )

    path = tmp_path / "labels.db"
    result = sync_dune_dataset(
        client=DuneLabelClient(
            "secret",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        ),
        database=path,
        dataset="labels",
        chains=("all",),
        categories=("institution",),
    )
    assert result.imported_records == 1
    assert (
        LocalLabelDatabase(path)
        .resolve("ethereum", "0x" + ("11" * 20))
        .preferred.label
        == "Example Institution"
    )


def test_contract_dataset_excludes_pair_and_pool(tmp_path):
    captured = {}

    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"execution_id": "contracts-1"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
        return httpx.Response(200, json={"result": {"rows": []}})

    sync_dune_dataset(
        client=DuneLabelClient(
            "secret",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        ),
        database=tmp_path / "contracts.db",
        dataset="contracts",
        chains=("all",),
    )
    assert "primary_category = 'Bridge'" in captured["sql"]
    assert "NOT LIKE '%pair%'" in captured["sql"]
    assert "NOT LIKE '%pool%'" in captured["sql"]


def test_services_exclude_bulk_custody_addresses(tmp_path):
    captured = {}

    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"execution_id": "services-1"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
        return httpx.Response(200, json={"result": {"rows": []}})

    sync_dune_dataset(
        client=DuneLabelClient(
            "secret",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        ),
        database=tmp_path / "services.db",
        dataset="services",
        chains=("all",),
    )
    assert "Payment Processing" in captured["sql"]
    assert "Privacy Services" in captured["sql"]
    assert "Custody Services" not in captured["sql"]


def test_deposit_lookup_is_bounded_and_imported_as_candidate(tmp_path):
    captured = {}

    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"execution_id": "deposit-1"})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"state": "QUERY_STATE_COMPLETED"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "rows": [
                        {
                            "blockchain": "ethereum",
                            "address_hex": "22" * 20,
                            "cex_name": "Example CEX",
                            "first_deposit_token_standard": "erc20",
                            "deposit_first_block_time": "2025-01-01 00:00:00 UTC",
                            "deposit_count": 3,
                            "deposit_unique_key": "deposit-key",
                        }
                    ]
                }
            },
        )

    path = tmp_path / "deposit.db"
    result = lookup_dune_deposit_address(
        client=DuneLabelClient(
            "secret",
            transport=httpx.MockTransport(handler),
            poll_interval=0,
        ),
        database=path,
        chain="ethereum",
        address="0x" + ("22" * 20),
    )

    assert "cex.deposit_addresses" in captured["sql"]
    assert "address = from_hex" in captured["sql"]
    assert result.imported_records == 1
    preferred = LocalLabelDatabase(path).resolve(
        "ethereum", "0x" + ("22" * 20)
    ).preferred
    assert preferred is not None
    assert preferred.category == "exchange_deposit_candidate"
    assert preferred.verification_status == "unverified_candidate"


def test_deposit_lookup_rejects_unsupported_chain_without_api_call(tmp_path):
    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        poll_interval=0,
    )

    try:
        lookup_dune_deposit_address(
            client=client,
            database=tmp_path / "deposit.db",
            chain="tron",
            address="TOne",
        )
    except ValueError as error:
        assert "EVM chains" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_offline_database_returns_all_conflicting_labels(tmp_path):
    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(_transport),
        poll_interval=0,
        page_size=1,
    )
    path = tmp_path / "labels.db"
    sync_dune_dataset(client=client, database=path, dataset="cex", chains=("tron",))
    resolution = LocalLabelDatabase(path).resolve("tron", "TOne")
    assert len(resolution.matches) == 1
    assert resolution.conflicting_labels == ()


def test_dune_http_error_is_redacted():
    def handler(request):
        return httpx.Response(
            401,
            headers={"x-request-id": "req-safe"},
            json={"error": "contains sensitive remote details"},
        )

    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(handler),
        poll_interval=0,
    )
    try:
        client.execute("SELECT 1")
    except DuneSyncError as error:
        message = str(error)
    else:
        raise AssertionError("expected DuneSyncError")
    assert "401" in message
    assert "req-safe" in message
    assert "secret" not in message
    assert "sensitive remote details" not in message


def test_failed_execution_preserves_safe_dune_diagnostic():
    def handler(request):
        if request.url.path.endswith("/sql/execute"):
            return httpx.Response(200, json={"execution_id": "failed-1"})
        return httpx.Response(
            200,
            json={
                "state": "QUERY_STATE_FAILED",
                "error": {
                    "type": "syntax_error",
                    "message": "line 1: unsupported column",
                },
            },
        )

    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(handler),
        poll_interval=0,
    )
    try:
        client.execute("SELECT bad")
    except DuneSyncError as error:
        message = str(error)
    else:
        raise AssertionError("expected DuneSyncError")
    assert "syntax_error" in message
    assert "unsupported column" in message
    assert "secret" not in message


def test_cli_requires_dune_key(monkeypatch, tmp_path):
    monkeypatch.delenv("DUNE_API_KEY", raising=False)
    result = CliRunner().invoke(
        app,
        ["labels-sync-dune", "--output", str(tmp_path / "labels.db")],
    )
    assert result.exit_code != 0
    assert "DUNE_API_KEY is not configured" in result.output


def test_cli_queries_local_database(tmp_path):
    client = DuneLabelClient(
        "secret",
        transport=httpx.MockTransport(_transport),
        poll_interval=0,
        page_size=1,
    )
    path = tmp_path / "labels.db"
    sync_dune_dataset(client=client, database=path, dataset="cex", chains=("tron",))
    result = CliRunner().invoke(
        app,
        [
            "labels-query-local",
            "TOne",
            "--chain",
            "tron",
            "--database",
            str(path),
        ],
    )
    assert result.exit_code == 0
    assert '"label": "OKX"' in result.output

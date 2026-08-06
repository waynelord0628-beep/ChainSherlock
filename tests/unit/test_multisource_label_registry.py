from datetime import UTC, datetime, timedelta
import sqlite3

from typer.testing import CliRunner

from crypto_investigator.cli import app
from crypto_investigator.labels import (
    CommercialLabelPolicy,
    EnrichmentBudget,
    LabelCacheEntry,
    MultiSourceLabelRegistry,
)


def test_dune_cex_import_preserves_distinct_name_and_snapshot(tmp_path):
    source = tmp_path / "cex.csv"
    source.write_text(
        "blockchain,address,cex_name,distinct_name,added_date\n"
        "tron,TOne,ExampleEx,Hot Wallet 1,2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )
    registry = MultiSourceLabelRegistry.import_dune_cex_csv(source)
    record = registry.records[0]
    assert record.chain == "tron"
    assert record.label == "ExampleEx"
    assert record.category == "exchange"
    assert record.subcategory == "Hot Wallet 1"
    assert record.verification_status == "dune_curated"
    assert registry.snapshots[0].sha256


def test_dune_owner_import_preserves_evidence(tmp_path):
    source = tmp_path / "owners.csv"
    source.write_text(
        "blockchain,address,custody_owner,primary_category,source_evidence,"
        "source_website,owner_key\n"
        "ethereum,0xABC,Custodian,cex,0xTX,https://evidence.test,owner-1\n",
        encoding="utf-8",
    )
    record = MultiSourceLabelRegistry.import_dune_owner_csv(source).records[0]
    assert record.address == "0xabc"
    assert record.label == "Custodian"
    assert record.source_evidence == "0xTX"
    assert record.source_record_id == "owner-1"


def test_same_address_keeps_multiple_sources_and_labels(tmp_path):
    cex = tmp_path / "cex.csv"
    owner = tmp_path / "owner.csv"
    cex.write_text(
        "blockchain,address,cex_name,distinct_name\n"
        "tron,TOne,ExampleEx,Hot\n",
        encoding="utf-8",
    )
    owner.write_text(
        "blockchain,address,custody_owner,primary_category\n"
        "tron,TOne,Example Custody,custody\n",
        encoding="utf-8",
    )
    registry = MultiSourceLabelRegistry.combine(
        MultiSourceLabelRegistry.import_dune_cex_csv(cex),
        MultiSourceLabelRegistry.import_dune_owner_csv(owner),
    )
    resolved = registry.resolve("TRON", "TOne")
    assert len(resolved.matches) == 2
    assert resolved.conflicting_labels == ("Example Custody", "ExampleEx")


def test_source_priority_selects_official_over_dune(tmp_path):
    cex = tmp_path / "cex.csv"
    ofac = tmp_path / "ofac.csv"
    cex.write_text(
        "blockchain,address,cex_name\ntron,TOne,ExampleEx\n", encoding="utf-8"
    )
    ofac.write_text(
        "uid,name,program,id_type,id_value\n"
        "42,Listed Entity,PROGRAM,Digital Currency Address - TRX,TOne\n",
        encoding="utf-8",
    )
    registry = MultiSourceLabelRegistry.combine(
        MultiSourceLabelRegistry.import_dune_cex_csv(cex),
        MultiSourceLabelRegistry.import_ofac_digital_currency_csv(ofac),
    )
    preferred = registry.resolve("tron", "TOne").preferred
    assert preferred is not None
    assert preferred.source == "ofac_sdn"
    assert preferred.verification_status == "official"


def test_ofac_wide_address_column_is_supported(tmp_path):
    source = tmp_path / "ofac.csv"
    source.write_text(
        "uid,name,Digital Currency Address - ETH\n"
        "7,Listed Entity,0xABC\n",
        encoding="utf-8",
    )
    record = MultiSourceLabelRegistry.import_ofac_digital_currency_csv(
        source
    ).records[0]
    assert record.chain == "ethereum"
    assert record.address == "0xabc"
    assert record.category == "sanctioned"


def test_ofac_does_not_remove_other_labels(tmp_path):
    source = tmp_path / "ofac.csv"
    source.write_text(
        "uid,name,id_type,id_value\n"
        "7,Listed Entity,Digital Currency Address - TRX,TOne\n",
        encoding="utf-8",
    )
    first = MultiSourceLabelRegistry.import_ofac_digital_currency_csv(source)
    combined = MultiSourceLabelRegistry.combine(first, first)
    assert len(combined.records) == 1


def test_sqlite_preserves_snapshots_and_multiple_labels(tmp_path):
    source = tmp_path / "cex.csv"
    source.write_text(
        "blockchain,address,cex_name,distinct_name\n"
        "tron,TOne,ExampleEx,Hot\n"
        "tron,TOne,ExampleEx,Reserve\n",
        encoding="utf-8",
    )
    registry = MultiSourceLabelRegistry.import_dune_cex_csv(source)
    database = registry.write_sqlite(tmp_path / "labels.db")
    with sqlite3.connect(database) as connection:
        snapshots = connection.execute(
            "SELECT COUNT(*) FROM label_snapshots"
        ).fetchone()[0]
        records = connection.execute(
            "SELECT COUNT(*) FROM label_records"
        ).fetchone()[0]
    assert snapshots == 1
    assert records == 1


def test_sqlite_key_is_not_only_chain_and_address(tmp_path):
    cex = tmp_path / "cex.csv"
    owner = tmp_path / "owner.csv"
    cex.write_text(
        "blockchain,address,cex_name\ntron,TOne,ExampleEx\n", encoding="utf-8"
    )
    owner.write_text(
        "blockchain,address,custody_owner,primary_category\n"
        "tron,TOne,Custodian,custody\n",
        encoding="utf-8",
    )
    registry = MultiSourceLabelRegistry.combine(
        MultiSourceLabelRegistry.import_dune_cex_csv(cex),
        MultiSourceLabelRegistry.import_dune_owner_csv(owner),
    )
    database = registry.write_sqlite(tmp_path / "labels.db")
    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM label_records").fetchone()[0]
    assert count == 2


def test_commercial_policy_skips_existing_local_match():
    budget = EnrichmentBudget(maximum_calls=3)
    assert not CommercialLabelPolicy().should_query(
        has_local_match=True, is_material_endpoint=True, budget=budget
    )
    assert budget.used_calls == 0


def test_commercial_policy_skips_non_material_address():
    assert not CommercialLabelPolicy().should_query(
        has_local_match=False,
        is_material_endpoint=False,
        budget=EnrichmentBudget(),
    )


def test_commercial_policy_uses_valid_cache():
    now = datetime.now(UTC)
    cache = LabelCacheEntry(
        "tron", "TOne", "misttrack", ("exchange",), "exchange",
        now, now + timedelta(days=1),
    )
    assert not CommercialLabelPolicy().should_query(
        has_local_match=False,
        is_material_endpoint=True,
        budget=EnrichmentBudget(),
        cached=cache,
    )


def test_commercial_policy_allows_expired_cache():
    now = datetime.now(UTC)
    cache = LabelCacheEntry(
        "tron", "TOne", "misttrack", ("exchange",), "exchange",
        now - timedelta(days=2), now - timedelta(days=1),
    )
    assert CommercialLabelPolicy().should_query(
        has_local_match=False,
        is_material_endpoint=True,
        budget=EnrichmentBudget(),
        cached=cache,
    )


def test_budget_never_exceeds_maximum():
    budget = EnrichmentBudget(maximum_calls=2)
    assert budget.consume()
    assert budget.consume()
    assert not budget.consume()
    assert budget.used_calls == 2
    assert budget.remaining_calls == 0


def test_cli_builds_registry_without_network_calls(tmp_path):
    source = tmp_path / "cex.csv"
    output = tmp_path / "labels.db"
    source.write_text(
        "blockchain,address,cex_name\ntron,TOne,ExampleEx\n", encoding="utf-8"
    )
    result = CliRunner().invoke(
        app,
        [
            "labels-build-registry",
            "--dune-cex",
            str(source),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.is_file()
    assert "Label records: 1" in result.output


def test_cli_requires_at_least_one_snapshot(tmp_path):
    result = CliRunner().invoke(
        app,
        ["labels-build-registry", "--output", str(tmp_path / "labels.db")],
    )
    assert result.exit_code != 0

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import networkx as nx
import pytest

from crypto_investigator.analyzers.engine import AnalysisEngine
from crypto_investigator.domain.transaction import Chain, Transaction
from crypto_investigator.graphs.builder import GraphBuilder
from crypto_investigator.graphs.errors import GraphSerializationError
from crypto_investigator.graphs.export import GraphExporter
from crypto_investigator.graphs.graphml_exporter import GraphMLExporter
from crypto_investigator.graphs.html_renderer import HtmlGraphRenderer
from crypto_investigator.graphs.json_exporter import JsonGraphExporter
from crypto_investigator.graphs.models import GraphFilterOptions
from crypto_investigator.graphs.networkx_adapter import NetworkXAdapter, graphml_value
from crypto_investigator.graphs.styling import NODE_COLORS, node_color


TARGET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40


def sample_graph():
    transaction = Transaction(
        chain=Chain.ETHEREUM,
        tx_hash="0x123",
        from_address=TARGET,
        to_address=OTHER,
        asset_symbol="USDT",
        amount=Decimal("1.234567890123456789"),
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
    )
    analysis = AnalysisEngine().analyze((transaction,), TARGET)
    return GraphBuilder().build(
        analysis, chain=Chain.ETHEREUM, target_address=TARGET
    )


def test_networkx_adapter_returns_multidigraph() -> None:
    converted = NetworkXAdapter().convert(sample_graph())
    assert isinstance(converted, nx.MultiDiGraph)


def test_networkx_preserves_node_and_edge_counts() -> None:
    graph = sample_graph()
    converted = NetworkXAdapter().convert(graph)
    assert converted.number_of_nodes() == len(graph.nodes)
    assert converted.number_of_edges() == len(graph.edges)


def test_networkx_preserves_multi_asset_scope_as_distinct_edges() -> None:
    first = sample_graph()
    edge = replace(
        first.edges[0],
        edge_id=first.edges[0].edge_id.replace("USDT", "ETH"),
        assets=("ETH",),
        amounts_by_asset={"ETH": Decimal("2")},
    )
    converted = NetworkXAdapter().convert(
        replace(first, edges=(first.edges[0], edge))
    )
    assert converted.number_of_edges() == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.2300"), "1.2300"),
        (datetime(2025, 1, 1, tzinfo=UTC), "2025-01-01T00:00:00+00:00"),
        (("ETH", "USDT"), '["ETH", "USDT"]'),
        ({"ETH": Decimal("1.2")}, '{"ETH": "1.2"}'),
    ],
)
def test_graphml_value_serialization(value, expected) -> None:
    assert graphml_value(value) == expected


def test_json_export_and_round_trip(tmp_path: Path) -> None:
    graph = sample_graph()
    path = JsonGraphExporter().write(graph, tmp_path / "flow_graph.json")
    restored = JsonGraphExporter().read(path)
    assert restored == graph


def test_json_output_is_deterministic(tmp_path: Path) -> None:
    graph = sample_graph()
    one = JsonGraphExporter().write(graph, tmp_path / "one.json")
    two = JsonGraphExporter().write(graph, tmp_path / "two.json")
    assert one.read_bytes() == two.read_bytes()


def test_json_malformed_input_raises_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(GraphSerializationError):
        JsonGraphExporter().read(path)


def test_graphml_can_be_reloaded_by_networkx(tmp_path: Path) -> None:
    path = GraphMLExporter().write(sample_graph(), tmp_path / "flow.graphml")
    restored = nx.read_graphml(path)
    assert len(restored.nodes) == 2
    assert len(restored.edges) == 1


def test_graphml_preserves_decimal_as_string(tmp_path: Path) -> None:
    path = GraphMLExporter().write(sample_graph(), tmp_path / "flow.graphml")
    restored = nx.read_graphml(path)
    data = next(iter(restored.edges(data=True)))[2]
    assert "1.234567890123456789" in data["amounts_by_asset"]


def test_graphml_serializes_datetime_as_iso8601(tmp_path: Path) -> None:
    path = GraphMLExporter().write(sample_graph(), tmp_path / "flow.graphml")
    restored = nx.read_graphml(path)
    data = next(iter(restored.edges(data=True)))[2]
    assert data["first_seen"] == "2025-01-01T00:00:00+00:00"


def test_html_is_generated_with_directed_arrows(tmp_path: Path) -> None:
    path = HtmlGraphRenderer().write(sample_graph(), tmp_path / "flow.html")
    content = path.read_text(encoding="utf-8")
    assert '"arrows": "to"' in content or '"arrows":"to"' in content


def test_html_contains_target_styling(tmp_path: Path) -> None:
    path = HtmlGraphRenderer().write(sample_graph(), tmp_path / "flow.html")
    content = path.read_text(encoding="utf-8")
    assert NODE_COLORS["target"] in content
    assert '"shape": "star"' in content or '"shape":"star"' in content


def test_html_uses_inline_assets(tmp_path: Path) -> None:
    path = HtmlGraphRenderer().write(sample_graph(), tmp_path / "flow.html")
    content = path.read_text(encoding="utf-8").lower()
    assert '<script src="https://' not in content
    assert '<link href="https://' not in content


@pytest.mark.parametrize(
    "payload",
    [
        "<script>v5_unique_attack()</script>",
        '<img src=x onerror="v5_unique_attack()">',
        "<svg onload=v5_unique_attack()>",
    ],
)
def test_html_escapes_malicious_node_labels(tmp_path: Path, payload: str) -> None:
    graph = sample_graph()
    malicious = replace(graph.nodes[0], label=payload, metadata={"html": payload})
    graph = replace(graph, nodes=(malicious, *graph.nodes[1:]))
    path = HtmlGraphRenderer().write(graph, tmp_path / "flow.html")
    content = path.read_text(encoding="utf-8")
    assert payload not in content
    assert "v5_unique_attack" in content


def test_html_limits_tooltip_length(tmp_path: Path) -> None:
    graph = sample_graph()
    long_label = "z" * 5000
    graph = replace(
        graph, nodes=(replace(graph.nodes[0], address=long_label), *graph.nodes[1:])
    )
    path = HtmlGraphRenderer().write(
        graph,
        tmp_path / "flow.html",
        GraphFilterOptions(maximum_tooltip_length=50),
    )
    assert "z" * 100 not in path.read_text(encoding="utf-8")


def test_html_does_not_render_provider_error_credentials(tmp_path: Path) -> None:
    graph = sample_graph()
    metadata = replace(
        graph.metadata,
        provider_errors=({"message": "api_key=V5_SECRET_SHOULD_NOT_RENDER"},),
    )
    path = HtmlGraphRenderer().write(
        replace(graph, metadata=metadata), tmp_path / "flow.html"
    )
    assert "V5_SECRET_SHOULD_NOT_RENDER" not in path.read_text(encoding="utf-8")


def test_html_shows_truncation_warning(tmp_path: Path) -> None:
    graph = sample_graph()
    graph = replace(graph, metadata=replace(graph.metadata, truncated=True))
    path = HtmlGraphRenderer().write(graph, tmp_path / "flow.html")
    assert "Graph data was truncated" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("exchange", NODE_COLORS["exchange"]),
        ("bridge", NODE_COLORS["bridge"]),
        ("mixer", NODE_COLORS["mixer"]),
        ("dex", NODE_COLORS["dex"]),
        ("service", NODE_COLORS["service"]),
        ("invalid", NODE_COLORS["unknown"]),
    ],
)
def test_category_styling(category, expected) -> None:
    assert node_color(category) == expected


def test_graph_exporter_writes_all_three_formats(tmp_path: Path) -> None:
    paths = GraphExporter().export_all(sample_graph(), tmp_path)
    assert set(paths) == {"json", "graphml", "html"}
    assert all(path.exists() for path in paths.values())

NODE_COLORS = {
    "target": "#dc2626",
    "exchange": "#2563eb",
    "bridge": "#7c3aed",
    "mixer": "#111827",
    "dex": "#0891b2",
    "service": "#16a34a",
    "unknown": "#64748b",
}

STAGE_COLORS = {
    "startup": "#f59e0b",
    "dominant": "#dc2626",
    "diversification": "#7c3aed",
    "dormant": "#64748b",
    "recovery": "#16a34a",
}
FUNDING_COLOR = "#0ea5e9"


def node_color(
    category: str,
    is_target: bool = False,
    stage: str | None = None,
    funding_source: bool = False,
) -> str:
    if stage in STAGE_COLORS:
        return STAGE_COLORS[stage]
    if funding_source:
        return FUNDING_COLOR
    return NODE_COLORS["target" if is_target else category if category in NODE_COLORS else "unknown"]

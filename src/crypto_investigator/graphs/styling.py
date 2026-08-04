NODE_COLORS = {
    "target": "#dc2626",
    "exchange": "#2563eb",
    "bridge": "#7c3aed",
    "mixer": "#111827",
    "dex": "#0891b2",
    "service": "#16a34a",
    "unknown": "#64748b",
}


def node_color(category: str, is_target: bool = False) -> str:
    return NODE_COLORS["target" if is_target else category if category in NODE_COLORS else "unknown"]

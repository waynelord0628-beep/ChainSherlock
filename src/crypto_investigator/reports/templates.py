from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from crypto_investigator.reports.errors import ReportTemplateError
from crypto_investigator.reports.typography import ScriptRole, mixed_script_runs


def _mixed_html(value, *, table=False):
    classes = {
        ScriptRole.CJK: "cjk",
        ScriptRole.LATIN: "latin",
        ScriptRole.NUMERIC: "numeric",
        ScriptRole.TABLE_TECH: "table-tech",
    }
    parts = []
    for run in mixed_script_runs(value, table=table):
        if run.role is ScriptRole.NEWLINE:
            parts.append("<br>")
        else:
            parts.append(
                f'<span class="{classes[run.role]}">{escape(run.text)}</span>'
            )
    return Markup("".join(parts))


def template_environment(*, html: bool = False) -> Environment:
    root = Path(__file__).resolve().parents[3] / "templates" / "reports"
    if not root.exists():
        raise ReportTemplateError("Report template directory is unavailable")
    environment = Environment(
        loader=FileSystemLoader(root),
        autoescape=True if html else False,
        undefined=StrictUndefined,
        trim_blocks=html,
        lstrip_blocks=html,
    )
    environment.filters["mixed_text"] = lambda value: _mixed_html(
        value, table=False
    )
    environment.filters["mixed_table"] = lambda value: _mixed_html(
        value, table=True
    )
    return environment

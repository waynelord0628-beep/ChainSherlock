from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from crypto_investigator.reports.errors import ReportTemplateError


def template_environment(*, html: bool = False) -> Environment:
    root = Path(__file__).resolve().parents[3] / "templates" / "reports"
    if not root.exists():
        raise ReportTemplateError("Report template directory is unavailable")
    return Environment(
        loader=FileSystemLoader(root),
        autoescape=True if html else False,
        undefined=StrictUndefined,
        trim_blocks=html,
        lstrip_blocks=html,
    )

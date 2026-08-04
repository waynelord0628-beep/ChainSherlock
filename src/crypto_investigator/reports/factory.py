from collections.abc import Callable

from crypto_investigator.reports.composer import ReportComposer
from crypto_investigator.reports.errors import ReportComposeError


class ReportFactory:
    _registry: dict[str, Callable[[], ReportComposer]] = {
        "address_report": ReportComposer,
        "transaction_report": ReportComposer,
        "file_report": ReportComposer,
    }

    @classmethod
    def create(cls, report_type: str) -> ReportComposer:
        try:
            return cls._registry[report_type]()
        except KeyError as error:
            raise ReportComposeError(f"Unknown report type: {report_type}") from error

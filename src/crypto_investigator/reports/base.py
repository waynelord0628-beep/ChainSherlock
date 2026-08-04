from typing import Protocol

from crypto_investigator.reports.models import ReportDocument


class ReportExporter(Protocol):
    def write(self, document: ReportDocument, path):
        """Export the composed ReportDocument without analysis logic."""

class ReportError(Exception):
    pass


class ReportComposeError(ReportError):
    pass


class ReportTemplateError(ReportError):
    pass


class ReportExportError(ReportError):
    pass


class MarkdownExportError(ReportExportError):
    pass


class HtmlExportError(ReportExportError):
    pass


class DocxExportError(ReportExportError):
    pass


class PdfExportError(ReportExportError):
    pass


class EvidenceError(ReportError):
    pass


class CitationError(ReportError):
    pass


class ReportSecurityError(ReportError):
    pass

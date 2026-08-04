from __future__ import annotations


class CaseError(Exception):
    """Base error for the V8 case foundation."""


class InvalidCaseIdError(CaseError):
    """Raised when a case identifier is unsafe."""


class UnsafeCasePathError(CaseError):
    """Raised when a path escapes its case workspace."""


class CaseNotFoundError(CaseError):
    """Raised when a requested case does not exist."""


class CaseAlreadyExistsError(CaseError):
    """Raised when a case identifier is already present."""


class EvidenceIntegrityError(CaseError):
    """Raised when immutable evidence no longer matches its record."""


class UnsupportedCaseSchemaError(CaseError):
    """Raised when a case schema cannot be migrated safely."""

class CryptoInvestigatorError(Exception):
    """Base application error."""


class InvalidIdentifierError(CryptoInvestigatorError):
    """Raised when input is neither a supported address nor transaction hash."""


class UnsupportedChainError(CryptoInvestigatorError):
    """Raised when a chain is unsupported."""


class ConfigurationError(CryptoInvestigatorError):
    """Raised when settings are invalid."""


class InvestigationError(Exception):
    pass


class InvestigationSerializationError(InvestigationError):
    pass


class UnknownInvestigationTypeError(InvestigationError):
    pass

from crypto_investigator.investigation.errors import UnknownInvestigationTypeError
from crypto_investigator.investigation.feature_engine import InvestigationFeatureEngine


class InvestigationFactory:
    _registry = {"default": InvestigationFeatureEngine, "deterministic": InvestigationFeatureEngine}

    @classmethod
    def create(cls, engine_type: str = "default"):
        try:
            return cls._registry[engine_type]()
        except KeyError as error:
            raise UnknownInvestigationTypeError(
                f"Unknown investigation type: {engine_type}"
            ) from error

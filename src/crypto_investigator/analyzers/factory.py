from crypto_investigator.analyzers.base import Analyzer
from crypto_investigator.analyzers.counterparty import CounterpartyAnalyzer
from crypto_investigator.analyzers.flow import FlowAnalyzer
from crypto_investigator.analyzers.statistics import StatisticsAnalyzer
from crypto_investigator.analyzers.summary import SummaryAnalyzer
from crypto_investigator.analyzers.timeline import TimelineAnalyzer


class AnalyzerFactory:
    _analyzers = {
        "summary": SummaryAnalyzer,
        "statistics": StatisticsAnalyzer,
        "counterparty": CounterpartyAnalyzer,
        "timeline": TimelineAnalyzer,
        "flow": FlowAnalyzer,
    }

    @classmethod
    def create(cls, name: str) -> Analyzer:
        analyzer_type = cls._analyzers.get(name.casefold())
        if analyzer_type is None:
            raise ValueError(f"Unknown analyzer: {name}")
        return analyzer_type()

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(cls._analyzers)

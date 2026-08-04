from __future__ import annotations

from collections.abc import Iterable

from crypto_investigator.config import Settings
from crypto_investigator.planner.engine import DeterministicPlanner
from crypto_investigator.providers.models import ProviderDescriptor


class PlannerFactory:
    @staticmethod
    def create(
        settings: Settings,
        *,
        provider_descriptors: Iterable[ProviderDescriptor] = (),
        ai_enabled: bool = False,
    ) -> DeterministicPlanner:
        return DeterministicPlanner(
            settings,
            provider_descriptors=provider_descriptors,
            ai_enabled=ai_enabled,
        )

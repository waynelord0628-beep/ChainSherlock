from dataclasses import asdict
from pathlib import Path
import json

from crypto_investigator.ai.models import AIUsage


class UsageTracker:
    def __init__(self, provider: str = "fallback", model: str = "deterministic-v1"):
        self.usage = AIUsage(provider, model)

    def record(self, *, input_tokens=0, output_tokens=0, elapsed_seconds=0.0, cache_hit=False):
        self.usage = AIUsage(
            provider=self.usage.provider,
            model=self.usage.model,
            input_tokens=self.usage.input_tokens + input_tokens,
            output_tokens=self.usage.output_tokens + output_tokens,
            total_tokens=self.usage.total_tokens + input_tokens + output_tokens,
            request_count=self.usage.request_count + (0 if cache_hit else 1),
            cache_hit=cache_hit,
            elapsed_seconds=self.usage.elapsed_seconds + elapsed_seconds,
            estimated_cost=None,
        )
        return self.usage

    def write(self, path: Path):
        path.write_text(json.dumps(asdict(self.usage), indent=2), encoding="utf-8")
        return path

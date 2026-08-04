from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class AISettings:
    enabled: bool = False
    provider: str = "fallback"
    model: str = "deterministic-v1"
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 120
    max_output_tokens: int = 3500
    temperature: float = 0
    reasoning_effort: str | None = "minimal"
    max_retries: int = 1
    max_input_characters: int = 100_000
    require_structured_output: bool = True
    allow_raw_transactions: bool = False
    allow_external_tools: bool = False
    allow_identity_inference: bool = False
    allow_criminal_judgment: bool = False
    privacy_mode: str = "standard"
    cache_ttl_seconds: int = 86400

    def __post_init__(self):
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not 1 <= self.max_output_tokens <= 8000:
            raise ValueError("max_output_tokens must be between 1 and 8000")
        if not 1000 <= self.max_input_characters <= 500_000:
            raise ValueError("max_input_characters must be bounded")
        if not 0 <= self.max_retries <= 3:
            raise ValueError("max_retries must be between 0 and 3")
        if self.temperature != 0:
            raise ValueError("V7 requires temperature=0")
        if self.reasoning_effort not in {None, "minimal", "low"}:
            raise ValueError("reasoning_effort must be minimal, low, or omitted")
        if self.privacy_mode not in {"strict", "standard", "off"}:
            raise ValueError("Unsupported privacy mode")

    @classmethod
    def from_env(cls):
        enabled = os.getenv("CHAINSHERLOCK_AI_ENABLED", "").casefold() in {
            "1", "true", "yes",
        }
        return cls(
            enabled=enabled,
            provider=os.getenv("CHAINSHERLOCK_AI_PROVIDER", "fallback"),
            model=os.getenv("CHAINSHERLOCK_AI_MODEL", "deterministic-v1"),
            api_key=os.getenv("CHAINSHERLOCK_AI_API_KEY") or None,
            base_url=os.getenv(
                "CHAINSHERLOCK_AI_BASE_URL", "https://api.openai.com/v1"
            ),
            timeout_seconds=int(
                os.getenv("CHAINSHERLOCK_AI_TIMEOUT_SECONDS", "120")
            ),
            max_output_tokens=int(
                os.getenv("CHAINSHERLOCK_AI_MAX_TOKENS", "3500")
            ),
            temperature=float(
                os.getenv("CHAINSHERLOCK_AI_TEMPERATURE", "0")
            ),
            reasoning_effort=(
                os.getenv("CHAINSHERLOCK_AI_REASONING_EFFORT", "minimal")
                or None
            ),
        )

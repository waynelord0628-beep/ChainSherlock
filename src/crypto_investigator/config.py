from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from crypto_investigator.exceptions import ConfigurationError


class ProviderChainConfig(BaseModel):
    primary: str
    fallback: list[str] = Field(default_factory=list)


class ProvidersConfig(BaseModel):
    ethereum: ProviderChainConfig
    tron: ProviderChainConfig
    bitcoin: ProviderChainConfig


class AnalysisConfig(BaseModel):
    top_counterparties: int = 20
    graph_max_nodes: int = 50
    default_depth: int = 1
    timezone: str = "UTC"


class CacheConfig(BaseModel):
    enabled: bool = True
    ttl_seconds: int = 86400


class OutputConfig(BaseModel):
    directory: Path = Path("output")
    include_raw: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"


class Settings(BaseModel):
    providers: ProvidersConfig
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


AppConfig = Settings


def load_config(path: Path | str = Path("config/default.yaml")) -> Settings:
    config_path = Path(path)
    try:
        with config_path.open(encoding="utf-8") as config_file:
            return Settings.model_validate(yaml.safe_load(config_file))
    except (OSError, yaml.YAMLError, ValueError) as error:
        raise ConfigurationError(f"Unable to load configuration: {config_path}") from error

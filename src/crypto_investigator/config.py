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
    directory: Path = Path("data/cache")
    ttl_seconds: int = 86400


class OutputConfig(BaseModel):
    directory: Path = Path("output")
    include_raw: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"


class HttpConfig(BaseModel):
    connect_timeout_seconds: float = 10
    read_timeout_seconds: float = 30
    total_timeout_seconds: float = 60
    retries: int = 3


class PaginationConfig(BaseModel):
    max_pages: int = 100
    max_records: int = 100000
    page_size: int = 100


class Settings(BaseModel):
    providers: ProvidersConfig
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
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

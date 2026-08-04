from crypto_investigator.config import load_config


def test_load_default_config():
    config = load_config()
    assert config.providers.ethereum.primary == "etherscan"
    assert config.analysis.timezone == "UTC"


from datetime import UTC, datetime, timedelta
import json

from crypto_investigator.cache.file_cache import FileCache
from crypto_investigator.cache.keys import build_cache_key
from crypto_investigator.domain import Chain
from crypto_investigator.providers.models import ProviderCapability


def key(**changes):
    values = {
        "provider": "etherscan",
        "chain": Chain.ETHEREUM,
        "capability": ProviderCapability.ADDRESS_TRANSACTIONS,
        "identifier": "0xABC",
        "parameters": {"page_size": 100},
        "page": 1,
    }
    values.update(changes)
    return build_cache_key(**values)


def test_cache_miss(tmp_path):
    assert FileCache(tmp_path).get(key()) is None


def test_cache_hit(tmp_path):
    cache = FileCache(tmp_path)
    cache.set(key(), {"records": [1]})
    assert cache.get(key()) == {"records": [1]}


def test_cache_expiry(tmp_path):
    cache = FileCache(tmp_path)
    cache.set(key(), {"records": [1]})
    path = next(tmp_path.glob("*.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cache.get(key()) is None
    assert not path.exists()


def test_cache_refresh_forces_miss(tmp_path):
    cache = FileCache(tmp_path)
    cache.set(key(), {"records": [1]})
    assert cache.get_or_none(key(), refresh=True) is None


def test_cache_corrupt_recovery(tmp_path):
    cache = FileCache(tmp_path)
    path = cache._path(key())
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("{corrupt", encoding="utf-8")
    assert cache.get(key()) is None
    assert not path.exists()


def test_cache_clear(tmp_path):
    cache = FileCache(tmp_path)
    cache.set(key(page=1), 1)
    cache.set(key(page=2), 2)
    assert cache.clear() == 2
    assert list(tmp_path.glob("*.json")) == []


def test_cache_key_normalizes_ethereum_identifier():
    assert key(identifier="0xABC") == key(identifier="0xabc")


def test_cache_key_excludes_api_key():
    without_secret = key(parameters={"page_size": 100})
    with_secret = key(
        parameters={"page_size": 100, "apikey": "super-secret", "api_key": "other"}
    )
    assert with_secret == without_secret


def test_cache_key_changes_with_cursor():
    assert key(page="first") != key(page="second")

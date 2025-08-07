import time
from unittest.mock import Mock

from drift.clients.mixins.caching import CacheEntry, CacheMixin


class TestCacheClass(CacheMixin):
    def __init__(self, cache_ttl: int = 300) -> None:
        self.cache_ttl = cache_ttl
        super().__init__()


def test_should_expire_when_time_exceeds_expiration() -> None:
    current_time = time.time()

    entry = CacheEntry(value="test", expires_at=current_time + 10)
    assert not entry.is_expired()

    entry = CacheEntry(value="test", expires_at=current_time - 10)
    assert entry.is_expired()


def test_should_generate_consistent_keys_when_same_args_provided() -> None:
    instance = TestCacheClass()

    key1 = instance._make_cache_key("arg1", "arg2", kwarg1="value1")
    key2 = instance._make_cache_key("arg1", "arg2", kwarg1="value1")
    key3 = instance._make_cache_key("arg1", "arg3", kwarg1="value1")

    assert key1 == key2
    assert key1 != key3


def test_should_return_cached_value_when_cache_hit_occurs() -> None:
    instance = TestCacheClass(cache_ttl=60)
    mock_func = Mock(return_value="result")

    @instance.with_cache(ttl=60)
    def cached_func(arg1: str, arg2: str) -> str:
        return mock_func(arg1, arg2)

    result1 = cached_func("a", "b")
    result2 = cached_func("a", "b")

    assert result1 == "result"
    assert result2 == "result"
    assert mock_func.call_count == 1


def test_should_call_function_when_cache_miss_occurs() -> None:
    instance = TestCacheClass(cache_ttl=60)
    mock_func = Mock(return_value="result")

    @instance.with_cache(ttl=60)
    def cached_func(arg1: str) -> str:
        return mock_func(arg1)

    result1 = cached_func("a")
    result2 = cached_func("b")

    assert result1 == "result"
    assert result2 == "result"
    assert mock_func.call_count == 2


def test_should_refresh_cache_when_entry_expires() -> None:
    instance = TestCacheClass(cache_ttl=1)
    mock_func = Mock(side_effect=["result1", "result2"])

    @instance.with_cache(ttl=0.01)
    def cached_func() -> str:
        return mock_func()

    result1 = cached_func()
    time.sleep(0.02)
    result2 = cached_func()

    assert result1 == "result1"
    assert result2 == "result2"
    assert mock_func.call_count == 2


def test_should_not_cache_when_ttl_is_zero() -> None:
    instance = TestCacheClass(cache_ttl=0)
    mock_func = Mock(return_value="result")

    @instance.with_cache()
    def cached_func() -> str:
        return mock_func()

    result1 = cached_func()
    result2 = cached_func()

    assert result1 == "result"
    assert result2 == "result"
    assert mock_func.call_count == 2


def test_should_include_prefix_when_key_prefix_is_specified() -> None:
    instance = TestCacheClass(cache_ttl=60)

    @instance.with_cache(ttl=60, key_prefix="test_prefix:")
    def cached_func(arg: str) -> str:
        return f"result_{arg}"

    result = cached_func("value")

    assert result == "result_value"
    assert any("test_prefix:" in key for key in instance._cache.keys())


def test_should_clear_all_entries_when_clear_cache_called() -> None:
    instance = TestCacheClass()

    instance._cache["key1"] = CacheEntry(value="value1", expires_at=time.time() + 60)
    instance._cache["key2"] = CacheEntry(value="value2", expires_at=time.time() + 60)
    instance._cache["key3"] = CacheEntry(value="value3", expires_at=time.time() + 60)

    instance.clear_cache()

    assert len(instance._cache) == 0


def test_should_clear_matching_entries_when_pattern_is_provided() -> None:
    instance = TestCacheClass()

    t = time.time()
    instance._cache["test_key1"] = CacheEntry(value="value1", expires_at=t + 60)
    instance._cache["test_key2"] = CacheEntry(value="value2", expires_at=t + 60)
    instance._cache["other_key"] = CacheEntry(value="value3", expires_at=t + 60)

    instance.clear_cache("test")

    assert "test_key1" not in instance._cache
    assert "test_key2" not in instance._cache
    assert "other_key" in instance._cache


def test_should_remove_expired_entries_when_evict_expired_called() -> None:
    instance = TestCacheClass()
    current_time = time.time()

    instance._cache["expired1"] = CacheEntry(
        value="value1", expires_at=current_time - 10
    )
    instance._cache["expired2"] = CacheEntry(
        value="value2", expires_at=current_time - 5
    )
    instance._cache["valid"] = CacheEntry(value="value3", expires_at=current_time + 60)

    instance.evict_expired()

    assert "expired1" not in instance._cache
    assert "expired2" not in instance._cache
    assert "valid" in instance._cache


def test_should_return_cache_statistics_when_get_cache_stats_called() -> None:
    instance = TestCacheClass()
    current_time = time.time()

    instance._cache["expired"] = CacheEntry(
        value="value1", expires_at=current_time - 10
    )
    instance._cache["valid1"] = CacheEntry(value="value2", expires_at=current_time + 60)
    instance._cache["valid2"] = CacheEntry(
        value="value3", expires_at=current_time + 120
    )

    stats = instance.get_cache_stats()

    assert stats["total_entries"] == 3
    assert stats["expired_entries"] == 1
    assert stats["active_entries"] == 2
    assert len(stats["cache_keys"]) == 3
    assert "expired" in stats["cache_keys"]
    assert "valid1" in stats["cache_keys"]
    assert "valid2" in stats["cache_keys"]

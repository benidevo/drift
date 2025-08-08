import time
from unittest.mock import Mock

from drift.clients.mixins.caching import CacheMixin


class TestCacheClass(CacheMixin):
    def __init__(self, cache_ttl: int = 300, cache_max_size: int = 500) -> None:
        self.cache_ttl = cache_ttl
        self.cache_max_size = cache_max_size
        super().__init__()


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

    instance._cache = type(instance._cache)(maxsize=500, ttl=0.01)

    @instance.with_cache()
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


def test_should_clear_all_entries_when_clear_cache_called() -> None:
    instance = TestCacheClass()

    instance._cache["key1"] = "value1"
    instance._cache["key2"] = "value2"
    instance._cache["key3"] = "value3"

    instance.clear_cache()

    assert len(instance._cache) == 0


def test_should_clear_matching_entries_when_pattern_is_provided() -> None:
    instance = TestCacheClass()

    instance._cache["test_key1"] = "value1"
    instance._cache["test_key2"] = "value2"
    instance._cache["other_key"] = "value3"

    instance.clear_cache("test")

    assert "test_key1" not in instance._cache
    assert "test_key2" not in instance._cache
    assert "other_key" in instance._cache

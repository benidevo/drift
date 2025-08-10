import pytest

from drift.clients.mixins.pagination import PaginationMixin


class PaginationTestHelper(PaginationMixin):
    def __init__(self) -> None:
        super().__init__()


def test_should_return_single_page_when_no_more_pages_exist() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        if page == 1:
            return ["item1", "item2", "item3"], False
        return [], False

    results = list(instance.paginate(fetch_func))

    assert results == ["item1", "item2", "item3"]


def test_should_iterate_all_pages_when_multiple_pages_exist() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        if page == 1:
            return ["item1", "item2"], True
        elif page == 2:
            return ["item3", "item4"], True
        elif page == 3:
            return ["item5"], False
        return [], False

    results = list(instance.paginate(fetch_func))

    assert results == ["item1", "item2", "item3", "item4", "item5"]


def test_should_stop_at_max_pages_when_limit_is_set() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        return [f"item{page}"], True

    results = list(instance.paginate(fetch_func, max_pages=3))

    assert results == ["item1", "item2", "item3"]


def test_should_raise_exception_when_fetch_function_fails() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        if page == 2:
            raise ValueError("Fetch error")
        return ["item1"], True

    with pytest.raises(ValueError, match="Fetch error"):
        list(instance.paginate(fetch_func))


def test_should_collect_all_pages_when_collect_paginated_called() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        if page == 1:
            return ["item1", "item2"], True
        elif page == 2:
            return ["item3"], False
        return [], False

    results = instance.collect_paginated(fetch_func)

    assert results == ["item1", "item2", "item3"]


def test_should_limit_items_when_max_items_is_specified() -> None:
    instance = PaginationTestHelper()

    def fetch_func(page: int) -> tuple[list[str], bool]:
        return [f"item{i}" for i in range(page * 3 - 2, page * 3 + 1)], True

    results = instance.collect_paginated(fetch_func, max_items=5)

    assert len(results) == 5
    assert results == ["item1", "item2", "item3", "item4", "item5"]


def test_should_paginate_github_list_when_paginate_github_called() -> None:
    instance = PaginationTestHelper()

    mock_paginated_list = ["item1", "item2", "item3", "item4", "item5"]

    results = list(instance.paginate_github(mock_paginated_list))

    assert results == mock_paginated_list


def test_should_limit_github_items_when_max_items_is_set() -> None:
    instance = PaginationTestHelper()

    mock_paginated_list = ["item1", "item2", "item3", "item4", "item5"]

    results = list(instance.paginate_github(mock_paginated_list, max_items=3))

    assert results == ["item1", "item2", "item3"]


def test_should_paginate_gitlab_generator_when_paginate_gitlab_called() -> None:
    instance = PaginationTestHelper()

    def mock_generator():
        yield "item1"
        yield "item2"
        yield "item3"

    results = list(instance.paginate_gitlab(mock_generator()))

    assert results == ["item1", "item2", "item3"]


def test_should_limit_gitlab_items_when_max_items_is_set() -> None:
    instance = PaginationTestHelper()

    def mock_generator():
        for i in range(1, 11):
            yield f"item{i}"

    results = list(instance.paginate_gitlab(mock_generator(), max_items=5))

    assert len(results) == 5
    assert results == ["item1", "item2", "item3", "item4", "item5"]

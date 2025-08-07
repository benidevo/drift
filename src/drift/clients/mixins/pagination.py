from collections.abc import Callable, Generator
from typing import Any, TypeVar

from drift.logger import get_logger


T = TypeVar("T")


class PaginationMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pagination_logger = get_logger(
            f"{self.__class__.__name__}.PaginationMixin"
        )

    def paginate(
        self,
        fetch_func: Callable[[int], tuple[list[T], bool]],
        page_size: int = 100,
        max_pages: int | None = None,
    ) -> Generator[T, None, None]:
        page = 1
        total_items = 0

        while max_pages is None or page <= max_pages:
            self._pagination_logger.debug(f"Fetching page {page} (size={page_size})")

            try:
                items, has_more = fetch_func(page)
            except Exception as e:
                self._pagination_logger.error(f"Error fetching page {page}: {e}")
                raise

            for item in items:
                yield item
                total_items += 1

            self._pagination_logger.debug(
                f"Page {page} returned {len(items)} items (total: {total_items})"
            )

            if not has_more:
                self._pagination_logger.info(
                    f"Pagination complete. Total items: {total_items}"
                )
                break

            page += 1

    def collect_paginated(
        self,
        fetch_func: Callable[[int], tuple[list[T], bool]],
        page_size: int = 100,
        max_items: int | None = None,
    ) -> list[T]:
        results: list[T] = []

        for item in self.paginate(fetch_func, page_size):
            results.append(item)
            if max_items is not None and len(results) >= max_items:
                self._pagination_logger.info(f"Reached max_items limit ({max_items})")
                break

        return results

    def paginate_github(
        self, paginated_list: Any, max_items: int | None = None
    ) -> Generator[Any, None, None]:
        count = 0
        for item in paginated_list:
            yield item
            count += 1
            if max_items is not None and count >= max_items:
                self._pagination_logger.info(f"Reached max_items limit ({max_items})")
                break

    def paginate_gitlab(
        self, generator: Generator[Any, None, None], max_items: int | None = None
    ) -> Generator[Any, None, None]:
        count = 0
        for item in generator:
            yield item
            count += 1
            if max_items is not None and count >= max_items:
                self._pagination_logger.info(f"Reached max_items limit ({max_items})")
                break

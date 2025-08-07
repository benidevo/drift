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
        """
        Generic pagination helper.

        Args:
            fetch_func: Function that takes page number and returns (items, has_more)
            page_size: Number of items per page
            max_pages: Maximum number of pages to fetch (None for all)

        Yields:
            Individual items from all pages
        """
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
        """
        Collect all paginated results into a list.

        Args:
            fetch_func: Function that takes page number and returns (items, has_more)
            page_size: Number of items per page
            max_items: Maximum total items to collect (None for all)

        Returns:
            List of all collected items
        """
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
        """
        Paginate through a PyGithub PaginatedList.

        Args:
            paginated_list: PyGithub PaginatedList object
            max_items: Maximum items to yield

        Yields:
            Individual items from the paginated list
        """
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
        """
        Paginate through a python-gitlab generator.

        Args:
            generator: python-gitlab generator
            max_items: Maximum items to yield

        Yields:
            Individual items from the generator
        """
        count = 0
        for item in generator:
            yield item
            count += 1
            if max_items is not None and count >= max_items:
                self._pagination_logger.info(f"Reached max_items limit ({max_items})")
                break

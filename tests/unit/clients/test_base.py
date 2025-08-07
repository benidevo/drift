from unittest.mock import Mock, patch

import pytest

from drift.clients.base import BaseGitClient


class ConcreteGitClient(BaseGitClient):
    def _load_repository(self) -> Mock:
        return Mock(name="repository")

    def get_pr_info(self, pr_id: str) -> dict:
        return {"id": pr_id}

    def get_diff_data(self, pr_id: str) -> dict:
        return {"pr_id": pr_id}

    def get_commit_messages(self, pr_id: str) -> list[str]:
        return ["commit message"]

    def get_pr_context(self, pr_id: str) -> dict[str, str]:
        return {"context": "test"}

    def get_existing_comments(self, pr_id: str) -> list:
        return []

    def post_comment(self, pr_id: str, comment: str) -> None:
        pass

    def update_comment(self, pr_id: str, comment_id: str, comment: str) -> None:
        pass


def test_should_initialize_base_client_when_parameters_are_provided() -> None:
    mock_client = Mock()
    client = ConcreteGitClient(
        client=mock_client,
        repo_identifier="owner/repo",
        cache_ttl=600,
        max_retries=5,
        backoff_factor=2.0,
    )

    assert client.client == mock_client
    assert client.repo_identifier == "owner/repo"
    assert client.cache_ttl == 600
    assert client.max_retries == 5
    assert client.backoff_factor == 2.0
    assert client._repo is None


def test_should_lazy_load_repository_when_accessed() -> None:
    client = ConcreteGitClient(client=Mock(), repo_identifier="owner/repo")

    assert client._repo is None

    repo = client.repo
    assert repo is not None
    assert client._repo is not None

    repo2 = client.repo
    assert repo is repo2


def test_should_retry_and_succeed_when_function_fails_then_works() -> None:
    client = ConcreteGitClient(
        client=Mock(),
        repo_identifier="owner/repo",
        max_retries=3,
        backoff_factor=0.01,
    )

    mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
    wrapped = client._with_retry(mock_func)

    with patch("drift.clients.base.sleep") as mock_sleep:
        result = wrapped()

    assert result == "success"
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2


def test_should_raise_exception_when_all_retry_attempts_fail() -> None:
    client = ConcreteGitClient(
        client=Mock(),
        repo_identifier="owner/repo",
        max_retries=3,
        backoff_factor=0.01,
    )

    mock_func = Mock(side_effect=Exception("persistent failure"))
    wrapped = client._with_retry(mock_func)

    with patch("drift.clients.base.sleep"):
        with pytest.raises(Exception, match="persistent failure"):
            wrapped()

    assert mock_func.call_count == 3


def test_should_use_custom_max_retries_when_specified() -> None:
    client = ConcreteGitClient(
        client=Mock(),
        repo_identifier="owner/repo",
        max_retries=3,
        backoff_factor=0.01,
    )

    mock_func = Mock(side_effect=Exception("failure"))
    wrapped = client._with_retry(mock_func, max_retries=2)

    with patch("drift.clients.base.sleep"):
        with pytest.raises(Exception, match="failure"):
            wrapped()

    assert mock_func.call_count == 2

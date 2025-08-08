from unittest.mock import Mock, patch

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
    from drift.exceptions import NetworkError

    client = ConcreteGitClient(
        client=Mock(),
        repo_identifier="owner/repo",
        max_retries=3,
        backoff_factor=0.01,
    )

    mock_func = Mock(
        side_effect=[NetworkError("fail"), NetworkError("fail"), "success"]
    )
    wrapped = client.with_retry(mock_func)

    with patch("time.sleep") as mock_sleep:
        result = wrapped()

    assert result == "success"
    assert mock_func.call_count == 3
    assert mock_sleep.call_count == 2

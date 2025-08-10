from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from drift.clients.github_client import GitHubClient
from drift.exceptions import AuthenticationError, ResourceNotFoundError
from drift.models import Comment, DiffData, FileStatus, PullRequestInfo


@pytest.fixture
def mock_github():
    with patch("drift.clients.github_client.Github") as mock:
        yield mock


@pytest.fixture
def mock_auth():
    with patch("drift.clients.github_client.Auth") as mock:
        yield mock


@pytest.fixture
def github_client(mock_github, mock_auth):
    mock_auth.Token.return_value = Mock()
    return GitHubClient(token="fake_token", repo_identifier="owner/repo")


@pytest.fixture
def mock_pr():
    pr = MagicMock()
    pr.number = 123
    pr.title = "Test PR"
    pr.body = "Test description"
    pr.user.login = "testuser"
    pr.head.ref = "feature-branch"
    pr.base.ref = "main"
    pr.state = "open"
    pr.merged = False
    pr.created_at = datetime(2024, 1, 1, 12, 0, 0)
    pr.updated_at = datetime(2024, 1, 2, 12, 0, 0)
    pr.additions = 100
    pr.deletions = 50
    pr.changed_files = 5
    pr.commits = 3
    pr.mergeable = True
    pr.labels = []
    pr.assignees = []
    pr.requested_reviewers = []
    pr.milestone = None
    pr.closed_at = None
    pr.merged_at = None
    return pr


def test_should_initialize_github_client_with_valid_config(mock_github, mock_auth):
    mock_auth.Token.return_value = Mock()
    client = GitHubClient(
        token="token",
        repo_identifier="owner/repo",
        cache_ttl=600,
        cache_maxsize=1000,
        max_retries=5,
    )

    assert client.repo_identifier == "owner/repo"
    assert client.cache_ttl == 600
    assert client.max_retries == 5
    assert client._cache.maxsize == 1000
    mock_github.assert_called_once()


def test_should_handle_authentication_error_when_loading_repository(github_client):
    github_client.client.get_repo.side_effect = Exception("401 Unauthorized")

    with pytest.raises(AuthenticationError):
        _ = github_client.repo


def test_should_get_pr_info_successfully(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    pr_info = github_client.get_pr_info("123")

    assert isinstance(pr_info, PullRequestInfo)
    assert pr_info.id == "123"
    assert pr_info.title == "Test PR"
    assert pr_info.author_username == "testuser"


def test_should_use_cache_on_repeated_calls(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    pr_info1 = github_client.get_pr_info("123")
    pr_info2 = github_client.get_pr_info("123")

    assert pr_info1 == pr_info2
    github_client.repo.get_pull.assert_called_once()


def test_should_get_diff_data_with_files(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    mock_file = MagicMock()
    mock_file.filename = "test.py"
    mock_file.status = "modified"
    mock_file.additions = 10
    mock_file.deletions = 5
    mock_file.patch = "@@ -1,3 +1,3 @@\n-old\n+new"
    mock_file.previous_filename = None

    mock_pr.get_files.return_value.__iter__ = Mock(return_value=iter([mock_file]))

    diff_data = github_client.get_diff_data("123")

    assert isinstance(diff_data, DiffData)
    assert len(diff_data.files) == 1
    assert diff_data.files[0].status == FileStatus.MODIFIED
    assert diff_data.total_additions == 100
    assert diff_data.total_deletions == 50


def test_should_get_commit_messages(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    mock_commit = MagicMock()
    mock_commit.commit.message = "Test commit"
    mock_pr.get_commits.return_value.__iter__ = Mock(return_value=iter([mock_commit]))

    messages = github_client.get_commit_messages("123")

    assert messages == ["Test commit"]


def test_should_get_pr_context_with_all_fields(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    context = github_client.get_pr_context("123")

    assert context["title"] == "Test PR"
    assert context["author"] == "testuser"
    assert context["state"] == "open"
    assert context["merged"] == "False"
    assert "additions" in context
    assert "deletions" in context


def test_should_get_and_post_comments(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    mock_comment = MagicMock()
    mock_comment.id = 1
    mock_comment.user.login = "user"
    mock_comment.body = "comment"
    mock_comment.created_at = datetime.now()
    mock_comment.updated_at = None

    mock_pr.get_issue_comments.return_value.__iter__ = Mock(
        return_value=iter([mock_comment])
    )
    mock_pr.get_comments.return_value.__iter__ = Mock(return_value=iter([]))

    comments = github_client.get_existing_comments("123")
    assert len(comments) == 1
    assert isinstance(comments[0], Comment)

    github_client.post_comment("123", "New comment")
    mock_pr.create_issue_comment.assert_called_once_with("New comment")


def test_should_handle_resource_not_found_errors(github_client):
    github_client._repo = Mock()
    github_client.repo.get_pull.side_effect = Exception("404")

    with pytest.raises(ResourceNotFoundError):
        github_client.get_pr_info("999")


def test_should_validate_input_and_prevent_injection(github_client):
    github_client._repo = Mock()

    with pytest.raises(ResourceNotFoundError):
        github_client.get_pr_info("invalid")

    github_client.repo.get_pull.assert_not_called()


def test_should_limit_resources_to_prevent_exhaustion(github_client, mock_pr):
    github_client._repo = Mock()
    github_client.repo.get_pull.return_value = mock_pr

    many_files = [MagicMock() for _ in range(1500)]
    for i, f in enumerate(many_files):
        f.filename = f"file{i}.py"
        f.status = "added"
        f.additions = 1
        f.deletions = 0
        f.patch = "+"
        f.previous_filename = None

    mock_pr.get_files.return_value.__iter__ = Mock(return_value=iter(many_files))

    diff_data = github_client.get_diff_data("123")

    assert len(diff_data.files) == github_client.MAX_FILES_PER_PR

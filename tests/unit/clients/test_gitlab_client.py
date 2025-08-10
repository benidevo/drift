from unittest.mock import MagicMock, patch

import pytest

from drift.clients.gitlab_client import GitLabClient
from drift.exceptions import APIError, AuthenticationError, ResourceNotFoundError
from drift.models import Comment, DiffData, FileStatus, PullRequestInfo


@pytest.fixture
def mock_gitlab():
    with patch("drift.clients.gitlab_client.Gitlab") as mock:
        yield mock


@pytest.fixture
def gitlab_client(mock_gitlab):
    client = GitLabClient(token="fake_token", repo_identifier="owner/repo")
    return client


@pytest.fixture
def mock_mr():
    mr = MagicMock()
    mr.iid = 123
    mr.title = "Test MR"
    mr.description = "Test description"
    mr.author = {"username": "testuser"}
    mr.source_branch = "feature-branch"
    mr.target_branch = "main"
    mr.state = "opened"
    mr.created_at = "2024-01-01T12:00:00Z"
    mr.updated_at = "2024-01-02T12:00:00Z"
    mr.merge_status = "can_be_merged"
    mr.has_conflicts = False
    mr.work_in_progress = False
    mr.draft = False
    mr.mergeable = True
    mr.pipeline = {"status": "success"}
    mr.approvals_required = 2
    mr.approvals_left = 1
    mr.discussion_locked = False
    mr.assignee = None
    mr.milestone = None
    mr.labels = []
    return mr


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.mergerequests = MagicMock()
    return project


class TestGitLabClient:
    def test_should_initialize_with_valid_config(self, mock_gitlab):
        client = GitLabClient(
            token="test_token",
            repo_identifier="namespace/project",
            base_url="https://gitlab.example.com",
            cache_ttl=600,
            max_retries=5,
        )

        assert client.repo_identifier == "namespace/project"
        assert client.cache_ttl == 600
        assert client.max_retries == 5
        mock_gitlab.assert_called_once_with(
            url="https://gitlab.example.com",
            private_token="test_token",
            per_page=100,
            timeout=30,
        )

    def test_should_validate_repo_identifier_with_namespace_format(self):
        GitLabClient._validate_repo_identifier("namespace/project")
        GitLabClient._validate_repo_identifier("group/subgroup/project")

        with pytest.raises(ValueError, match="Invalid repository identifier format"):
            GitLabClient._validate_repo_identifier("invalid")

    def test_should_validate_repo_identifier_with_numeric_id(self):
        GitLabClient._validate_repo_identifier("12345")
        GitLabClient._validate_repo_identifier("1")

        with pytest.raises(ValueError, match="Invalid project ID range"):
            GitLabClient._validate_repo_identifier("2147483648")

    def test_should_validate_repo_identifier_with_invalid_characters(self):
        with pytest.raises(ValueError, match="Invalid characters"):
            GitLabClient._validate_repo_identifier("namespace/project@123")

    def test_should_validate_repo_identifier_with_length_limits(self):
        long_path = "a" * 256
        with pytest.raises(ValueError, match="Repository identifier too long"):
            GitLabClient._validate_repo_identifier(long_path)

    def test_should_load_repository_successfully(self, gitlab_client, mock_gitlab):
        mock_project = MagicMock()
        gitlab_client.client.projects.get.return_value = mock_project

        result = gitlab_client._load_repository()

        assert result == mock_project
        gitlab_client.client.auth.assert_called_once()
        gitlab_client.client.projects.get.assert_called_once_with("owner/repo")

    def test_should_raise_authentication_error_on_401(self, gitlab_client):
        gitlab_client.client.auth.side_effect = Exception("401 Unauthorized")

        with pytest.raises(AuthenticationError):
            gitlab_client._load_repository()

    def test_should_raise_resource_not_found_on_404(self, gitlab_client):
        gitlab_client.client.auth.return_value = None
        gitlab_client.client.projects.get.side_effect = Exception("404 Not Found")

        with pytest.raises(ResourceNotFoundError):
            gitlab_client._load_repository()

    def test_should_get_pr_info_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        result = gitlab_client.get_pr_info("123")

        assert isinstance(result, PullRequestInfo)
        assert result.id == "123"
        assert result.title == "Test MR"
        assert result.author_username == "testuser"
        mock_project.mergerequests.get.assert_called_once_with(123)

    def test_should_cache_pr_info(self, gitlab_client, mock_mr, mock_project):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        result1 = gitlab_client.get_pr_info("123")
        result2 = gitlab_client.get_pr_info("123")

        assert result1 == result2
        mock_project.mergerequests.get.assert_called_once()

    def test_should_get_diff_data_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_changes = {
            "changes": [
                {
                    "old_path": "file1.py",
                    "new_path": "file1.py",
                    "new_file": False,
                    "deleted_file": False,
                    "renamed_file": False,
                    "diff": (
                        "@@ -1,3 +1,4 @@\n def hello():\n-    pass\n"
                        "+    print('hello')\n+    return 'hello'"
                    ),
                }
            ]
        }
        mock_mr.changes.return_value = mock_changes

        result = gitlab_client.get_diff_data("123")

        assert isinstance(result, DiffData)
        assert len(result.files) == 1
        assert result.files[0].path == "file1.py"
        assert result.files[0].status == FileStatus.MODIFIED
        mock_mr.changes.assert_called_once()

    def test_should_limit_files_in_diff_data(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        changes = []
        for i in range(GitLabClient.MAX_FILES_PER_MR + 100):
            changes.append(
                {
                    "old_path": f"file{i}.py",
                    "new_path": f"file{i}.py",
                    "new_file": False,
                    "deleted_file": False,
                    "renamed_file": False,
                    "diff": "some diff",
                }
            )

        mock_mr.changes.return_value = {"changes": changes}

        result = gitlab_client.get_diff_data("123")

        assert len(result.files) == GitLabClient.MAX_FILES_PER_MR

    def test_should_get_commit_messages_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_commits = [
            MagicMock(message="feat: add feature"),
            MagicMock(message="fix: bug fix"),
            MagicMock(message="docs: update readme"),
        ]
        mock_mr.commits.return_value = mock_commits

        result = gitlab_client.get_commit_messages("123")

        assert len(result) == 3
        assert result[0] == "feat: add feature"
        assert result[1] == "fix: bug fix"
        assert result[2] == "docs: update readme"

    def test_should_limit_commit_messages(self, gitlab_client, mock_mr, mock_project):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_commits = []
        for i in range(GitLabClient.MAX_COMMITS_PER_MR + 100):
            mock_commits.append(MagicMock(message=f"commit {i}"))

        mock_mr.commits.return_value = mock_commits

        result = gitlab_client.get_commit_messages("123")

        assert len(result) == GitLabClient.MAX_COMMITS_PER_MR

    def test_should_get_pr_context_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        result = gitlab_client.get_pr_context("123")

        assert isinstance(result, dict)
        assert result["merge_status"] == "can_be_merged"
        assert result["has_conflicts"] == "False"
        assert result["work_in_progress"] == "False"
        assert result["pipeline_status"] == "success"

    def test_should_get_existing_comments_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_notes = [
            MagicMock(
                id=1,
                author={"username": "user1"},
                body="First comment",
                created_at="2024-01-01T10:00:00Z",
                updated_at="2024-01-01T11:00:00Z",
            ),
            MagicMock(
                id=2,
                author={"username": "user2"},
                body="Second comment with drift",
                created_at="2024-01-01T12:00:00Z",
                updated_at=None,
            ),
        ]
        mock_mr.notes.list.side_effect = (
            lambda **kwargs: mock_notes if kwargs.get("page", 1) == 1 else []
        )
        mock_mr.discussions.list.side_effect = lambda **kwargs: []

        result = gitlab_client.get_existing_comments("123")

        assert len(result) == 2
        assert isinstance(result[0], Comment)
        assert result[0].author_username == "user1"
        assert result[0].body == "First comment"
        assert result[1].is_drift_comment is True

    def test_should_get_discussion_comments(self, gitlab_client, mock_mr, mock_project):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_mr.notes.list.side_effect = lambda **kwargs: []

        mock_discussion = MagicMock()
        mock_discussion.attributes = {
            "notes": [
                {
                    "id": 3,
                    "author": {"username": "user3"},
                    "body": "Diff comment",
                    "created_at": "2024-01-01T13:00:00Z",
                    "updated_at": None,
                    "position": {
                        "new_path": "file.py",
                        "old_path": "file.py",
                        "new_line": 10,
                        "old_line": None,
                    },
                }
            ]
        }

        mock_mr.discussions.list.side_effect = (
            lambda **kwargs: [mock_discussion] if kwargs.get("page", 1) == 1 else []
        )

        result = gitlab_client.get_existing_comments("123")

        assert len(result) == 1
        assert result[0].file_path == "file.py"
        assert result[0].line_from == 10
        assert result[0].line_to == 10

    def test_should_post_comment_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        gitlab_client.post_comment("123", "Test comment")

        mock_mr.notes.create.assert_called_once_with({"body": "Test comment"})

    def test_should_validate_empty_comment(self, gitlab_client):
        with pytest.raises(ValueError, match="Comment cannot be empty"):
            gitlab_client.post_comment("123", "")

        with pytest.raises(ValueError, match="Comment cannot be empty"):
            gitlab_client.post_comment("123", "   ")

    def test_should_validate_long_comment(self, gitlab_client):
        long_comment = "a" * 65537
        with pytest.raises(ValueError, match="Comment is too long"):
            gitlab_client.post_comment("123", long_comment)

    def test_should_update_comment_successfully(
        self, gitlab_client, mock_mr, mock_project
    ):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.return_value = mock_mr

        mock_note = MagicMock()
        mock_mr.notes.get.return_value = mock_note

        gitlab_client.update_comment("123", "456", "Updated comment")

        assert mock_note.body == "Updated comment"
        mock_note.save.assert_called_once()

    def test_should_raise_error_for_invalid_mr_id(self, gitlab_client):
        with pytest.raises(ResourceNotFoundError, match="Invalid MR ID"):
            gitlab_client.get_pr_info("invalid")

        with pytest.raises(ResourceNotFoundError, match="MR ID out of valid range"):
            gitlab_client.get_pr_info("2147483648")

    def test_should_sanitize_error_messages(self, gitlab_client):
        error = Exception("Error with token=secret123 and api_key=key456")
        sanitized = gitlab_client._sanitize_error_message(error, "Test context")

        assert "secret123" not in sanitized
        assert "key456" not in sanitized
        assert "[REDACTED]" in sanitized
        assert "Test context" in sanitized

    def test_should_handle_api_errors(self, gitlab_client, mock_project):
        gitlab_client._repo = mock_project
        mock_project.mergerequests.get.side_effect = Exception("API error")

        with pytest.raises(APIError) as exc_info:
            gitlab_client.get_pr_info("123")

        assert "Failed to get MR info" in str(exc_info.value)

from datetime import datetime
from unittest.mock import MagicMock

from drift.adapters.github_mapper import GitHubMapper
from drift.models import FileStatus


def test_to_pull_request_info():
    spec = [
        "number",
        "title",
        "body",
        "user",
        "head",
        "base",
        "state",
        "merged",
        "created_at",
        "updated_at",
    ]
    mock_pr = MagicMock(spec=spec)
    mock_pr.number = 123
    mock_pr.title = "Add new feature"
    mock_pr.body = "This PR adds a new feature"
    mock_pr.user.login = "testuser"
    mock_pr.head.ref = "feature-branch"
    mock_pr.base.ref = "main"
    mock_pr.state = "open"
    mock_pr.merged = False
    mock_pr.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_pr.updated_at = datetime(2023, 1, 2, 12, 0, 0)

    result = GitHubMapper.to_pull_request_info(mock_pr)

    assert result.id == "123"
    assert result.title == "Add new feature"
    assert result.description == "This PR adds a new feature"
    assert result.author_username == "testuser"
    assert result.source_branch == "feature-branch"
    assert result.target_branch == "main"
    assert result.state == "open"
    assert result.is_merged is False
    assert result.created_at == "2023-01-01T12:00:00"
    assert result.updated_at == "2023-01-02T12:00:00"


def test_to_pull_request_info_merged():
    spec = [
        "number",
        "title",
        "body",
        "user",
        "head",
        "base",
        "state",
        "merged",
        "created_at",
        "updated_at",
    ]
    mock_pr = MagicMock(spec=spec)
    mock_pr.number = 456
    mock_pr.title = "Fix bug"
    mock_pr.body = None
    mock_pr.user.login = "bugfixer"
    mock_pr.head.ref = "bugfix"
    mock_pr.base.ref = "main"
    mock_pr.state = "closed"
    mock_pr.merged = True
    mock_pr.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_pr.updated_at = None

    result = GitHubMapper.to_pull_request_info(mock_pr)

    assert result.id == "456"
    assert result.description == ""
    assert result.state == "merged"
    assert result.is_merged is True
    assert result.updated_at == "2023-01-01T12:00:00"


def test_to_file_change_added():
    spec = ["filename", "status", "additions", "deletions", "patch"]
    mock_file = MagicMock(spec=spec)
    mock_file.filename = "src/new_file.py"
    mock_file.status = "added"
    mock_file.additions = 100
    mock_file.deletions = 0
    mock_file.patch = "@@ -0,0 +1,100 @@\n+new content"

    result = GitHubMapper.to_file_change(mock_file)

    assert result.path == "src/new_file.py"
    assert result.old_path is None
    assert result.status == FileStatus.ADDED
    assert result.additions == 100
    assert result.deletions == 0
    assert result.patch == "@@ -0,0 +1,100 @@\n+new content"


def test_to_file_change_deleted():
    spec = ["filename", "status", "additions", "deletions", "patch"]
    mock_file = MagicMock(spec=spec)
    mock_file.filename = "src/old_file.py"
    mock_file.status = "removed"
    mock_file.additions = 0
    mock_file.deletions = 50
    mock_file.patch = "@@ -1,50 +0,0 @@\n-old content"

    result = GitHubMapper.to_file_change(mock_file)

    assert result.status == FileStatus.DELETED


def test_to_file_change_renamed():
    spec = [
        "filename",
        "status",
        "additions",
        "deletions",
        "patch",
        "previous_filename",
    ]
    mock_file = MagicMock(spec=spec)
    mock_file.filename = "src/new_name.py"
    mock_file.previous_filename = "src/old_name.py"
    mock_file.status = "renamed"
    mock_file.additions = 5
    mock_file.deletions = 3
    mock_file.patch = None

    result = GitHubMapper.to_file_change(mock_file)

    assert result.path == "src/new_name.py"
    assert result.old_path == "src/old_name.py"
    assert result.status == FileStatus.RENAMED
    assert result.patch == ""


def test_to_file_change_unknown_status():
    spec = ["filename", "status", "additions", "deletions", "patch"]
    mock_file = MagicMock(spec=spec)
    mock_file.filename = "src/file.py"
    mock_file.status = "unknown_status"
    mock_file.additions = 10
    mock_file.deletions = 5
    mock_file.patch = "diff content"

    result = GitHubMapper.to_file_change(mock_file)

    assert result.status == FileStatus.MODIFIED


def test_to_comment_from_issue_comment():
    spec = ["id", "user", "body", "created_at", "updated_at"]
    mock_comment = MagicMock(spec=spec)
    mock_comment.id = 12345
    mock_comment.user.login = "reviewer"
    mock_comment.body = "This looks good! 🌊"
    mock_comment.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_comment.updated_at = datetime(2023, 1, 2, 12, 0, 0)

    result = GitHubMapper.to_comment_from_issue_comment(mock_comment)

    assert result.id == "12345"
    assert result.author_username == "reviewer"
    assert result.body == "This looks good! 🌊"
    assert result.created_at == "2023-01-01T12:00:00"
    assert result.updated_at == "2023-01-02T12:00:00"
    assert result.is_drift_comment is True
    assert result.file_path is None
    assert result.line_from is None
    assert result.line_to is None


def test_to_comment_from_review_comment():
    spec = [
        "id",
        "user",
        "body",
        "created_at",
        "updated_at",
        "path",
        "original_line",
        "line",
    ]
    mock_comment = MagicMock(spec=spec)
    mock_comment.id = 54321
    mock_comment.user.login = "reviewer"
    mock_comment.body = "This could be improved"
    mock_comment.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_comment.updated_at = datetime(2023, 1, 2, 12, 0, 0)
    mock_comment.path = "src/main.py"
    mock_comment.original_line = 10
    mock_comment.line = 15

    result = GitHubMapper.to_comment_from_review_comment(mock_comment)

    assert result.id == "54321"
    assert result.file_path == "src/main.py"
    assert result.line_from == 10
    assert result.line_to == 15
    assert result.is_drift_comment is False


def test_to_comment_from_review_comment_no_original_line():
    spec = [
        "id",
        "user",
        "body",
        "created_at",
        "updated_at",
        "path",
        "original_line",
        "line",
    ]
    mock_comment = MagicMock(spec=spec)
    mock_comment.id = 99999
    mock_comment.user.login = "reviewer"
    mock_comment.body = "Fix this"
    mock_comment.created_at = datetime(2023, 1, 1, 12, 0, 0)
    mock_comment.updated_at = None
    mock_comment.path = "src/utils.py"
    mock_comment.original_line = None
    mock_comment.line = 20

    result = GitHubMapper.to_comment_from_review_comment(mock_comment)

    assert result.line_from == 20
    assert result.line_to == 20

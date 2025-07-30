import pytest

from drift.adapters.gitlab_mapper import GitLabMapper
from drift.models import FileStatus


def test_should_map_merge_request_when_mr_is_open():
    mr_data = {
        "iid": 123,
        "title": "Add new feature",
        "description": "This MR adds a new feature",
        "author": {"username": "testuser"},
        "source_branch": "feature-branch",
        "target_branch": "main",
        "state": "opened",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
    }

    result = GitLabMapper.to_pull_request_info(mr_data)

    assert result.id == "123"
    assert result.title == "Add new feature"
    assert result.description == "This MR adds a new feature"
    assert result.author_username == "testuser"
    assert result.source_branch == "feature-branch"
    assert result.target_branch == "main"
    assert result.state == "opened"
    assert result.is_merged is False
    assert result.created_at == "2023-01-01T12:00:00Z"
    assert result.updated_at == "2023-01-02T12:00:00Z"


def test_should_map_merge_request_when_mr_is_merged():
    mr_data = {
        "iid": 456,
        "title": "Fix bug",
        "description": None,
        "author": {"username": "bugfixer"},
        "source_branch": "bugfix",
        "target_branch": "main",
        "state": "merged",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
    }

    result = GitLabMapper.to_pull_request_info(mr_data)

    assert result.id == "456"
    assert result.description == ""
    assert result.state == "merged"
    assert result.is_merged is True


def test_should_map_file_change_when_file_is_new():
    change_data = {
        "old_path": "src/new_file.py",
        "new_path": "src/new_file.py",
        "new_file": True,
        "deleted_file": False,
        "renamed_file": False,
        "diff": "@@ -0,0 +1,100 @@\n+new content",
    }

    result = GitLabMapper.to_file_change(change_data)

    assert result.path == "src/new_file.py"
    assert result.old_path is None
    assert result.status == FileStatus.ADDED
    assert result.additions == 1
    assert result.deletions == 0
    assert result.patch == "@@ -0,0 +1,100 @@\n+new content"


def test_should_map_file_change_when_file_is_deleted():
    change_data = {
        "old_path": "src/old_file.py",
        "new_path": "src/old_file.py",
        "new_file": False,
        "deleted_file": True,
        "renamed_file": False,
        "diff": "@@ -1,50 +0,0 @@\n-old content\n-more content",
    }

    result = GitLabMapper.to_file_change(change_data)

    assert result.path == "src/old_file.py"
    assert result.old_path is None
    assert result.status == FileStatus.DELETED
    assert result.additions == 0
    assert result.deletions == 2  # Two lines deleted based on diff
    assert result.patch == "@@ -1,50 +0,0 @@\n-old content\n-more content"


def test_should_map_file_change_when_file_is_renamed():
    change_data = {
        "old_path": "src/old_name.py",
        "new_path": "src/new_name.py",
        "new_file": False,
        "deleted_file": False,
        "renamed_file": True,
        "diff": None,
    }

    result = GitLabMapper.to_file_change(change_data)

    assert result.path == "src/new_name.py"
    assert result.old_path == "src/old_name.py"
    assert result.status == FileStatus.RENAMED
    assert result.patch == ""


def test_should_map_file_change_when_file_is_modified():
    change_data = {
        "old_path": "src/file.py",
        "new_path": "src/file.py",
        "new_file": False,
        "deleted_file": False,
        "renamed_file": False,
        "diff": (
            "@@ -10,3 +10,4 @@\n def hello():\n"
            "-    print('old')\n+    print('new')\n+    return True"
        ),
    }

    result = GitLabMapper.to_file_change(change_data)

    assert result.path == "src/file.py"
    assert result.old_path is None
    assert result.status == FileStatus.MODIFIED
    assert result.additions == 2  # Two lines added
    assert result.deletions == 1  # One line deleted
    assert "@@ -10,3 +10,4 @@" in result.patch


def test_should_map_comment_when_note_contains_drift_marker():
    note_data = {
        "id": 12345,
        "author": {"username": "reviewer"},
        "body": "This looks good! 🌊",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
        "position": None,
    }

    result = GitLabMapper.to_comment(note_data)

    assert result.id == "12345"
    assert result.author_username == "reviewer"
    assert result.body == "This looks good! 🌊"
    assert result.created_at == "2023-01-01T12:00:00Z"
    assert result.updated_at == "2023-01-02T12:00:00Z"
    assert result.is_drift_comment is True
    assert result.file_path is None
    assert result.line_from is None
    assert result.line_to is None


def test_should_map_comment_when_note_has_new_line_position():
    note_data = {
        "id": 54321,
        "author": {"username": "reviewer"},
        "body": "This could be improved",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": None,
        "position": {
            "new_path": "src/main.py",
            "old_path": None,
            "new_line": 15,
            "old_line": None,
        },
    }

    result = GitLabMapper.to_comment(note_data)

    assert result.file_path == "src/main.py"
    assert result.line_from == 15
    assert result.line_to == 15
    assert result.updated_at is None


def test_should_map_comment_when_note_has_old_line_position():
    note_data = {
        "id": 99999,
        "author": {"username": "reviewer"},
        "body": "Fix this",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
        "position": {
            "new_path": None,
            "old_path": "src/utils.py",
            "new_line": None,
            "old_line": 20,
        },
    }

    result = GitLabMapper.to_comment(note_data)

    assert result.file_path == "src/utils.py"
    assert result.line_from == 20
    assert result.line_to == 20


def test_should_map_comment_when_position_is_empty():
    note_data = {
        "id": 11111,
        "author": {"username": "user"},
        "body": "Comment",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": None,
        "position": {},
    }

    result = GitLabMapper.to_comment(note_data)

    assert result.file_path is None
    assert result.line_from is None
    assert result.line_to is None


def test_should_raise_error_when_mr_data_is_missing_fields():
    mr_data = {
        "iid": 123,
        "title": "Test MR",
    }

    with pytest.raises(ValueError, match="Invalid GitLab merge request data"):
        GitLabMapper.to_pull_request_info(mr_data)


def test_should_raise_error_when_mr_author_is_missing_username():
    mr_data = {
        "iid": 123,
        "title": "Test MR",
        "author": {},
        "source_branch": "feature",
        "target_branch": "main",
        "state": "opened",
        "created_at": "2023-01-01T12:00:00Z",
        "updated_at": "2023-01-02T12:00:00Z",
    }

    with pytest.raises(ValueError, match="Invalid GitLab merge request data"):
        GitLabMapper.to_pull_request_info(mr_data)


def test_should_raise_error_when_file_change_data_is_invalid():
    change_data = {
        "old_path": "file.py",
    }

    with pytest.raises(ValueError, match="Invalid GitLab file change data"):
        GitLabMapper.to_file_change(change_data)


def test_should_raise_error_when_note_data_is_missing_fields():
    note_data = {
        "id": 12345,
        "body": "Comment",
    }

    with pytest.raises(ValueError, match="Invalid GitLab note data"):
        GitLabMapper.to_comment(note_data)


def test_should_raise_error_when_note_author_is_missing_username():
    note_data = {
        "id": 12345,
        "author": {},
        "body": "Comment",
        "created_at": "2023-01-01T12:00:00Z",
    }

    with pytest.raises(ValueError, match="Invalid GitLab note data"):
        GitLabMapper.to_comment(note_data)

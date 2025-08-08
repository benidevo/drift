from dataclasses import dataclass
from enum import StrEnum


class FileStatus(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass(frozen=True)
class PullRequestInfo:
    id: str
    title: str
    description: str
    author_username: str
    source_branch: str
    target_branch: str
    state: str
    is_merged: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class FileChange:
    path: str
    old_path: str | None
    status: FileStatus
    additions: int
    deletions: int
    patch: str


@dataclass(frozen=True)
class Comment:
    """Can be either a general comment or line-specific review comment."""

    id: str
    author_username: str
    body: str
    created_at: str
    updated_at: str | None
    is_drift_comment: bool = False
    file_path: str | None = None
    line_from: int | None = None
    line_to: int | None = None


@dataclass(frozen=True)
class DiffData:
    files: list[FileChange]
    total_additions: int
    total_deletions: int

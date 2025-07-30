from typing import TypedDict

from drift.models import Comment, FileChange, FileStatus, PullRequestInfo


class GitLabUser(TypedDict):
    username: str


class GitLabMergeRequest(TypedDict):
    iid: int
    title: str
    description: str | None
    author: GitLabUser
    source_branch: str
    target_branch: str
    state: str
    created_at: str
    updated_at: str


class GitLabChange(TypedDict):
    old_path: str
    new_path: str
    new_file: bool | None
    deleted_file: bool | None
    renamed_file: bool | None
    diff: str | None


class GitLabPosition(TypedDict, total=False):
    new_path: str | None
    old_path: str | None
    new_line: int | None
    old_line: int | None


class GitLabNote(TypedDict):
    id: int
    author: GitLabUser
    body: str
    created_at: str
    updated_at: str | None
    position: GitLabPosition | None


class GitLabMapper:
    @staticmethod
    def to_pull_request_info(mr: GitLabMergeRequest) -> PullRequestInfo:
        try:
            return PullRequestInfo(
                id=str(mr["iid"]),
                title=mr["title"],
                description=mr.get("description") or "",
                author_username=mr["author"]["username"],
                source_branch=mr["source_branch"],
                target_branch=mr["target_branch"],
                state="merged" if mr["state"] == "merged" else mr["state"],
                is_merged=mr["state"] == "merged",
                created_at=mr["created_at"],
                updated_at=mr["updated_at"],
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid GitLab merge request data: {e}") from e

    @staticmethod
    def to_file_change(change: GitLabChange) -> FileChange:
        try:
            if change.get("new_file"):
                status = FileStatus.ADDED
            elif change.get("deleted_file"):
                status = FileStatus.DELETED
            elif change.get("renamed_file"):
                status = FileStatus.RENAMED
            else:
                status = FileStatus.MODIFIED

            diff_text = change.get("diff") or ""
            additions = 0
            deletions = 0

            for line in diff_text.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

            return FileChange(
                path=change["new_path"],
                old_path=change["old_path"]
                if change["old_path"] != change["new_path"]
                else None,
                status=status,
                additions=additions,
                deletions=deletions,
                patch=change.get("diff") or "",
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid GitLab file change data: {e}") from e

    @staticmethod
    def to_comment(note: GitLabNote) -> Comment:
        try:
            position = note.get("position")
            file_path = None
            line_from = None
            line_to = None

            if position:
                file_path = position.get("new_path") or position.get("old_path")
                if position.get("new_line"):
                    line_from = position.get("new_line")
                    line_to = position.get("new_line")
                elif position.get("old_line"):
                    line_from = position.get("old_line")
                    line_to = position.get("old_line")

            return Comment(
                id=str(note["id"]),
                author_username=note["author"]["username"],
                body=note["body"],
                created_at=note["created_at"],
                updated_at=note.get("updated_at"),
                is_drift_comment="drift" in note["body"].lower()
                or "🌊" in note["body"],
                file_path=file_path,
                line_from=line_from,
                line_to=line_to,
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid GitLab note data: {e}") from e

from github.File import File
from github.IssueComment import IssueComment
from github.PullRequest import PullRequest
from github.PullRequestComment import PullRequestComment

from drift.models import Comment, FileChange, FileStatus, PullRequestInfo


class GitHubMapper:
    @staticmethod
    def to_pull_request_info(pr: PullRequest) -> PullRequestInfo:
        try:
            return PullRequestInfo(
                id=str(pr.number),
                title=pr.title,
                description=pr.body or "",
                author_username=pr.user.login,
                source_branch=pr.head.ref,
                target_branch=pr.base.ref,
                state="merged" if pr.merged else pr.state,
                is_merged=pr.merged,
                created_at=pr.created_at.isoformat(),
                updated_at=pr.updated_at.isoformat()
                if pr.updated_at
                else pr.created_at.isoformat(),
            )
        except AttributeError as e:
            raise ValueError(f"Invalid GitHub PR data: {e}") from e

    @staticmethod
    def to_file_change(file: File) -> FileChange:
        try:
            status_map = {
                "added": FileStatus.ADDED,
                "removed": FileStatus.DELETED,
                "modified": FileStatus.MODIFIED,
                "renamed": FileStatus.RENAMED,
            }

            return FileChange(
                path=file.filename,
                old_path=getattr(file, "previous_filename", None),
                status=status_map.get(file.status, FileStatus.MODIFIED),
                additions=file.additions,
                deletions=file.deletions,
                patch=file.patch or "",
            )
        except AttributeError as e:
            raise ValueError(f"Invalid GitHub file data: {e}") from e

    @staticmethod
    def to_comment_from_issue_comment(comment: IssueComment) -> Comment:
        try:
            return Comment(
                id=str(comment.id),
                author_username=comment.user.login,
                body=comment.body,
                created_at=comment.created_at.isoformat(),
                updated_at=comment.updated_at.isoformat()
                if comment.updated_at
                else None,
                is_drift_comment=bool(
                    comment.body
                    and ("drift" in comment.body.lower() or "🌊" in comment.body)
                ),
            )
        except AttributeError as e:
            raise ValueError(f"Invalid GitHub issue comment data: {e}") from e

    @staticmethod
    def to_comment_from_review_comment(comment: PullRequestComment) -> Comment:
        try:
            return Comment(
                id=str(comment.id),
                author_username=comment.user.login,
                body=comment.body,
                created_at=comment.created_at.isoformat(),
                updated_at=comment.updated_at.isoformat()
                if comment.updated_at
                else None,
                is_drift_comment=bool(
                    comment.body
                    and ("drift" in comment.body.lower() or "🌊" in comment.body)
                ),
                file_path=comment.path,
                line_from=comment.original_line or comment.line,
                line_to=comment.line,
            )
        except AttributeError as e:
            raise ValueError(f"Invalid GitHub review comment data: {e}") from e

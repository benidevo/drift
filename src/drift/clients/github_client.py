import hashlib
import json
import re
import secrets
from typing import Any

from cachetools import TTLCache
from github import Auth, Github
from github.PullRequest import PullRequest

from drift.adapters.github_mapper import GitHubMapper
from drift.clients.base import BaseGitClient
from drift.clients.mixins.caching import CacheMixin
from drift.clients.mixins.pagination import PaginationMixin
from drift.exceptions import APIError, AuthenticationError, ResourceNotFoundError
from drift.logger import get_logger
from drift.models import Comment, DiffData, FileChange, PullRequestInfo


class GitHubClient(BaseGitClient[Github], CacheMixin, PaginationMixin):
    MAX_FILES_PER_PR = 1000
    MAX_COMMENTS_PER_PR = 1000
    MAX_COMMITS_PER_PR = 500

    def __init__(
        self,
        token: str,
        repo_identifier: str,
        base_url: str | None = None,
        logger: Any | None = None,
        cache_ttl: int = 300,
        cache_maxsize: int = 500,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        per_page: int = 100,
    ) -> None:
        auth = Auth.Token(token)
        client = Github(
            auth=auth,
            base_url=base_url or "https://api.github.com",
            per_page=per_page,
        )
        logger = logger or get_logger(self.__class__.__name__)
        super().__init__(
            client=client,
            repo_identifier=repo_identifier,
            logger=logger,
            cache_ttl=cache_ttl,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)
        self._cache_ttl = cache_ttl
        self._cache_salt = secrets.token_hex(8)
        self.per_page = min(per_page, 100)
        self.mapper = GitHubMapper()
        self._validate_repo_identifier(repo_identifier)

    def _make_cache_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate secure cache key with salt."""
        key_data = {
            "class": self.__class__.__name__,
            "salt": self._cache_salt,
            "repo": hashlib.sha256(self.repo_identifier.encode()).hexdigest()[:8],
            "args": [str(arg) for arg in args],
            "kwargs": {k: str(v) for k, v in sorted(kwargs.items())},
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    @staticmethod
    def _validate_repo_identifier(identifier: str) -> None:
        """Validate repository identifier format."""
        pattern = r"^[a-zA-Z0-9\-_.]+/[a-zA-Z0-9\-_.]+$"
        if not re.match(pattern, identifier):
            raise ValueError("Invalid repository identifier format")

    def _validate_pr_id(self, pr_id: str) -> int:
        """Validate and convert PR ID to prevent injection."""
        try:
            pr_int = int(pr_id)
            if pr_int <= 0 or pr_int > 999999:
                raise ValueError("Invalid PR ID range")
            return pr_int
        except (ValueError, TypeError) as e:
            raise ResourceNotFoundError("Invalid PR identifier") from e

    def _validate_comment_id(self, comment_id: str) -> int:
        """Validate and convert comment ID."""
        try:
            comment_int = int(comment_id)
            if comment_int <= 0:
                raise ValueError("Invalid comment ID")
            return comment_int
        except (ValueError, TypeError) as e:
            raise ResourceNotFoundError("Invalid comment identifier") from e

    def _sanitize_error_message(self, error: Exception, context: str) -> str:
        """Sanitize error messages to prevent information leakage."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str:
            return f"Authentication failed during {context}"
        elif "404" in error_str or "not found" in error_str:
            return f"Resource not found during {context}"
        elif "403" in error_str or "forbidden" in error_str:
            return f"Access forbidden during {context}"
        elif "rate limit" in error_str:
            return f"Rate limit exceeded during {context}"
        else:
            return f"Operation failed during {context}"

    def _load_repository(self) -> Any:
        try:
            return self.with_retry(lambda: self.client.get_repo(self.repo_identifier))()
        except Exception as e:
            error_str = str(e).lower()
            if "401" in error_str or "unauthorized" in error_str:
                raise AuthenticationError(
                    self._sanitize_error_message(e, "repository access")
                ) from e
            if "404" in error_str or "not found" in error_str:
                raise ResourceNotFoundError(
                    self._sanitize_error_message(e, "repository lookup")
                ) from e
            msg = self._sanitize_error_message(e, "repository loading")
            self.logger.error(f"Failed to load repository: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "repository loading")
            ) from e

    def get_pr_info(self, pr_id: str) -> PullRequestInfo:
        pr_int = self._validate_pr_id(pr_id)
        cache_key = f"pr_info:{self._make_cache_key(pr_id)}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            pr = self.with_retry(lambda: self.repo.get_pull(pr_int))()
            result = self.mapper.to_pull_request_info(pr)
            self._cache[cache_key] = result
            return result
        except ValueError as e:
            if "Invalid GitHub PR data" in str(e):
                raise
            raise ResourceNotFoundError(f"Pull request {pr_id} not found") from e
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "PR info retrieval")
            self.logger.error(f"Failed to get PR info: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "PR info retrieval")
            ) from e

    def get_diff_data(self, pr_id: str) -> DiffData:
        pr_int = self._validate_pr_id(pr_id)
        cache_key = f"diff_data:{self._make_cache_key(pr_id)}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()

            files: list[FileChange] = []
            file_count = 0
            for file in self.paginate_github(pr.get_files()):
                if file_count >= self.MAX_FILES_PER_PR:
                    self.logger.warning(
                        f"PR has more than {self.MAX_FILES_PER_PR} files, truncating"
                    )
                    break
                files.append(self.mapper.to_file_change(file))
                file_count += 1

            result = DiffData(
                files=files,
                total_additions=pr.additions,
                total_deletions=pr.deletions,
            )
            self._cache[cache_key] = result
            return result
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "diff data retrieval")
            self.logger.error(f"Failed to get diff data: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "diff data retrieval")
            ) from e

    def get_commit_messages(self, pr_id: str) -> list[str]:
        pr_int = self._validate_pr_id(pr_id)
        cache_key = f"commit_messages:{self._make_cache_key(pr_id)}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()

            messages: list[str] = []
            commit_count = 0
            for commit in self.paginate_github(pr.get_commits()):
                if commit_count >= self.MAX_COMMITS_PER_PR:
                    self.logger.warning(
                        f"Truncating: PR has >{self.MAX_COMMITS_PER_PR} commits"
                    )
                    break
                messages.append(commit.commit.message)
                commit_count += 1

            self._cache[cache_key] = messages
            return messages
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "commit message retrieval")
            self.logger.error(f"Failed to get commit messages: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "commit message retrieval")
            ) from e

    def get_pr_context(self, pr_id: str) -> dict[str, str]:
        pr_int = self._validate_pr_id(pr_id)
        cache_key = f"pr_context:{self._make_cache_key(pr_id)}"
        if cache_key in self._cache:
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()

            context = {
                "title": pr.title,
                "description": pr.body or "",
                "author": pr.user.login,
                "base_branch": pr.base.ref,
                "head_branch": pr.head.ref,
                "state": pr.state,
                "merged": str(pr.merged),
                "mergeable": (
                    str(pr.mergeable) if pr.mergeable is not None else "unknown"
                ),
                "labels": ", ".join([label.name for label in pr.labels]),
                "assignees": ", ".join([a.login for a in pr.assignees]),
                "reviewers": ", ".join([r.login for r in pr.requested_reviewers]),
                "milestone": pr.milestone.title if pr.milestone else "",
                "created_at": pr.created_at.isoformat(),
                "updated_at": pr.updated_at.isoformat() if pr.updated_at else "",
                "closed_at": pr.closed_at.isoformat() if pr.closed_at else "",
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else "",
                "commits": str(pr.commits),
                "additions": str(pr.additions),
                "deletions": str(pr.deletions),
                "changed_files": str(pr.changed_files),
            }

            self._cache[cache_key] = context
            return context
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "PR context retrieval")
            self.logger.error(f"Failed to get PR context: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "PR context retrieval")
            ) from e

    def get_existing_comments(self, pr_id: str) -> list[Comment]:
        pr_int = self._validate_pr_id(pr_id)
        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()

            comments: list[Comment] = []
            comment_count = 0

            for issue_comment in self.paginate_github(pr.get_issue_comments()):
                if comment_count >= self.MAX_COMMENTS_PER_PR:
                    self.logger.warning(
                        f"Truncating: PR has >{self.MAX_COMMENTS_PER_PR} comments"
                    )
                    break
                comments.append(
                    self.mapper.to_comment_from_issue_comment(issue_comment)
                )
                comment_count += 1

            for review_comment in self.paginate_github(pr.get_comments()):
                if comment_count >= self.MAX_COMMENTS_PER_PR:
                    self.logger.warning(
                        f"Truncating: PR has >{self.MAX_COMMENTS_PER_PR} comments"
                    )
                    break
                comments.append(
                    self.mapper.to_comment_from_review_comment(review_comment)
                )
                comment_count += 1

            return comments
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "comment retrieval")
            self.logger.error(f"Failed to get comments: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "comment retrieval")
            ) from e

    def post_comment(self, pr_id: str, comment: str) -> None:
        pr_int = self._validate_pr_id(pr_id)
        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()
            self.with_retry(lambda: pr.create_issue_comment(comment))()
            self.logger.info(f"Posted comment to PR {pr_id}")
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Pull request not found") from e
            msg = self._sanitize_error_message(e, "comment posting")
            self.logger.error(f"Failed to post comment: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "comment posting")
            ) from e

    def update_comment(self, pr_id: str, comment_id: str, comment: str) -> None:
        pr_int = self._validate_pr_id(pr_id)
        comment_int = self._validate_comment_id(comment_id)
        try:
            pr: PullRequest = self.with_retry(lambda: self.repo.get_pull(pr_int))()
            issue_comment = self.with_retry(lambda: pr.get_issue_comment(comment_int))()
            self.with_retry(lambda: issue_comment.edit(comment))()
            self.logger.info(f"Updated comment {comment_id} on PR {pr_id}")
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError("Comment or pull request not found") from e
            msg = self._sanitize_error_message(e, "comment update")
            self.logger.error(f"Failed to update comment: {msg}")
            raise APIError(
                message=self._sanitize_error_message(e, "comment update")
            ) from e

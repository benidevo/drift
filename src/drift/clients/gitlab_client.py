import hashlib
import json
import re
import secrets
import time
from typing import Any

from cachetools import TTLCache
from gitlab import Gitlab
from gitlab.exceptions import GitlabError

from drift.adapters.gitlab_mapper import (
    GitLabChange,
    GitLabMapper,
    GitLabMergeRequest,
    GitLabNote,
    GitLabPosition,
)
from drift.clients.base import BaseGitClient
from drift.clients.mixins.caching import CacheMixin
from drift.clients.mixins.pagination import PaginationMixin
from drift.exceptions import APIError, AuthenticationError, ResourceNotFoundError
from drift.logger import get_logger
from drift.models import Comment, DiffData, PullRequestInfo


class GitLabClient(BaseGitClient[Gitlab], CacheMixin, PaginationMixin):
    MAX_FILES_PER_MR = 1000
    MAX_COMMENTS_PER_MR = 1000
    MAX_COMMITS_PER_MR = 500

    SENSITIVE_PATTERNS = [
        re.compile(r"token[=:][\S]{1,100}", re.IGNORECASE),
        re.compile(r"api[_-]?key[=:][\S]{1,100}", re.IGNORECASE),
        re.compile(r"password[=:][\S]{1,100}", re.IGNORECASE),
        re.compile(r"secret[=:][\S]{1,100}", re.IGNORECASE),
        re.compile(r"glpat-[\S]{20,}", re.IGNORECASE),
        re.compile(r"private[_-]?token[=:\s]+[\S]{1,100}", re.IGNORECASE),
    ]

    MAX_MEMORY_PER_REQUEST = 50 * 1024 * 1024
    ESTIMATED_OBJECT_OVERHEAD = 2048

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
        client = Gitlab(
            url=base_url or "https://gitlab.com",
            private_token=token,
            per_page=per_page,
            timeout=30,
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

        self._cache_salt = hashlib.sha256(
            f"{repo_identifier}:{secrets.token_hex(16)}:{time.time()}".encode()
        ).hexdigest()[:32]
        self.per_page = min(per_page, 100)
        self.mapper = GitLabMapper()
        self._validate_repo_identifier(repo_identifier)

    def _make_cache_key(self, *args: Any, **kwargs: Any) -> str:
        MAX_ARG_SIZE = 100
        MAX_ARGS = 10

        truncated_args = []
        for arg in args[:MAX_ARGS]:
            arg_str = str(arg)[:MAX_ARG_SIZE]
            truncated_args.append(hashlib.sha256(arg_str.encode()).hexdigest()[:32])

        truncated_kwargs = {}
        for k, v in sorted(kwargs.items())[:MAX_ARGS]:
            k_str = str(k)[:50]
            v_str = str(v)[:MAX_ARG_SIZE]
            truncated_kwargs[k_str] = hashlib.sha256(v_str.encode()).hexdigest()[:32]

        key_data = {
            "class": self.__class__.__name__,
            "salt": self._cache_salt[:32],
            "repo": hashlib.sha256(self.repo_identifier.encode()).hexdigest()[:32],
            "args": truncated_args,
            "kwargs": truncated_kwargs,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        if len(key_str) > 10000:
            key = f"oversized:{len(key_str)}:{key_str[:1000]}"
            return hashlib.sha256(key.encode()).hexdigest()
        return hashlib.sha256(key_str.encode()).hexdigest()

    @staticmethod
    def _validate_repo_identifier(identifier: str) -> None:
        if len(identifier) > 255:
            raise ValueError("Repository identifier too long")

        if identifier.isdigit():
            if not (1 <= int(identifier) <= 2147483647):
                raise ValueError("Invalid project ID range")
        else:
            parts = identifier.split("/")
            if len(parts) < 2:
                raise ValueError("Invalid repository identifier format")

            valid_chars = set(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/.~"
            )
            if not all(c in valid_chars for c in identifier):
                raise ValueError("Invalid characters in repository identifier")

    def _validate_mr_id(self, mr_id: str) -> int:
        if not isinstance(mr_id, str | int):
            raise ResourceNotFoundError("Invalid MR identifier type")

        try:
            mr_id_int = int(mr_id)
            if not (1 <= mr_id_int <= 2147483647):
                raise ResourceNotFoundError("MR ID out of valid range")
            return mr_id_int
        except (ValueError, TypeError) as e:
            raise ResourceNotFoundError(f"Invalid MR ID: {mr_id}") from e

    def _validate_comment_id(self, comment_id: str) -> int:
        if not isinstance(comment_id, str | int):
            raise ValueError("Invalid comment identifier type")

        try:
            comment_id_int = int(comment_id)
            if not (1 <= comment_id_int <= 2147483647):
                raise ValueError("Comment ID out of valid range")
            return comment_id_int
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid comment ID: {comment_id}") from e

    def _sanitize_error_message(self, error: Exception, context: str) -> str:
        error_msg = str(error)[:5000]

        for pattern in self.SENSITIVE_PATTERNS:
            error_msg = pattern.sub("[REDACTED]", error_msg)

        if len(error_msg) > 500:
            error_msg = error_msg[:497] + "..."

        return f"{context}: {error_msg}"

    def _estimate_object_size(self, obj: Any) -> int:
        if hasattr(obj, "__dict__"):
            return len(str(obj.__dict__)) + self.ESTIMATED_OBJECT_OVERHEAD
        elif hasattr(obj, "__sizeof__"):
            return int(obj.__sizeof__()) + self.ESTIMATED_OBJECT_OVERHEAD
        else:
            return self.ESTIMATED_OBJECT_OVERHEAD

    def _fetch_with_transient_error_handling(self, fetch_func: Any) -> Any:
        try:
            return fetch_func()
        except GitlabError as e:
            if hasattr(e, "response_code") and e.response_code in [502, 503, 504]:
                from drift.exceptions import NetworkError

                raise NetworkError(
                    f"GitLab service temporarily unavailable: {e.response_code}"
                ) from e
            raise

    def _load_repository(self) -> Any:
        try:
            self.client.auth()

            if self.repo_identifier.isdigit():
                return self.client.projects.get(int(self.repo_identifier))
            else:
                return self.client.projects.get(self.repo_identifier)
        except GitlabError as e:
            if hasattr(e, "response_code") and e.response_code in [502, 503, 504]:
                from drift.exceptions import NetworkError

                raise NetworkError(
                    f"GitLab service temporarily unavailable: {e.response_code}"
                ) from e
            elif "401" in str(e) or "Unauthorized" in str(e):
                raise AuthenticationError(
                    "Authentication failed: Invalid or expired token"
                ) from e
            elif "404" in str(e) or "Not Found" in str(e):
                raise ResourceNotFoundError(
                    f"Repository not found: {self.repo_identifier}"
                ) from e
            else:
                raise APIError(
                    message=self._sanitize_error_message(e, "Failed to load repository")
                ) from e
        except Exception as e:
            if "401" in str(e) or "Unauthorized" in str(e):
                raise AuthenticationError(
                    "Authentication failed: Invalid or expired token"
                ) from e
            elif "404" in str(e) or "Not Found" in str(e):
                raise ResourceNotFoundError(
                    f"Repository not found: {self.repo_identifier}"
                ) from e
            else:
                raise APIError(
                    message=self._sanitize_error_message(e, "Failed to load repository")
                ) from e

    def get_pr_info(self, pr_id: str) -> PullRequestInfo:
        mr_id = self._validate_mr_id(pr_id)
        cache_key = f"mr_info:{self._make_cache_key(pr_id)}"

        if cache_key in self._cache:
            self.logger.debug(f"Cache hit for MR info: {mr_id}")
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            mr = self.with_retry(
                lambda: self._fetch_with_transient_error_handling(
                    lambda: self.repo.mergerequests.get(mr_id)
                )
            )()

            mr_data: GitLabMergeRequest = {
                "iid": mr.iid,
                "title": mr.title,
                "description": mr.description,
                "author": {"username": mr.author["username"]},
                "source_branch": mr.source_branch,
                "target_branch": mr.target_branch,
                "state": mr.state,
                "created_at": mr.created_at,
                "updated_at": mr.updated_at,
            }

            result = self.mapper.to_pull_request_info(mr_data)
            self._cache[cache_key] = result
            return result
        except ResourceNotFoundError:
            raise
        except GitlabError as e:
            if hasattr(e, "response_code") and e.response_code in [502, 503, 504]:
                from drift.exceptions import NetworkError

                raise NetworkError(
                    f"GitLab service temporarily unavailable: {e.response_code}"
                ) from e
            elif (
                "404" in str(e) or e.response_code == 404
                if hasattr(e, "response_code")
                else False
            ):
                raise ResourceNotFoundError(f"Merge request not found: {mr_id}") from e
            msg = self._sanitize_error_message(e, f"Failed to get MR info for {mr_id}")
            raise APIError(message=msg) from e
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError(f"Merge request not found: {mr_id}") from e
            msg = self._sanitize_error_message(e, f"Failed to get MR info for {mr_id}")
            raise APIError(message=msg) from e

    def get_diff_data(self, pr_id: str) -> DiffData:
        mr_id = self._validate_mr_id(pr_id)
        cache_key = f"diff_data:{self._make_cache_key(pr_id)}"

        if cache_key in self._cache:
            self.logger.debug(f"Cache hit for diff data: {mr_id}")
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()

            changes = self.with_retry(lambda: mr.changes())()

            files = []
            total_additions = 0
            total_deletions = 0

            for i, change in enumerate(changes.get("changes", [])):
                if i >= self.MAX_FILES_PER_MR:
                    self.logger.warning(
                        f"MR {mr_id} has more than {self.MAX_FILES_PER_MR} files. "
                        "Truncating."
                    )
                    break

                change_data: GitLabChange = {
                    "old_path": change.get("old_path", ""),
                    "new_path": change.get("new_path", ""),
                    "new_file": change.get("new_file", False),
                    "deleted_file": change.get("deleted_file", False),
                    "renamed_file": change.get("renamed_file", False),
                    "diff": change.get("diff", ""),
                }

                file_change = self.mapper.to_file_change(change_data)
                files.append(file_change)
                total_additions += file_change.additions
                total_deletions += file_change.deletions

            result = DiffData(
                files=files,
                total_additions=total_additions,
                total_deletions=total_deletions,
            )
            self._cache[cache_key] = result
            return result
        except ResourceNotFoundError:
            raise
        except Exception as e:
            msg = self._sanitize_error_message(
                e, f"Failed to get diff data for MR {mr_id}"
            )
            raise APIError(message=msg) from e

    def get_commit_messages(self, pr_id: str) -> list[str]:
        mr_id = self._validate_mr_id(pr_id)
        cache_key = f"commit_messages:{self._make_cache_key(pr_id)}"

        if cache_key in self._cache:
            self.logger.debug(f"Cache hit for commit messages: {mr_id}")
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()

            commits = self.with_retry(lambda: mr.commits())()

            messages = []
            for i, commit in enumerate(commits):
                if i >= self.MAX_COMMITS_PER_MR:
                    self.logger.warning(
                        f"MR {mr_id} has more than {self.MAX_COMMITS_PER_MR} commits. "
                        "Truncating."
                    )
                    break
                messages.append(commit.message.strip())

            self._cache[cache_key] = messages
            return messages
        except ResourceNotFoundError:
            raise
        except Exception as e:
            msg = self._sanitize_error_message(
                e, f"Failed to get commits for MR {mr_id}"
            )
            raise APIError(message=msg) from e

    def get_pr_context(self, pr_id: str) -> dict[str, str]:
        mr_id = self._validate_mr_id(pr_id)
        cache_key = f"mr_context:{self._make_cache_key(pr_id)}"

        if cache_key in self._cache:
            self.logger.debug(f"Cache hit for MR context: {mr_id}")
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()

            context = {
                "merge_status": mr.merge_status,
                "has_conflicts": (
                    str(mr.has_conflicts) if hasattr(mr, "has_conflicts") else "unknown"
                ),
                "work_in_progress": (
                    str(mr.work_in_progress)
                    if hasattr(mr, "work_in_progress")
                    else "false"
                ),
                "draft": str(mr.draft) if hasattr(mr, "draft") else "false",
                "mergeable": (
                    str(mr.mergeable) if hasattr(mr, "mergeable") else "unknown"
                ),
                "pipeline_status": (
                    mr.pipeline.get("status", "none") if mr.pipeline else "none"
                ),
                "approvals_required": (
                    str(mr.approvals_required)
                    if hasattr(mr, "approvals_required")
                    else "0"
                ),
                "approvals_left": (
                    str(mr.approvals_left) if hasattr(mr, "approvals_left") else "0"
                ),
                "discussion_locked": (
                    str(mr.discussion_locked)
                    if hasattr(mr, "discussion_locked")
                    else "false"
                ),
                "assignee": (
                    mr.assignee.get("username", "none") if mr.assignee else "none"
                ),
                "milestone": (
                    mr.milestone.get("title", "none") if mr.milestone else "none"
                ),
                "labels": ", ".join(mr.labels) if mr.labels else "none",
            }

            self._cache[cache_key] = context
            return context
        except ResourceNotFoundError:
            raise
        except Exception as e:
            msg = self._sanitize_error_message(
                e, f"Failed to get context for MR {mr_id}"
            )
            raise APIError(message=msg) from e

    def get_existing_comments(self, pr_id: str) -> list[Comment]:
        mr_id = self._validate_mr_id(pr_id)
        cache_key = f"comments:{self._make_cache_key(pr_id)}"

        if cache_key in self._cache:
            self.logger.debug(f"Cache hit for comments: {mr_id}")
            return self._cache[cache_key]  # type: ignore[no-any-return]

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()

            notes: list[Any] = []
            page = 1
            per_page = 100
            max_pages = 50
            estimated_memory = 0

            while len(notes) < self.MAX_COMMENTS_PER_MR and page <= max_pages:
                expected_size = per_page * self.ESTIMATED_OBJECT_OVERHEAD
                if estimated_memory + expected_size > self.MAX_MEMORY_PER_REQUEST:
                    self.logger.warning(
                        f"Stopping comment fetch for MR {mr_id}: memory limit"
                    )
                    break

                batch = self.with_retry(
                    lambda p=page: mr.notes.list(
                        page=p,
                        per_page=min(per_page, self.MAX_COMMENTS_PER_MR - len(notes)),
                        get_all=False,
                    )
                )()
                if not batch:
                    break

                batch_memory = sum(self._estimate_object_size(note) for note in batch)
                if estimated_memory + batch_memory > self.MAX_MEMORY_PER_REQUEST:
                    self.logger.warning(
                        f"Stopping comment fetch for MR {mr_id}: actual memory exceeded"
                    )
                    break

                notes.extend(batch)
                estimated_memory += batch_memory
                page += 1
                if len(batch) < per_page:
                    break

            comments = []
            for i, note in enumerate(notes):
                if i >= self.MAX_COMMENTS_PER_MR:
                    self.logger.warning(
                        f"MR {mr_id} has more than {self.MAX_COMMENTS_PER_MR} "
                        "comments. Truncating."
                    )
                    break

                try:
                    note_data: GitLabNote = {
                        "id": note.id,
                        "author": {"username": note.author.get("username", "unknown")},
                        "body": note.body,
                        "created_at": note.created_at,
                        "updated_at": (
                            note.updated_at if hasattr(note, "updated_at") else None
                        ),
                        "position": None,
                    }
                    comment = self.mapper.to_comment(note_data)
                    comments.append(comment)
                except (AttributeError, KeyError, TypeError) as e:
                    self.logger.warning(f"Failed to process note in MR {mr_id}: {e}")
                    continue

            discussions = []
            page = 1
            per_page = 100
            max_pages = 50
            remaining = self.MAX_COMMENTS_PER_MR - len(comments)

            while remaining > 0 and page <= max_pages:
                expected_size = per_page * self.ESTIMATED_OBJECT_OVERHEAD
                if estimated_memory + expected_size > self.MAX_MEMORY_PER_REQUEST:
                    self.logger.warning(
                        f"Stopping discussion fetch for MR {mr_id}: memory limit"
                    )
                    break

                batch = self.with_retry(
                    lambda p=page, r=remaining: mr.discussions.list(
                        page=p, per_page=min(per_page, r), get_all=False
                    )
                )()
                if not batch:
                    break

                batch_memory = sum(self._estimate_object_size(disc) for disc in batch)
                if estimated_memory + batch_memory > self.MAX_MEMORY_PER_REQUEST:
                    self.logger.warning(
                        f"Stopping discussion fetch for MR {mr_id}: memory exceeded"
                    )
                    break

                discussions.extend(batch)
                estimated_memory += batch_memory
                page += 1

                for disc in batch:
                    try:
                        attributes = getattr(disc, "attributes", {})
                        notes_list = attributes.get("notes")
                        notes_count = (
                            len(notes_list) if isinstance(notes_list, list) else 0
                        )
                    except (AttributeError, TypeError):
                        notes_count = 0
                        self.logger.warning(
                            f"Malformed discussion object in MR {mr_id}"
                        )
                    remaining -= notes_count
                    if remaining <= 0:
                        break

                if remaining <= 0 or len(batch) < per_page:
                    break

            for discussion in discussions:
                try:
                    discussion_notes = getattr(discussion, "attributes", {}).get(
                        "notes", []
                    )
                except (AttributeError, TypeError):
                    self.logger.warning(f"Malformed discussion in MR {mr_id}")
                    continue

                for note in discussion_notes:
                    if len(comments) >= self.MAX_COMMENTS_PER_MR:
                        break

                    try:
                        if not note.get("id") or not note.get("created_at"):
                            self.logger.warning(
                                f"Skipping malformed discussion note in MR {mr_id}: "
                                "missing required fields"
                            )
                            continue

                        position: GitLabPosition | None = None
                        if "position" in note and isinstance(
                            note.get("position"), dict
                        ):
                            position = GitLabPosition(
                                new_path=note["position"].get("new_path"),
                                old_path=note["position"].get("old_path"),
                                new_line=note["position"].get("new_line"),
                                old_line=note["position"].get("old_line"),
                            )

                        discussion_note_data: GitLabNote = {
                            "id": int(note["id"]),
                            "author": {
                                "username": note.get("author", {}).get(
                                    "username", "unknown"
                                )
                            },
                            "body": note.get("body", ""),
                            "created_at": note["created_at"],
                            "updated_at": note.get("updated_at"),
                            "position": position,
                        }

                        comment = self.mapper.to_comment(discussion_note_data)
                        comments.append(comment)
                    except (AttributeError, KeyError, TypeError) as e:
                        self.logger.warning(
                            f"Failed to process discussion note in MR {mr_id}: {e}"
                        )
                        continue

            self._cache[cache_key] = comments
            return comments
        except ResourceNotFoundError:
            raise
        except Exception as e:
            msg = self._sanitize_error_message(
                e, f"Failed to get comments for MR {mr_id}"
            )
            raise APIError(message=msg) from e

    def post_comment(self, pr_id: str, comment: str) -> None:
        mr_id = self._validate_mr_id(pr_id)

        if not comment or not comment.strip():
            raise ValueError("Comment cannot be empty")

        if len(comment) > 65536:
            raise ValueError("Comment is too long")

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()
            self.with_retry(lambda: mr.notes.create({"body": comment}))()

            cache_key = f"comments:{self._make_cache_key(pr_id)}"
            if cache_key in self._cache:
                del self._cache[cache_key]

            self.logger.info(f"Posted comment to MR {mr_id}")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            msg = self._sanitize_error_message(
                e, f"Failed to post comment to MR {mr_id}"
            )
            raise APIError(message=msg) from e

    def update_comment(self, pr_id: str, comment_id: str, comment: str) -> None:
        mr_id = self._validate_mr_id(pr_id)
        note_id = self._validate_comment_id(comment_id)

        if not comment or not comment.strip():
            raise ValueError("Comment cannot be empty")

        if len(comment) > 65536:
            raise ValueError("Comment is too long")

        try:
            mr = self.with_retry(lambda: self.repo.mergerequests.get(mr_id))()
            note = self.with_retry(lambda: mr.notes.get(note_id))()
            note.body = comment
            self.with_retry(lambda: note.save())()

            cache_key = f"comments:{self._make_cache_key(pr_id)}"
            if cache_key in self._cache:
                del self._cache[cache_key]

            self.logger.info(f"Updated comment {note_id} in MR {mr_id}")
        except ResourceNotFoundError:
            raise
        except Exception as e:
            if "404" in str(e):
                raise ResourceNotFoundError(f"Comment not found: {comment_id}") from e
            msg = self._sanitize_error_message(
                e, f"Failed to update comment {comment_id} in MR {mr_id}"
            )
            raise APIError(message=msg) from e

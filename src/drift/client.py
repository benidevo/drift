from abc import ABC, abstractmethod
from enum import StrEnum

from drift.models import Comment, DiffData, PullRequestInfo


class GitProvider(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class GitClient(ABC):
    @abstractmethod
    def get_pr_info(self, pr_id: str) -> PullRequestInfo:
        raise NotImplementedError

    @abstractmethod
    def get_diff_data(self, pr_id: str) -> DiffData:
        raise NotImplementedError

    @abstractmethod
    def get_commit_messages(self, pr_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_pr_context(self, pr_id: str) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def get_existing_comments(self, pr_id: str) -> list[Comment]:
        raise NotImplementedError

    @abstractmethod
    def post_comment(self, pr_id: str, comment: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_comment(self, pr_id: str, comment_id: str, comment: str) -> None:
        raise NotImplementedError

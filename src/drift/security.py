from pathlib import Path
import re

from drift.exceptions import ConfigurationError, SecurityError


class SecurityValidator:
    FORBIDDEN_OUTPUT_DIRS = {"/etc", "/sys", "/proc", "/boot", "/dev", "/root"}
    SENSITIVE_FILE_PATTERNS = {
        ".ssh/authorized_keys",
        ".ssh/id_rsa",
        ".ssh/id_rsa.pub",
        ".bashrc",
        ".bash_profile",
        ".zshrc",
        ".gitconfig",
        "passwd",
        "shadow",
        "sudoers",
    }

    @staticmethod
    def validate_config_path(path: str) -> Path:
        if not path:
            raise ConfigurationError("Config path cannot be empty")

        resolved = Path(path).resolve()
        if not resolved.exists():
            raise ConfigurationError(f"Config file not found: {path}")
        if resolved.is_dir():
            raise ConfigurationError("Config path must be a file, not a directory")
        if resolved.suffix not in {".yaml", ".yml", ".json"}:
            raise ConfigurationError("Config file must be .yaml, .yml, or .json")

        max_size = 1024 * 1024
        if resolved.stat().st_size > max_size:
            raise ConfigurationError(f"Config file too large (max {max_size} bytes)")

        return resolved

    @staticmethod
    def validate_output_path(path: str) -> Path:
        if not path:
            raise ValueError("Output path cannot be empty")

        resolved = Path(path).resolve()
        for forbidden in SecurityValidator.FORBIDDEN_OUTPUT_DIRS:
            if str(resolved).startswith(forbidden):
                raise SecurityError(f"Cannot write to system directory: {forbidden}")
        path_str = str(resolved)
        for pattern in SecurityValidator.SENSITIVE_FILE_PATTERNS:
            if pattern in path_str:
                raise SecurityError("Cannot overwrite sensitive file")
        parent = resolved.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            except PermissionError as e:
                raise SecurityError(f"Cannot create output directory: {parent}") from e
        if resolved.exists():
            if not resolved.is_file():
                raise SecurityError("Output path must be a file, not a directory")
            if not resolved.parent.is_dir():
                raise SecurityError("Parent directory does not exist")

        return resolved

    @staticmethod
    def validate_pr_id(pr_id_str: str) -> str:
        if not pr_id_str:
            raise ValueError("PR ID cannot be empty")

        pr_id_str = pr_id_str.strip()
        try:
            pr_id = int(pr_id_str)
        except ValueError as e:
            raise ValueError(f"Invalid PR ID format: {pr_id_str}") from e
        if not 1 <= pr_id <= 2147483647:
            raise ValueError(f"PR ID out of valid range: {pr_id}")

        return pr_id_str

    @staticmethod
    def validate_comment_id(comment_id_str: str) -> str:
        if not comment_id_str:
            raise ValueError("Comment ID cannot be empty")

        comment_id_str = comment_id_str.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", comment_id_str):
            raise ValueError(f"Invalid comment ID format: {comment_id_str}")
        if len(comment_id_str) > 100:
            raise ValueError("Comment ID too long")

        return comment_id_str

    @staticmethod
    def sanitize_for_logging(text: str) -> str:
        if not text:
            return text
        patterns = [
            # GitHub tokens
            (r"ghp_[A-Za-z0-9]{36}", "ghp_[REDACTED]"),
            (r"ghp_[A-Za-z0-9]+", "ghp_[REDACTED]"),  # Partial tokens
            (r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}", "github_pat_[REDACTED]"),
            # GitLab tokens
            (r"glpat-[A-Za-z0-9_\-]{20,}", "glpat-[REDACTED]"),
            (r"glprt-[A-Za-z0-9_\-]{20,}", "glprt-[REDACTED]"),
            # Generic patterns
            (r"(password|token|secret|key|api_key|apikey)=[^\s]+", r"\1=[REDACTED]"),
            (r"(Authorization|X-Api-Key):\s*Bearer\s+[^\s]+", r"\1: [REDACTED]"),
            (r"(Authorization|X-Api-Key):\s*[^\s]+", r"\1: [REDACTED]"),
        ]

        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    @staticmethod
    def sanitize_error_message(error: Exception) -> str:
        error_str = str(error)
        sanitized = SecurityValidator.sanitize_for_logging(error_str)
        sanitized = re.sub(r"/[/\w\-\.]+/(\w+\.\w+)", r"\1", sanitized)

        return sanitized

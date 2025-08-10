class DriftException(Exception):
    pass


class AuthenticationError(DriftException):
    pass


class RateLimitError(DriftException):
    def __init__(self, reset_time: int | None = None, *args: object) -> None:
        super().__init__(*args)
        self.reset_time = reset_time


class ResourceNotFoundError(DriftException):
    pass


class APIError(DriftException):
    def __init__(
        self, status_code: int | None = None, message: str = "", *args: object
    ) -> None:
        super().__init__(message, *args)
        self.status_code = status_code
        self.message = message


class ConfigurationError(DriftException):
    pass


class SecurityError(DriftException):
    pass


class ValidationError(DriftException):
    pass


class NetworkError(DriftException):
    pass


class TimeoutError(DriftException):
    pass

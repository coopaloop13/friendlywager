class DomainError(Exception):
    code = "INVALID"

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    code = "NOT_FOUND"


class Forbidden(DomainError):
    code = "FORBIDDEN"


class Conflict(DomainError):
    code = "CONFLICT"


class Invalid(DomainError):
    code = "INVALID"


class Locked(DomainError):
    code = "LOCKED"


class Unauthenticated(DomainError):
    code = "UNAUTHENTICATED"


class HandleRequired(DomainError):
    """The code was right but the email is new: ask for a handle and verify again with the same code."""

    code = "HANDLE_REQUIRED"


class RateLimited(DomainError):
    code = "RATE_LIMITED"


class Unavailable(DomainError):
    """Something we depend on failed; the message is safe to show and the action is worth retrying."""

    code = "UNAVAILABLE"

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

from enum import Enum


class FailureCode(Enum):
    UNAUTHORIZED = "Unauthorized"
    CONFLICT = "Conflict"
    INVALID_INPUT = "InvalidInput"
    NOT_FOUND = "NotFound"
    UNAVAILABLE = "Unavailable"


class Failure(Exception):
    """An operation refused or could not complete. `code` says which kind; `message` is for the operator."""

    def __init__(self, code: FailureCode, message: str):
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message

"""Domain errors. The API turns each into a JSON error with a stable `code`."""


class CarobError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str = "", **details: object) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details


class NotFound(CarobError):
    status = 404
    code = "not_found"


class Forbidden(CarobError):
    status = 403
    code = "forbidden"


class Unauthorized(CarobError):
    status = 401
    code = "unauthorized"


class Conflict(CarobError):
    status = 409
    code = "conflict"


class InsufficientFunds(CarobError):
    status = 422
    code = "insufficient_funds"


class AccountNotActive(CarobError):
    status = 422
    code = "account_not_active"


class InvalidAmount(CarobError):
    status = 422
    code = "invalid_amount"


class QuoteExpired(CarobError):
    status = 422
    code = "quote_expired"


class ProviderError(CarobError):
    status = 502
    code = "provider_error"

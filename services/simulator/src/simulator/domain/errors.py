class DomainError(Exception):
    """A business rule was violated; the surrounding transaction is rolled back."""


class NotFound(DomainError):
    pass


class InvalidTransition(DomainError):
    pass


class OutOfStock(DomainError):
    pass


class ProductUnavailable(DomainError):
    pass

def validate_unit(value: str) -> str:
    """Return a usable batch unit label."""
    if not isinstance(value, str) or not value.strip() or not value.isprintable():
        raise ValueError('unit must be nonblank printable text')
    return value


def require_batch_unit(registered: str, requested: str) -> None:
    if validate_unit(requested) != registered:
        raise ValueError('unit differs from the registered batch unit')

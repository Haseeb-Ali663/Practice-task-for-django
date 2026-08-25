"""Helpers for reading and validating raw query-string values."""

from rest_framework.exceptions import ValidationError


def int_param(params, name, default=None, minimum=None):
    """
    Read `name` out of a query dict as an integer.

    Returns `default` when the parameter is absent or blank. Raises DRF's
    ValidationError (rendered as HTTP 400) when the value is not an integer,
    or falls below `minimum`.
    """
    raw = params.get(name)
    if raw in (None, ""):
        return default

    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: "Must be an integer."})

    if minimum is not None and value < minimum:
        raise ValidationError({name: f"Must be greater than or equal to {minimum}."})
    return value

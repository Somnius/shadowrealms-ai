"""
Strict request-field parsing for JSON bodies (pure, no Flask).

Every helper raises ``RequestValidationError`` (a ``ValueError``) whose
``public_message`` is fit for a 400 response, so a route can turn bad input
types into a 400 instead of a 500. JSON booleans are
never accepted as numbers (Python's ``bool`` is an ``int`` subclass, so
``int(True) == 1`` would otherwise slip through).
"""

from __future__ import annotations

import re
from typing import Any, Optional

_INT_STR = re.compile(r"^\s*[+-]?\d+\s*$")


class RequestValidationError(ValueError):
    """
    Bad client input, with a message written by our own code for the client.

    ``public_message`` is built only from fixed text, field names and limits that
    the calling code chose (never from another exception's text), so a route may
    return it in a 400 body. Routes catch this type and answer with
    ``e.public_message``; any other exception (a plain ``ValueError`` from a
    library, a DB error, ...) must get a generic message, with details only in
    the logs. It subclasses ``ValueError`` so older callers that catch
    ``ValueError`` keep working.
    """

    def __init__(self, public_message: str):
        super().__init__(public_message)
        self.public_message = public_message


def body_object(data: Any) -> dict:
    """A JSON body must be an object; a missing/empty body counts as ``{}``."""
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RequestValidationError("Request body must be a JSON object")
    return data


def strict_int(
    value: Any,
    name: str,
    default: Optional[int] = None,
    lo: Optional[int] = None,
    hi: Optional[int] = None,
) -> Optional[int]:
    """
    Parse an integer field. ``None`` / ``""`` → ``default``. Accepts ints, whole-number
    floats (``3.0``) and digit strings (``"3"``). Rejects bools, fractions and anything
    else. ``lo`` / ``hi`` are inclusive bounds (checked only on a given value).
    """
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise RequestValidationError(f"{name} must be an integer, not a boolean")
    if isinstance(value, int):
        iv = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise RequestValidationError(f"{name} must be a whole number")
        iv = int(value)
    elif isinstance(value, str) and _INT_STR.match(value):
        iv = int(value)
    else:
        raise RequestValidationError(f"{name} must be an integer")
    if lo is not None and iv < lo:
        raise RequestValidationError(f"{name} must be at least {lo}" if hi is None else f"{name} must be between {lo} and {hi}")
    if hi is not None and iv > hi:
        raise RequestValidationError(f"{name} must be at most {hi}" if lo is None else f"{name} must be between {lo} and {hi}")
    return iv


def strict_bool(value: Any, name: str, default: bool = False) -> bool:
    """A JSON boolean; ``None`` → ``default``. Strings like ``"false"`` are rejected."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise RequestValidationError(f"{name} must be true or false")


def optional_str(value: Any, name: str, default: str = "", max_len: Optional[int] = None) -> str:
    """A string field, stripped; ``None`` / blank → ``default``. Non-strings are rejected."""
    if value is None:
        return default
    if not isinstance(value, str):
        raise RequestValidationError(f"{name} must be a string")
    s = value.strip()
    if not s:
        return default
    if max_len is not None and len(s) > max_len:
        raise RequestValidationError(f"{name} must be at most {max_len} characters")
    return s


def chat_text(value: Any, name: str = "message", max_len: int = 8000) -> str:
    """A required chat text: a non-blank string of at most ``max_len`` characters (returned as is)."""
    if not isinstance(value, str):
        raise RequestValidationError(f"{name} must be a string")
    if not value.strip():
        raise RequestValidationError(f"{name} is required")
    if len(value) > max_len:
        raise RequestValidationError(f"{name} is too long (max {max_len} characters)")
    return value

"""
Log-injection protection (CodeQL py/log-injection, CWE-117).

A value a client controls (a username, a path segment, an exception text that
quotes user input) must not be able to start a new log line or hide one with
terminal control codes. Two layers:

* ``install_log_sanitizer()`` wraps the process-wide log record factory, so
  every record (ours, gunicorn's, any library's) gets its finished message
  escaped: CR/LF and other control characters become visible escapes such as
  ``\\n``. Tracebacks from ``logger.exception`` keep their real line breaks,
  but control characters inside each line are escaped too.
* ``safe_log_value()`` escapes one value at the call site. It is what static
  analysis (CodeQL) recognises, so the flagged log calls use it explicitly.
"""

from __future__ import annotations

import logging
import re
import traceback
from typing import Any, Optional

# C0 controls except TAB, DEL, C1 controls, and the Unicode line/paragraph
# separators, which some log viewers also treat as line breaks.
_UNSAFE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f  ]")
_NAMED = {"\n": "\\n", "\r": "\\r"}


def _escape_char(match: "re.Match[str]") -> str:
    ch = match.group(0)
    named = _NAMED.get(ch)
    if named:
        return named
    code = ord(ch)
    return f"\\x{code:02x}" if code <= 0xFF else f"\\u{code:04x}"


def escape_log_text(text: str) -> str:
    """Escape control characters in ``text`` (``"a\\nb"`` -> ``"a\\\\nb"``)."""
    if not _UNSAFE.search(text):
        return text
    return _UNSAFE.sub(_escape_char, text)


def safe_log_value(value: Any, max_len: Optional[int] = None) -> str:
    """
    ``value`` as a single-line string that is safe to put in a log message.

    Control characters are escaped (so the original is still readable) and the
    result is cut to ``max_len`` characters when given. ``None`` becomes
    ``"None"``, like ``%s`` would print it.
    """
    text = value if isinstance(value, str) else str(value)
    if max_len is not None and len(text) > max_len:
        text = text[:max_len] + "..."
    text = escape_log_text(text)
    # No line breaks are left after escape_log_text; the explicit replace calls
    # are the form CodeQL's log-injection query recognises as a sanitizer.
    return text.replace("\r\n", "").replace("\n", "")


class LogInjectionFilter(logging.Filter):
    """Handler/logger filter that escapes control characters in a record's message."""

    def filter(self, record: logging.LogRecord) -> bool:
        sanitize_record(record)
        return True


def sanitize_record(record: logging.LogRecord) -> logging.LogRecord:
    """Render ``msg % args`` once and store the escaped result (``args`` cleared)."""
    if getattr(record, "_sr_log_safe", False):
        return record
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001 - a bad format string; leave it for logging to report
        return record
    record.msg = escape_log_text(message)
    record.args = None
    # Tracebacks and stacks keep their line breaks, but each line is escaped: exception text
    # often quotes client input. Formatters reuse a pre-filled exc_text instead of rendering it.
    if record.exc_info and not record.exc_text:
        record.exc_text = format_exception_safely(record.exc_info)
    if record.stack_info:
        record.stack_info = _escape_lines(record.stack_info)
    # Note: fields passed with extra={...} are set after this runs and are not escaped.
    record._sr_log_safe = True
    return record


_FRAME_CHUNK = ("  File ", "Traceback ", "\nDuring handling", "\nThe above exception")


def format_exception_safely(exc_info) -> str:
    """
    A traceback like ``Formatter.formatException`` makes, with the exception messages escaped.

    Frame lines keep their line breaks (each line escaped); an exception message is escaped
    as a whole, so a newline inside it can't start a fake log line.
    """
    try:
        chunks = traceback.TracebackException(*exc_info).format()
        out = []
        for chunk in chunks:
            if chunk.startswith(_FRAME_CHUNK):
                out.append(_escape_lines(chunk))
            else:
                body = chunk[:-1] if chunk.endswith("\n") else chunk
                out.append(escape_log_text(body) + "\n")
        return "".join(out).rstrip("\n")
    except Exception:  # noqa: BLE001 - never let logging fail over a traceback
        return escape_log_text(str(exc_info[1]))


def _escape_lines(text: str) -> str:
    return "\n".join(escape_log_text(line) for line in text.split("\n"))


_installed = False


def install_log_sanitizer() -> None:
    """Wrap the global log record factory so every record is escaped (idempotent)."""
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        return sanitize_record(previous(*args, **kwargs))

    logging.setLogRecordFactory(factory)
    _installed = True

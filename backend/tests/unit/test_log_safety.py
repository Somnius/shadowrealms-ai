"""Log-injection protection: the safe_log_value helper and the global record sanitizer."""

import io
import logging

import pytest

from services import log_safety
from services.log_safety import (
    LogInjectionFilter,
    escape_log_text,
    install_log_sanitizer,
    safe_log_value,
    sanitize_record,
)


def test_safe_log_value_escapes_line_breaks():
    assert safe_log_value("alice\nINFO forged admin login") == "alice\\nINFO forged admin login"
    assert safe_log_value("a\r\nb") == "a\\r\\nb"
    assert "\n" not in safe_log_value("x\n\n\ny")


def test_safe_log_value_escapes_other_control_chars():
    assert safe_log_value("\x1b[31mred") == "\\x1b[31mred"
    assert safe_log_value("nul\x00") == "nul\\x00"
    assert safe_log_value("del\x7f") == "del\\x7f"
    assert safe_log_value("nel\x85") == "nel\\x85"
    assert safe_log_value("ls ps ") == "ls\\u2028ps\\u2029"


def test_safe_log_value_keeps_plain_text_and_tabs():
    assert safe_log_value("Λευτέρης 42") == "Λευτέρης 42"
    assert safe_log_value("a\tb") == "a\tb"


def test_safe_log_value_converts_non_strings():
    assert safe_log_value(None) == "None"
    assert safe_log_value(17) == "17"
    assert safe_log_value(ValueError("bad\nvalue")) == "bad\\nvalue"
    assert safe_log_value(["a\nb"]) == "['a\\nb']"  # repr already escapes inside lists


def test_safe_log_value_truncates_before_escaping():
    assert safe_log_value("abcdef", max_len=3) == "abc..."
    assert safe_log_value("ab\ncd", max_len=3) == "ab\\n..."
    assert safe_log_value("abc", max_len=3) == "abc"


def test_escape_log_text_returns_same_object_when_clean():
    s = "nothing to do"
    assert escape_log_text(s) is s


def _record(msg, *args):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args or None, None)


def test_sanitize_record_escapes_message_and_args():
    rec = sanitize_record(_record("user %s from %s", "eve\nERROR fake", "1.2.3.4\r"))
    assert rec.getMessage() == "user eve\\nERROR fake from 1.2.3.4\\r"
    assert rec.args is None


def test_sanitize_record_keeps_numeric_formatting():
    rec = sanitize_record(_record("%d rows, %.1f s", 3, 1.25))
    assert rec.getMessage() == "3 rows, 1.2 s"


def test_sanitize_record_with_dict_args():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "%(a)s", ({"a": "x\ny"},), None)
    assert sanitize_record(rec).getMessage() == "x\\ny"


def test_sanitize_record_leaves_broken_format_alone():
    rec = _record("%s %s", "only one")
    assert sanitize_record(rec) is rec
    assert rec.args == ("only one",)


def test_filter_on_a_handler():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(LogInjectionFilter())
    log = logging.getLogger("test_log_safety.filter")
    log.propagate = False
    log.addHandler(handler)
    try:
        log.warning("login failed for %s", "bob\n2026-01-01 INFO admin logged in")
    finally:
        log.removeHandler(handler)
    out = stream.getvalue()
    assert out.count("\n") == 1
    assert "bob\\n2026-01-01 INFO admin logged in" in out


@pytest.fixture
def restore_factory():
    original = logging.getLogRecordFactory()
    was_installed = log_safety._installed
    yield
    logging.setLogRecordFactory(original)
    log_safety._installed = was_installed


def test_install_log_sanitizer_covers_every_logger(restore_factory):
    log_safety._installed = False
    install_log_sanitizer()
    install_log_sanitizer()  # idempotent: no double wrapping
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("test_log_safety.factory")
    log.propagate = False
    log.addHandler(handler)
    try:
        log.error("path %s", "/api/x\r\nINJECTED")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            log.exception("failed on %s", "a\nb")
    finally:
        log.removeHandler(handler)
    lines = stream.getvalue().splitlines()
    assert lines[0] == "path /api/x\\r\\nINJECTED"
    assert lines[1] == "failed on a\\nb"
    # The traceback the formatter appends keeps its own line breaks.
    assert lines[2].startswith("Traceback")

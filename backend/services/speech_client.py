"""
Client for the speech container (speech/, docs/VOICE.md): 127.0.0.1 only, every call carries
X-Speech-Secret. Errors never leak details: callers get (status, json-or-bytes).
"""

import json
import os
import urllib.error
import urllib.request

TIMEOUT = 20


class SpeechUnavailable(Exception):
    """The speech service is not configured or not reachable."""


def _base():
    host = os.getenv("SPEECH_HOST", "127.0.0.1")
    port = os.getenv("SPEECH_PORT", "5055")
    return os.getenv("SPEECH_URL") or f"http://{host}:{port}"


def _call(method, path, body=None):
    secret = os.getenv("SPEECH_SECRET", "")
    if not secret:
        raise SpeechUnavailable("no secret")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_base() + path, data=data, method=method)
    req.add_header("X-Speech-Secret", secret)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # noqa: S310 (fixed local URL)
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "") if e.headers else ""
    except (urllib.error.URLError, OSError) as e:
        raise SpeechUnavailable(type(e).__name__) from e


def call_json(method, path, body=None):
    status, raw, _ = _call(method, path, body)
    try:
        return status, json.loads(raw or b"{}")
    except ValueError:
        return status, {}


def call_bytes(path):
    status, raw, ctype = _call("GET", path)
    return status, raw, ctype


def call_upload(path, fields, filename, data, mime, timeout=60):
    """multipart/form-data POST with one file part named 'file'. (status, json)."""
    import uuid

    secret = os.getenv("SPEECH_SECRET", "")
    if not secret:
        raise SpeechUnavailable("no secret")
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(_base() + path, data=b"".join(parts), method="POST")
    req.add_header("X-Speech-Secret", secret)
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed local URL)
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, OSError) as e:
        raise SpeechUnavailable(type(e).__name__) from e
    try:
        return status, json.loads(raw or b"{}")
    except ValueError:
        return status, {}

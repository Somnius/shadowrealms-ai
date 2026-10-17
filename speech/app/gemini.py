"""Cloud voices (0.23): Google Gemini TTS, opt-in per chronicle, never required.

The backend sends `cloud: {tier, model}` only when the site admin turned cloud voices on and the
chronicle opted in. Keys come from the environment of this container: GEMINI_API_KEY (free tier)
and GEMINI_API_KEY_PAID (paid tier). Keys are never logged or returned, only whether they are set.
Any error, timeout or 429 makes the caller fall back to the local voice for that line.
Stdlib only, so the tests import it without the models.
"""
import base64
import datetime
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
import wave

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS = ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
          "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts")
DEFAULT_MODEL = MODELS[0]
TIERS = ("free", "paid")
KEY_ENV = {"free": "GEMINI_API_KEY", "paid": "GEMINI_API_KEY_PAID"}
PREFIX = "gemini-"

# Google's prebuilt voices and the style word its docs give each (ai.google.dev, speech generation).
# The docs give no genders; Kore (female) and Charon (male) were heard in Greek and English.
VOICES = {
    "Zephyr": "Bright", "Puck": "Upbeat", "Charon": "Informative", "Kore": "Firm",
    "Fenrir": "Excitable", "Leda": "Youthful", "Orus": "Firm", "Aoede": "Breezy",
    "Callirrhoe": "Easy-going", "Autonoe": "Bright", "Enceladus": "Breathy", "Iapetus": "Clear",
    "Umbriel": "Easy-going", "Algieba": "Smooth", "Despina": "Smooth", "Erinome": "Clear",
    "Algenib": "Gravelly", "Rasalgethi": "Informative", "Laomedeia": "Upbeat", "Achernar": "Soft",
    "Alnilam": "Firm", "Schedar": "Even", "Gacrux": "Mature", "Pulcherrima": "Forward",
    "Achird": "Friendly", "Zubenelgenubi": "Casual", "Vindemiatrix": "Gentle", "Sadachbia": "Lively",
    "Sadaltager": "Knowledgeable", "Sulafat": "Warm",
}
HEARD_GENDER = {"Kore": "female", "Charon": "male"}
# gender / role -> voice. Neutral: Schedar, whose documented style is "Even".
ROLES = {"female": "Kore", "male": "Charon", "neutral": "Schedar", "narrator": "Charon"}


class CloudError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code, self.detail = code, detail


def key_for(tier):
    return os.environ.get(KEY_ENV.get(tier, ""), "").strip()


def keys_present():
    return {t: bool(key_for(t)) for t in TIERS}


def voice_name(voice_id):
    """'gemini-Kore' -> 'Kore', else None."""
    if isinstance(voice_id, str) and voice_id.startswith(PREFIX) and voice_id[len(PREFIX):] in VOICES:
        return voice_id[len(PREFIX):]
    return None


def pick(voice=None, gender=None, role=None):
    """The Gemini voice name for a line: an explicit gemini-* voice, else by role / gender."""
    name = voice_name(voice)
    if name:
        return name
    if role == "narrator":
        return ROLES["narrator"]
    return ROLES.get(gender if gender in ("female", "male") else "neutral")


def valid_cloud(cloud):
    """(tier, model) when the request asks for a usable cloud voice, else None."""
    if not isinstance(cloud, dict):
        return None
    tier, model = cloud.get("tier"), cloud.get("model") or DEFAULT_MODEL
    if tier not in TIERS or model not in MODELS or not key_for(tier):
        return None
    return tier, model


def listing():
    return [dict(id=PREFIX + n, engine="gemini", lang="multi", style=s, gender=HEARD_GENDER.get(n),
                 default_for=sorted(r for r, v in ROLES.items() if v == n)) for n, s in VOICES.items()]


def request_body(text, name):
    return {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": name}}}}}


def wav_bytes(resp):
    """RIFF WAV bytes from a generateContent response (raw L16 PCM is wrapped, 24 kHz mono)."""
    try:
        part = resp["candidates"][0]["content"]["parts"][0]["inlineData"]
        raw = base64.b64decode(part["data"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise CloudError("bad_response")
    if raw[:4] == b"RIFF":
        return raw
    mime = str(part.get("mimeType") or "").lower()
    if "l16" not in mime and "pcm" not in mime:
        raise CloudError("bad_response", mime[:60])
    rate = 24000
    for bit in mime.split(";"):
        if bit.strip().startswith("rate="):
            try:
                rate = int(bit.split("=", 1)[1])
            except ValueError:
                pass
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(raw)
    return buf.getvalue()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # the key header must never follow a redirect
        return None


# No proxies from the environment and no redirects: the key goes to Google's API host only.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def synth_until(deadline, text, name, model, tier, wav_path, opener=None):
    """synth() bounded by a total deadline (time.monotonic()): CloudError('timeout') when it passes.
    The call runs in a daemon thread; a late answer is dropped (its temp dir is gone by then)."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise CloudError("timeout")
    box = {}

    def go():
        try:
            synth(text, name, model, tier, wav_path, timeout=left, opener=opener)
        except BaseException as e:  # noqa: BLE001  handed to the caller
            box["e"] = e

    th = threading.Thread(target=go, daemon=True)
    th.start()
    th.join(left)
    if th.is_alive():
        raise CloudError("timeout")
    if "e" in box:
        raise box["e"]


def synth(text, name, model, tier, wav_path, timeout=20, opener=None):
    """One line to a WAV file. Raises CloudError (never with the key in it)."""
    key = key_for(tier)
    if not key:
        raise CloudError("no_key")
    req = urllib.request.Request(API.format(model=model), method="POST",
                                 data=json.dumps(request_body(text, name)).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with (opener or _OPENER.open)(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise CloudError("rate_limited" if e.code == 429 else f"http_{e.code}")
    except (TimeoutError, OSError) as e:  # URLError is an OSError; socket timeouts too
        raise CloudError("timeout" if "timed out" in str(e).lower() else "network", type(e).__name__)
    except ValueError:
        raise CloudError("bad_response")
    with open(wav_path, "wb") as f:
        f.write(wav_bytes(data))


class Stats:
    """Cloud errors today (UTC day) and the last one, for the admin voice health panel."""

    def __init__(self, today=None):
        self._today = today or (lambda: datetime.datetime.now(datetime.timezone.utc).date().isoformat())
        self._lock = threading.Lock()
        self.day, self.errors, self.ok, self.last = None, 0, 0, None

    def _roll(self):
        d = self._today()
        if d != self.day:
            self.day, self.errors, self.ok = d, 0, 0

    def error(self, code, model, tier):
        with self._lock:
            self._roll()
            self.errors += 1
            self.last = dict(code=code, model=model, tier=tier,
                             at=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z")

    def success(self):
        with self._lock:
            self._roll()
            self.ok += 1

    def snapshot(self):
        with self._lock:
            self._roll()
            return dict(keys=keys_present(), errors_today=self.errors, lines_today=self.ok,
                        last_error=self.last)

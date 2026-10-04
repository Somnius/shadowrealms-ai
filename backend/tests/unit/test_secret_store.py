"""Encrypted API keys: roundtrip, wrong key, masking, storage never holds plaintext."""

from services import secret_store as ss


def test_roundtrip_and_random_iv():
    t1 = ss.encrypt_secret("sk-ant-abcdef1234567890", "master-1")
    t2 = ss.encrypt_secret("sk-ant-abcdef1234567890", "master-1")
    assert t1 != t2  # Fernet uses a random IV
    assert "sk-ant" not in t1
    assert ss.decrypt_secret(t1, "master-1") == "sk-ant-abcdef1234567890"


def test_wrong_master_key_or_garbage_gives_none():
    tok = ss.encrypt_secret("secret-value-123456", "master-1")
    assert ss.decrypt_secret(tok, "master-2") is None
    assert ss.decrypt_secret("not-a-token", "master-1") is None


def test_mask_shows_only_last_four():
    assert ss.mask_secret("sk-proj-0123456789abcd") == "••••abcd"
    assert ss.mask_secret("short") == "••••"  # too short to reveal a tail
    assert ss.mask_secret("") == ""
    assert ss.mask_secret(None) == ""


def test_set_get_status_and_delete(app_settings, monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "unit-test-master")
    ss.set_secret("openai_api_key", "  sk-test-0000000000wxyz ")
    stored = app_settings["secret:openai_api_key"]
    assert "sk-test" not in stored
    assert ss.get_secret("openai_api_key") == "sk-test-0000000000wxyz"
    assert ss.secret_status("openai_api_key") == {"set": True, "masked": "••••wxyz"}

    # Rotating FLASK_SECRET_KEY makes the stored key unreadable -> treated as unset
    monkeypatch.setenv("FLASK_SECRET_KEY", "rotated")
    assert ss.get_secret("openai_api_key") is None
    assert ss.secret_status("openai_api_key") == {"set": False, "masked": ""}

    ss.set_secret("openai_api_key", None)
    assert "secret:openai_api_key" not in app_settings

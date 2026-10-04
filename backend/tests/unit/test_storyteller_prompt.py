"""Storyteller prompt budget, history formatting, overflow shrink/retry, Greek script check."""

import pytest

from services import ai_providers as ap
from services import ai_roles
from services import storyteller_prompt as sp


def rows(n, long_reply=False):
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"player line {i}", "username": "bob"})
        out.append({"role": "assistant", "content": ("reply %d " % i) * (200 if long_reply else 3), "username": "bob"})
    return out


def test_estimate_counts_greek_heavier():
    assert sp.estimate_tokens("a" * 350) == 101
    assert sp.estimate_tokens("α" * 200) == 101
    assert sp.estimate_tokens("") == 0


def test_history_drops_current_message_labels_storyteller_and_keeps_newest():
    r = rows(3) + [{"role": "user", "content": "  I draw  my knife ", "username": "bob"}]
    text, n = sp.format_history(r, "I draw my knife", 10_000)
    assert "I draw my knife" not in text and n == 6
    assert "Storyteller: reply 2" in text and "AI (" not in text and "Player bob: player line 0" in text
    small, n2 = sp.format_history(rows(20), None, 60)
    assert 0 < n2 < 40 and "player line 19" in small and "player line 0" not in small


def test_history_clips_long_replies():
    text, _ = sp.format_history(rows(1, long_reply=True), None, 10_000)
    assert len(text) < sp.HISTORY_REPLY_CHARS + 200 and "[…]" in text


def test_budget_and_truncate():
    assert sp.prompt_budget(8192, 1024) == 8192 - 1024 - sp.PROMPT_RESERVE_TOKENS
    t = sp.truncate_to_tokens("word " * 1000, 50)
    assert sp.estimate_tokens(t) <= 52 and t.endswith("[…]")


def test_overflow_detection():
    for msg in ("LM Studio HTTP 400: The number of tokens to keep from the initial prompt is greater than the context length",
                "OpenAI 400 context_length_exceeded", "Trying to keep the first 12453 tokens when context the overflows. n_ctx 8192"):
        assert sp.is_context_overflow(msg)
    assert not sp.is_context_overflow("LM Studio HTTP 500: Failed to load model")


def test_shrink_keeps_player_turn():
    msgs = [{"role": "system", "content": "S" * 1000}, {"role": "user", "content": "U" * 2000}]
    out = sp.shrink_messages(msgs, 0.5)
    assert out[1]["content"] == "U" * 2000 and len(out[0]["content"]) < 600 and "trimmed" in out[0]["content"]


def test_overflow_retries_same_model_trimmed_and_never_falls_to_ollama():
    calls = []

    class LM:
        def generate(self, messages, params):
            calls.append((params["model"], len(messages[0]["content"])))
            if len(messages[0]["content"]) > 500:
                raise ap.ProviderError("LM Studio HTTP 400: context length of 8192 exceeded")
            return "ok"

    msgs = [{"role": "system", "content": "x" * 1000}, {"role": "user", "content": "hi"}]
    res = ai_roles.generate_for_role("storyteller_en", msgs, {}, chain=[("lm_studio", "m"), ("ollama", "o")],
                                     builder=lambda n: LM())
    assert res["model"] == "m" and res["trimmed"] == 2 and [c[0] for c in calls] == ["m", "m", "m"]

    class Always:
        def generate(self, messages, params):
            calls.append(params["model"])
            raise ap.ProviderError("context length exceeded")

    calls.clear()
    with pytest.raises(ap.ProviderError) as e:
        ai_roles.generate_for_role("storyteller_en", msgs, {}, chain=[("lm_studio", "m"), ("ollama", "o")],
                                   builder=lambda n: Always())
    assert "o" not in calls and "prompt too long" in str(e.value)


def test_greek_script_check():
    good = "Ο Φύλακας κοιτάζει — «Φύγε!» 3 ζάρια, Dominate… 🙂"
    assert sp.foreign_script_chars(good) == []
    bad = "Όταν开口, η σιωπή δεν διαρρέει. Οι μαρμάρινα πάγ ιδρώνει สวัสดี"
    assert set(sp.foreign_script_chars(bad)) >= {"开", "口"}
    fixed = sp.strip_foreign_script(bad)
    assert sp.foreign_script_chars(fixed) == [] and fixed.startswith("Όταν, η σιωπή")


def test_in_world_rule_forbids_meta_commentary():
    from services.storyteller_prompt import IN_WORLD_RULE

    rule = IN_WORLD_RULE.lower()
    assert "fourth wall" in rule and "meta commentary" in rule
    assert "dice" in rule and "interface" in rule


def test_storyteller_reply_sends_the_in_world_rule():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2] / "routes" / "ai.py").read_text()
    assert "fixed.append(sp.IN_WORLD_RULE)" in src

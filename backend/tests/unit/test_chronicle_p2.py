"""Chronicle so far, 0.25: the PDF in the sheet's look, the Storyteller's edit copy, translation on
request, the chronicle's language (docs/CHRONICLE.md). Fake models only."""

import io
import re
from datetime import datetime

import pytest

pytest.importorskip("reportlab")

from services import chronicle_digest as cd  # noqa: E402
from services import chronicle_jobs as cj  # noqa: E402
from services.chronicle_pdf import blocks, build_pdf, inline  # noqa: E402
from tests.unit.chronicle_fixtures import Conn, FakeModel  # noqa: E402
from tests.unit.test_chronicle_routes import ADMIN, HELPER_IN, HELPER_OUT, OUTSIDER, PLAYER, ST, api, write  # noqa: E402,F401

EL_URL = cd.FOOTER_URL["el"]  # the one link allowed in exported files
EN_URL = cd.FOOTER_URL["en"]


def pdf_pages(data):
    pypdf = pytest.importorskip("pypdf")
    return [p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(data)).pages]


def pdf_links(data):
    pypdf = pytest.importorskip("pypdf")
    out = set()
    for p in pypdf.PdfReader(io.BytesIO(data)).pages:
        for a in p.get("/Annots") or []:
            a = a.get_object()
            if a.get("/A") and a["/A"].get("/URI"):
                out.add(str(a["/A"]["/URI"]))
    return out


# --- the Markdown we read ---------------------------------------------------------------------

def test_inline_markdown_is_escaped_text():
    assert inline("**Έκδοση:** V5") == "<b>Έκδοση:</b> V5"
    assert inline("_(messages M1)_") == "<i>(messages M1)</i>"
    assert inline(cd.md("<b>x</b> & *y* [z](http://evil)")) == "&lt;b&gt;x&lt;/b&gt; &amp; *y* [z](http://evil)"
    assert inline("snake_case_word") == "snake_case_word"
    assert blocks("# T\n\nA\nB\n\n- one\n- two\n\n## S\n---\n") == [
        ("h1", "T"), ("p", "A B"), ("li", "one"), ("li", "two"), ("h2", "S")]


# --- the PDF ----------------------------------------------------------------------------------

def _story(api, view="st", extra=""):
    return api("GET", f"/api/campaigns/10/chronicle.md?view={view}{extra}", ST).get_data(as_text=True)


def test_greek_pdf_text_footer_link_and_paper(api):
    write(api)
    r = api("GET", "/api/campaigns/10/chronicle.pdf", ST)
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    assert ".pdf" in r.headers["Content-Disposition"]
    data = r.get_data()
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in data  # A4
    pages = pdf_pages(data)
    text = "\n".join(pages)
    assert "Το χρονικό ως τώρα" in text and "Η ΙΣΤΟΡΙΑ ΩΣ ΤΩΡΑ" in text  # section rules in capitals
    assert "Κωνσταντίνος" in text and "Γράφτηκε από το ShadowRealms AI" in text
    assert f"1 / {len(pages)}" in pages[0]
    assert pdf_links(data) == {EL_URL}
    assert b"reportlab.com" not in data and b"http://" not in data  # no host but the footer link
    # the Storyteller part starts on its own page
    st_page = next(i for i, p in enumerate(pages) if "ΜΟΝΟ ΓΙΑ ΤΟΝ STORYTELLER" in p)
    assert st_page > 0 and "Η ΙΣΤΟΡΙΑ ΩΣ ΤΩΡΑ" not in pages[st_page]
    letter = api("GET", "/api/campaigns/10/chronicle.pdf?paper=letter", ST).get_data()
    assert b"/MediaBox [ 0 0 612 792 ]" in letter


def test_player_pdf_has_no_storyteller_part(api):
    write(api)
    text = "\n".join(pdf_pages(api("GET", "/api/campaigns/10/chronicle.pdf?view=player", ST).get_data()))
    assert "ΜΟΝΟ ΓΙΑ ΤΟΝ STORYTELLER" not in text and "eleni_player" not in text and "The Crypt" not in text


def test_english_letter_pdf():
    md = cd.story_markdown({"name": "Night Owls"}, {"tldr": "Short.", "so_far": ["One.", "Two."]}, [], "en", "st")
    data = build_pdf(md, "en", "letter", title="Night Owls — The chronicle so far")
    assert b"/MediaBox [ 0 0 612 792 ]" in data
    text = "\n".join(pdf_pages(data))
    assert "THE STORY SO FAR" in text and "Written by ShadowRealms AI" in text and EN_URL in text
    assert pdf_links(data) == {EN_URL}


def test_pdf_routes_have_the_md_permissions(api):
    write(api)
    for url in ("/api/campaigns/10/chronicle.pdf", "/api/campaigns/10/chronicle/minutes.pdf?last=2"):
        assert api("GET", url, OUTSIDER).status_code == 404
        assert api("GET", url, HELPER_OUT).status_code == 404
        assert api("GET", url, PLAYER).status_code == 403
        for uid in (ST, ADMIN, HELPER_IN):
            assert api("GET", url, uid).status_code == 200, (url, uid)
    assert api("GET", "/api/campaigns/10/chronicle/minutes.pdf?last=x", ST).status_code == 400
    m = "\n".join(pdf_pages(api("GET", "/api/campaigns/10/chronicle/minutes.pdf?last=2", ST).get_data()))
    assert "Οι τελευταίες 2 νύχτες" in m


# --- the edit copy ----------------------------------------------------------------------------

EDIT = "# Athens — Το χρονικό ως τώρα\n\n## Η ιστορία ως τώρα\n\nΗ δική μου εκδοχή της ιστορίας.\n"


def test_edit_copy_who_may_save(api):
    write(api)
    url = "/api/campaigns/10/chronicle/edit"
    for uid in (HELPER_IN, PLAYER):
        assert api("PUT", url, uid, {"markdown": EDIT}).status_code == 403
        assert api("GET", url, uid).status_code == 403
    assert api("PUT", url, OUTSIDER, {"markdown": EDIT}).status_code == 404
    g = api("GET", url, ST).get_json()
    assert g["edited"] is False and g["markdown"].startswith("# Athens: Blood and Concrete")
    assert EL_URL not in g["markdown"]  # the footer is added on export
    assert api("PUT", url, ST, {"markdown": "  "}).status_code == 400
    assert api("PUT", url, ST, {"markdown": "x" * (cj.EDIT_MAX_CHARS + 1)}).status_code == 413
    r = api("PUT", url, ADMIN, {"markdown": EDIT})
    assert r.status_code == 200 and r.get_json()["edited"] is True and r.get_json()["newer"] is False
    assert api("GET", "/api/campaigns/10/chronicle", HELPER_IN).get_json()["edit"]["edited"] is True


def test_no_edit_before_a_digest(api):
    assert api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": EDIT}).status_code == 409


def test_exports_use_the_edit_and_say_so(api):
    write(api)
    generated = api.raw.execute("SELECT digest FROM chronicle_digests WHERE kind = 'final'").fetchone()[0]
    api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": EDIT})
    md = _story(api)
    assert "Η δική μου εκδοχή" in md and "με αλλαγές του Storyteller" in md and md.count(EL_URL) == 1
    text = "\n".join(pdf_pages(api("GET", "/api/campaigns/10/chronicle.pdf", HELPER_IN).get_data()))
    assert "Η δική μου εκδοχή" in text and "με αλλαγές του Storyteller" in text
    # the generated text is untouched; the player view and the minutes stay the generated record
    assert api.raw.execute("SELECT digest FROM chronicle_digests WHERE kind = 'final'").fetchone()[0] == generated
    assert "Η δική μου εκδοχή" not in _story(api, "player")
    minutes = api("GET", "/api/campaigns/10/chronicle/minutes.md", ST).get_data(as_text=True)
    assert "Η δική μου εκδοχή" not in minutes and "με αλλαγές" not in minutes


def test_newer_digest_keep_or_start_again(api):
    write(api)
    url = "/api/campaigns/10/chronicle/edit"
    api("PUT", url, ST, {"markdown": EDIT})
    # a newer digest (Rewrite everything) keeps the edit and says so
    api.raw.execute("UPDATE chronicle_digests SET source_hash = 'newer' WHERE kind = 'final'")
    api.raw.commit()
    g = api("GET", url, ST).get_json()
    assert g["edited"] and g["newer"] and "Η δική μου εκδοχή" in g["markdown"]
    assert api("GET", "/api/campaigns/10/chronicle", ST).get_json()["edit"]["newer"] is True
    k = api("PUT", url, ST, {"keep": True}).get_json()
    assert k["edited"] and not k["newer"]
    api.raw.execute("UPDATE chronicle_digests SET source_hash = 'newest' WHERE kind = 'final'")
    api.raw.commit()
    assert api("DELETE", url, HELPER_IN).status_code == 403
    d = api("DELETE", url, ST).get_json()  # start from the new one
    assert d["edited"] is False and "Η δική μου εκδοχή" not in d["markdown"]
    assert "Η δική μου εκδοχή" not in _story(api)


def test_the_writer_keeps_the_edit_when_it_rewrites_the_digest(api):
    write(api)
    api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": EDIT})
    conn = Conn(api.raw)
    runner = cj.Runner(conn, {"id": 1, "campaign_id": 10}, generate=FakeModel(), sleep=lambda s: None, ctx_tokens=32768)
    runner.lang = "el"
    runner._save_digest("final", 0, {"tldr": "new", "so_far": ["new"]}, "h2")
    row = api.raw.execute("SELECT edited_markdown, source_hash, edited_from_hash FROM chronicle_digests "
                          "WHERE kind = 'final'").fetchone()
    assert "Η δική μου εκδοχή" in row[0] and row[1] == "h2" and row[2] != "h2"


# --- translation ------------------------------------------------------------------------------

class Translator(FakeModel):
    """The translator answers 'EN:' plus the placeholders it was given, so the names come back."""

    def __call__(self, role, messages, params, **kw):
        if role != "translator":
            return super().__call__(role, messages, params, **kw)
        line = messages[-1]["content"]
        self.calls.append({"role": role, "name": "translate", "messages": messages})
        phs = re.findall(r"⟦\d+⟧", line)
        return {"text": "EN: translated " + " ".join(phs), "model": "fake-translator"}


def _translate(api, model=None):
    conn = Conn(api.raw)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, ST, "translate", now=datetime(2020, 1, 1), lang="en")
    cur.execute("UPDATE chronicle_jobs SET status = 'running' WHERE id = %s", (jid,))
    conn.commit()
    model = model or Translator()
    status = cj.run_job(conn, cj.get_job(cur, 10, jid), generate=model, sleep=lambda s: None, ctx_tokens=32768)
    return status, model, jid


def test_translate_job_caches_a_translated_digest(api, monkeypatch):
    write(api)
    monkeypatch.setattr(cj, "_pg", lambda: True)
    assert api("POST", "/api/campaigns/10/chronicle/jobs", HELPER_IN, {"scope": "translate", "lang": "en"}).status_code == 403
    assert api("POST", "/api/campaigns/10/chronicle/jobs", ST, {"scope": "translate", "lang": "el"}).status_code == 400
    assert api("POST", "/api/campaigns/10/chronicle/jobs", ST, {"scope": "translate", "lang": "xx"}).status_code == 400
    est = api("GET", "/api/campaigns/10/chronicle/estimate?scope=translate", ST).get_json()
    assert est["texts"] > 5 and est["from"] == "el"
    before = api("GET", "/api/campaigns/10/chronicle?lang=en", ST).get_json()
    assert before["digest"] is None and before["translation"] is None and before["own_lang"] == "el"
    status, model, jid = _translate(api)
    assert status == "done"
    assert {c["role"] for c in model.calls} == {"translator"}
    # names are hidden from the model and put back
    seen = "\n".join(c["messages"][-1]["content"] for c in model.calls)
    assert "⟦1⟧" in seen and "Κωνσταντίνος" not in seen
    row = api.raw.execute("SELECT lang, translated_from, digest FROM chronicle_digests WHERE translated_from IS NOT NULL").fetchone()
    assert row[0] == "en" and row[1] == "el"
    assert "Κωνσταντίνος" in row[2]
    job = api.raw.execute("SELECT status, nights_done, nights, lang FROM chronicle_jobs WHERE id = ?", (jid,)).fetchone()
    assert job[0] == "done" and job[1] == job[2] > 0 and job[3] == "en"
    # the own-language read is unchanged; lang=en reads the translation
    assert api("GET", "/api/campaigns/10/chronicle", ST).get_json()["digest"]["tldr"] == "Ο Κωνσταντίνος κατέβηκε στο υπόγειο και βρήκε το σημείωμα με τα σύμβολα."
    en = api("GET", "/api/campaigns/10/chronicle?lang=en", ST).get_json()
    assert en["lang"] == "en" and en["translation"]["from"] == "el" and en["translation"]["stale"] is False
    assert en["digest"]["tldr"].startswith("EN: translated") and en["chapters"][0]["chapter"]["title"].startswith("EN:")
    p = api("GET", "/api/campaigns/10/chronicle?lang=en&view=player", ST).get_json()
    assert "st_so_far" not in p["digest"]
    md = _story(api, "st", "&lang=en")
    assert md.startswith("# Athens: Blood and Concrete — The chronicle so far") and "translated from Greek" in md
    pdf = api("GET", "/api/campaigns/10/chronicle.pdf?lang=en&paper=letter", ST).get_data()
    assert pdf_links(pdf) == {EN_URL}
    mm = api("GET", "/api/campaigns/10/chronicle/minutes.md?lang=en", ST).get_data(as_text=True)
    assert "EN: translated" in mm and "# Athens: Blood and Concrete — Minutes" in mm
    # a newer digest makes the translation stale
    api.raw.execute("UPDATE chronicle_digests SET source_hash = 'newer' WHERE translated_from IS NULL AND kind = 'final'")
    api.raw.commit()
    assert api("GET", "/api/campaigns/10/chronicle?lang=en", ST).get_json()["translation"]["stale"] is True
    # the own-language read still ignores the translated row
    assert cj.stored_digest(Conn(api.raw).cursor(), 10, "en") is None


def test_translate_needs_a_digest_and_fails_when_nothing_translates(api, monkeypatch):
    monkeypatch.setattr(cj, "_pg", lambda: True)
    assert api("POST", "/api/campaigns/10/chronicle/jobs", ST, {"scope": "translate", "lang": "en"}).status_code == 409
    write(api)

    class Broken(Translator):
        def __call__(self, role, messages, params, **kw):
            if role == "translator":
                return {"text": "", "model": "x"}
            return super().__call__(role, messages, params, **kw)

    status, _m, jid = _translate(api, Broken())
    assert status == "failed"
    assert api.raw.execute("SELECT error FROM chronicle_jobs WHERE id = ?", (jid,)).fetchone()[0] == "translate_failed"
    assert api.raw.execute("SELECT COUNT(*) FROM chronicle_digests WHERE translated_from IS NOT NULL").fetchone()[0] == 0


def test_translation_texts_round_trip():
    digest = {"tldr": "a", "so_far": ["b", "c"], "threads_open": [{"text": "d", "nights": [1]}], "st_so_far": ["e"],
              "_hash": "h"}
    chs = [{"key": "k", "kind": "story", "chapter": {"title": "t", "summary": ["s"], "events": [{"text": "ev", "ids": [1]}],
                                                    "characters": [{"name": "N", "note": "n"}]}}]
    texts = cd.translation_texts(digest, chs)
    assert texts == ["a", "b", "c", "d", "e", "t", "s", "ev", "n"]
    out = cd.apply_translation(digest, chs, [x.upper() for x in texts])
    assert out["threads_open"] == [{"text": "D", "nights": [1]}] and "_hash" not in out
    over = cd.overlay_translation(chs, out)
    assert over[0]["chapter"]["events"] == [{"text": "EV", "ids": [1]}]
    assert over[0]["chapter"]["characters"] == [{"name": "N", "note": "N"}]


# --- the chronicle's language -----------------------------------------------------------------

def test_chronicle_language_validation():
    from services.chronicle_digest import validate_chronicle_language

    assert validate_chronicle_language("el") == ("el", None)
    assert validate_chronicle_language(" EN ") == ("en", None)
    assert validate_chronicle_language(None) == (None, None)
    assert validate_chronicle_language("") == (None, None)
    for bad in ("de", 3, ["el"], "greek"):
        assert validate_chronicle_language(bad)[1]


def test_campaign_language_is_the_digest_language(api):
    api.raw.execute("UPDATE campaigns SET language = 'en'")
    api.raw.commit()
    camp = cj.campaign_row(Conn(api.raw).cursor(), 10)
    assert cj.chronicle_lang(Conn(api.raw).cursor(), camp) == "en"
    assert api("GET", "/api/campaigns/10/chronicle", ST).get_json()["own_lang"] == "en"


def test_campaign_routes_take_the_language():
    """create_campaign and update_campaign validate and store campaigns.language (el/en)."""
    import os

    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "routes", "campaigns.py"), encoding="utf-8").read()
    create = src[src.index("def create_campaign"):src.index("def create_campaign") + 4000]
    assert "validate_chronicle_language(data.get('language'))" in create and "language)" in create
    update = src[src.index("def update_campaign"):]
    update = update[:update.index("\n@campaigns_bp.route")]
    assert "validate_chronicle_language(data.get('language'))" in update and "'language = %s'" in update


# --- review fixes ------------------------------------------------------------------------------

def test_crossed_marks_close_in_order_and_the_pdf_builds(api):
    assert inline("**a _b** c_") == "<b>a <i>b</i></b><i> c</i>"
    assert inline("_x **y_ z**") == "<i>x <b>y</b></i><b> z</b>"
    write(api)
    api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": "# T\n\n**α _β** γ_ and <b>x & **unclosed\n\n- _i **j_"})
    r = api("GET", "/api/campaigns/10/chronicle.pdf", ST)
    assert r.status_code == 200
    text = "\n".join(pdf_pages(r.get_data()))
    assert "α β γ" in text and "<b>x &" in text


def test_greek_bold_prints_bold_and_extracts():
    md = "# Χρονικό\n\n**Κωνσταντίνος Κατακουζηνός** μίλησε.\n"
    data = build_pdf(md, "el")
    plain_data = build_pdf(md.replace("**", ""), "el")
    # one more embedded font: the bold face (its internal name is the variable font's, so count files)
    assert data.count(b"/FontFile2") == plain_data.count(b"/FontFile2") + 1
    assert "Κωνσταντίνος Κατακουζηνός μίλησε." in "\n".join(pdf_pages(data))


def test_the_sheet_pdf_is_byte_identical_after_a_chronicle_pdf(monkeypatch):
    from reportlab import rl_config

    from services.character_sheet_pdf import build_sheet_pdf
    from tests.unit.test_character_sheet_pdf import V5_CHAR

    monkeypatch.setattr(rl_config, "invariant", 1)
    before = build_sheet_pdf(V5_CHAR, player_name="lef")
    build_pdf("# T\n\n**bold** _it_\n", "el")
    assert build_sheet_pdf(V5_CHAR, player_name="lef") == before


def test_a_long_heading_stays_inside_the_rule():
    from reportlab.pdfbase import pdfmetrics

    from services.pdf_look import CINZEL_BOLD, _ellipsize

    long = "A VERY LONG HEADING " * 20
    short = _ellipsize(long, CINZEL_BOLD, 10, 400)
    assert short.endswith("…") and pdfmetrics.stringWidth(short, CINZEL_BOLD, 10) <= 400
    build_pdf("# T\n\n## " + long + "\n\ntext\n", "en")  # builds


def test_split_sentences_keeps_everything():
    text = ("Μία πρόταση εδώ. " * 300).strip()
    parts = cd.split_sentences(text, 2000)
    assert len(parts) > 1 and all(len(p) <= 2000 for p in parts)
    assert " ".join(parts) == text
    assert cd.split_sentences("x" * 4500, 2000) == ["x" * 2000, "x" * 2000, "x" * 500]
    assert cd.split_sentences("short.", 2000) == ["short."]


def test_translate_survives_provider_errors_and_reports_partial(api):
    from services.ai_providers import ProviderError

    write(api)

    class Flaky(Translator):
        n = 0

        def __call__(self, role, messages, params, **kw):
            if role == "translator":
                Flaky.n += 1
                assert params["timeout"] == cj.TRANSLATE_TIMEOUT_S
                if Flaky.n % 3 == 0:
                    raise ProviderError("timeout")
            return super().__call__(role, messages, params, **kw)

    status, _m, jid = _translate(api, Flaky())
    assert status == "partial"
    assert api.raw.execute("SELECT status FROM chronicle_jobs WHERE id = ?", (jid,)).fetchone()[0] == "partial"
    en = api("GET", "/api/campaigns/10/chronicle?lang=en", ST).get_json()
    assert en["translation"]["untranslated"] > 0


def test_long_texts_are_translated_in_pieces(api):
    write(api)
    long_p = ("Ο Κωνσταντίνος κατέβηκε στο υπόγειο. " * 120).strip()
    api.raw.execute("UPDATE chronicle_digests SET digest = json_set(digest, '$.tldr', ?) WHERE kind = 'final'", (long_p,))
    api.raw.commit()
    status, model, _j = _translate(api)
    assert status == "done"
    assert max(len(c["messages"][-1]["content"]) for c in model.calls) < 2100
    tr = api("GET", "/api/campaigns/10/chronicle?lang=en", ST).get_json()["digest"]["tldr"]
    assert tr.count("EN: translated") >= 3


def test_translate_does_not_hold_update_back(api, monkeypatch):
    write(api)
    monkeypatch.setattr(cj, "_pg", lambda: True)
    api.raw.execute("DELETE FROM chronicle_jobs")
    api.raw.commit()
    _translate(api)
    api.raw.execute("UPDATE chronicle_jobs SET created_at = ?", (datetime.now().isoformat(" "),))
    api.raw.commit()
    assert api("POST", "/api/campaigns/10/chronicle/jobs", ST, {}).status_code == 202


def test_translate_refuses_to_drop_an_edit_in_the_target_language(api, monkeypatch):
    write(api)
    monkeypatch.setattr(cj, "_pg", lambda: True)
    # the chronicle was Greek and edited; now it is English with its own digest, and Greek is the other language
    api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": EDIT})
    api.raw.execute("INSERT INTO chronicle_digests (campaign_id, kind, era, lang, digest, source_hash) "
                    "VALUES (10, 'final', 0, 'en', '{\"tldr\": \"x\", \"so_far\": [\"x\"]}', 'h')")
    api.raw.execute("UPDATE campaigns SET language = 'en'")
    api.raw.commit()
    r = api("POST", "/api/campaigns/10/chronicle/jobs", ST, {"scope": "translate", "lang": "el"})
    assert r.status_code == 409 and r.get_json()["error"] == "edited_in_target"
    conn = Conn(api.raw)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, ST, "translate", now=datetime(2020, 1, 1), lang="el")
    cur.execute("UPDATE chronicle_jobs SET status = 'running' WHERE id = %s", (jid,))
    conn.commit()
    assert cj.run_job(conn, cj.get_job(cur, 10, jid), generate=Translator(), sleep=lambda s: None) == "failed"
    edit = api.raw.execute("SELECT edited_markdown FROM chronicle_digests WHERE lang = 'el' AND kind = 'final'").fetchone()[0]
    assert "Η δική μου εκδοχή" in edit


def test_helpers_cannot_cancel(api, monkeypatch):
    monkeypatch.setattr(cj, "_pg", lambda: True)
    job = api("POST", "/api/campaigns/10/chronicle/jobs", ST, {}).get_json()["job"]
    url = f"/api/campaigns/10/chronicle/jobs/{job['id']}"
    assert api("DELETE", url, HELPER_IN).status_code == 403
    assert api("GET", url, HELPER_IN).status_code == 200
    assert api("DELETE", url, ADMIN).status_code == 200

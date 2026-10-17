"""Chronicle so far, 0.26: the horror look of the PDFs, minutes for a date range in the Storyteller's
timezone, and "session ended here" marks (docs/CHRONICLE.md). Fake models only."""

import io
from datetime import datetime

import pytest

pytest.importorskip("reportlab")

from services import chronicle_digest as cd  # noqa: E402
from services import chronicle_jobs as cj  # noqa: E402
from services.chronicle_pdf import build_pdf  # noqa: E402
from tests.unit.chronicle_fixtures import Conn, FakeModel, build, db  # noqa: E402
from tests.unit.test_chronicle_routes import ADMIN, HELPER_IN, OUTSIDER, PLAYER, ST, api, write  # noqa: E402,F401

EL_URL = cd.FOOTER_URL["el"]


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


# --- the horror look ---------------------------------------------------------------------------

def test_horror_pdf_greek_a4_text_paper_once_and_one_link(api):
    write(api)
    r = api("GET", "/api/campaigns/10/chronicle.pdf?look=horror", ST)
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    data = r.get_data()
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in data
    pages = pdf_pages(data)
    assert len(pages) >= 2
    text = "\n".join(pages)
    # Greek comes back out as text: the words are vector text, not part of the paper image
    assert "Το χρονικό ως τώρα" in text and "Κωνσταντίνος" in text and "Η ΙΣΤΟΡΙΑ ΩΣ ΤΩΡΑ" in text
    assert "Γράφτηκε από το ShadowRealms AI" in text and f"1 / {len(pages)}" in pages[0]
    assert data.count(b"/Subtype /Image") == 1  # the paper is embedded once and drawn on every page
    assert pdf_links(data) == {EL_URL}
    assert b"http://" not in data and b"reportlab.com" not in data
    st_page = next(i for i, p in enumerate(pages) if "ΜΟΝΟ ΓΙΑ ΤΟΝ STORYTELLER" in p)
    assert st_page > 0


def test_horror_minutes_and_letter(api):
    write(api)
    data = api("GET", "/api/campaigns/10/chronicle/minutes.pdf?look=horror&paper=letter", ST).get_data()
    assert b"/MediaBox [ 0 0 612 792 ]" in data and data.count(b"/Subtype /Image") == 1
    assert "ΝΥΧΤΑ 1" in "\n".join(pdf_pages(data))


def test_the_sheet_look_stays_the_default():
    md = cd.story_markdown({"name": "Night Owls"}, {"tldr": "Short.", "so_far": ["One."]}, [], "en", "st")
    sheet = build_pdf(md, "en", "a4")
    assert b"/Subtype /Image" not in sheet
    horror = build_pdf(md, "en", "a4", look="horror")
    assert b"/Subtype /Image" in horror
    # an unknown look is the sheet
    assert b"/Subtype /Image" not in build_pdf(md, "en", "a4", look="nope")


def test_horror_route_flag_only_horror(api):
    write(api)
    plain = api("GET", "/api/campaigns/10/chronicle.pdf?look=whatever", ST).get_data()
    assert b"/Subtype /Image" not in plain


def test_horror_text_stays_inside_the_margins():
    from services import chronicle_pdf as cp

    W, H = 595.2756, 841.8898
    long = "\n\n".join(["Μια μεγάλη παράγραφος με πολλές λέξεις για να γεμίσει τη σελίδα. " * 12] * 20)
    data = build_pdf("# Τίτλος\n\n## Ενότητα\n\n" + long, "el", "a4", look="horror")
    pypdf = pytest.importorskip("pypdf")
    xs = []

    def visit(text, cm, tm, font, size):
        if text.strip():
            xs.append((cm[4] + tm[4], cm[5] + tm[5]))

    for p in pypdf.PdfReader(io.BytesIO(data)).pages:
        p.extract_text(visitor_text=visit)
    body = [(x, y) for x, y in xs if y > cp.HM_FOOT + 20]  # the footer line has its own place
    assert body and min(x for x, _ in body) >= cp.HM_SIDE - 1
    assert max(y for _, y in body) <= H - cp.HM_TOP + 14
    assert min(y for _, y in body) >= cp.HM_BOTTOM - 1


# --- minutes for a date range ----------------------------------------------------------------

def _minutes(api, q, uid=ST):
    return api("GET", f"/api/campaigns/10/chronicle/minutes.md?{q}", uid)


def test_range_in_utc_takes_the_nights_whose_first_message_is_inside(api):
    write(api)  # nights start 1, 2 and 3 Oct 2026 at 21:00 UTC
    text = _minutes(api, "from=2026-10-02&to=2026-10-02&tz=UTC").get_data(as_text=True)
    # night 2 is two chapters (Elysium and the closed Crypt), both started on 2 Oct
    assert "## Νύχτα 2" in text and "## Νύχτα 1" not in text and "## Νύχτα 3" not in text
    assert "Από 2 Οκτ 2026 έως 2 Οκτ 2026: 2 γραμμένες νύχτες." in text
    assert "δεν έχουν γραφτεί" not in text and "δεν έχει γραφτεί" not in text


def test_range_uses_the_timezone(api):
    write(api)
    # 21:00 UTC on 1 Oct is midnight on 2 Oct in Athens: night 1 belongs to 2 Oct there
    text = _minutes(api, "from=2026-10-02&to=2026-10-02&tz=Europe/Athens").get_data(as_text=True)
    assert "## Νύχτα 1" in text and "## Νύχτα 2" not in text
    # every date in the file is in that timezone too
    assert "## Νύχτα 1 — The Echoing Basement — 2 Οκτ 2026" in text


def test_range_defaults_to_the_users_display_timezone(api):
    write(api)
    api.raw.execute("ALTER TABLE users ADD COLUMN display_timezone TEXT")
    api.raw.execute("UPDATE users SET display_timezone = 'Europe/Athens' WHERE id = ?", (ST,))
    api.raw.commit()
    text = _minutes(api, "from=2026-10-02&to=2026-10-02").get_data(as_text=True)
    assert "## Νύχτα 1" in text and "## Νύχτα 2" not in text
    # without the column or a timezone it is UTC (the other tests)


def test_range_bad_input(api):
    assert _minutes(api, "from=2026-10-02x").status_code == 400
    assert _minutes(api, "from=2026-10-03&to=2026-10-02").status_code == 400
    assert _minutes(api, "from=2026-13-01&to=2026-13-02").status_code == 400
    assert _minutes(api, "from=yesterday&to=today").status_code == 400
    r = _minutes(api, "from=2026-10-01&to=2026-10-02&tz=Mars/Olympus")
    assert r.status_code == 400 and r.get_json()["error"] == "bad_tz"
    assert _minutes(api, "from=2026-10-01&to=2026-10-02", PLAYER).status_code == 403
    assert _minutes(api, "from=2026-10-01&to=2026-10-02", OUTSIDER).status_code == 404


def test_range_reports_unwritten_nights_at_the_top(api):
    text = _minutes(api, "from=2026-10-01&to=2026-10-31&tz=UTC").get_data(as_text=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[1] == "4 νύχτες σε αυτό το διάστημα δεν έχουν γραφτεί ακόμα ή άλλαξαν από τότε: πάτα Ενημέρωση."
    write(api)
    text = _minutes(api, "from=2026-10-01&to=2026-10-31&tz=UTC").get_data(as_text=True)
    assert "δεν έχουν γραφτεί" not in text and "## Νύχτα 3" in text
    # a new night after the last Update
    api.raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, character_id, message_type, content, "
                    "role, created_at) VALUES (5000, 10, 101, 3, 20, 'ic', 'Μια νέα νύχτα.', 'user', '2026-10-09 21:00:00')")
    api.raw.commit()
    text = _minutes(api, "from=2026-10-01&to=2026-10-31&tz=UTC").get_data(as_text=True)
    assert "1 νύχτα σε αυτό το διάστημα δεν έχει γραφτεί ακόμα ή άλλαξε από τότε: πάτα Ενημέρωση." in text
    # outside the range it is not counted
    text = _minutes(api, "from=2026-10-01&to=2026-10-03&tz=UTC").get_data(as_text=True)
    assert "δεν έχει γραφτεί" not in text


def test_range_minutes_are_the_generated_record_not_the_edit(api):
    write(api)
    assert api("PUT", "/api/campaigns/10/chronicle/edit", ST, {"markdown": "# Mine\n\nHAND EDIT"}).status_code == 200
    for fmt in ("md", "pdf"):
        r = api("GET", f"/api/campaigns/10/chronicle/minutes.{fmt}?from=2026-10-01&to=2026-10-03&tz=UTC", ST)
        assert r.status_code == 200
        body = r.get_data(as_text=True) if fmt == "md" else "\n".join(pdf_pages(r.get_data()))
        assert "HAND EDIT" not in body and ("Νύχτα 1" in body or "ΝΥΧΤΑ 1" in body)


@pytest.fixture
def late_api(monkeypatch, tmp_path):
    """Nights that start at 23:50 UTC and run past midnight."""
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import chronicle

    rows, marks = build("el", 3, start=datetime(2026, 10, 1, 23, 50))
    raw = db(rows, marks)
    monkeypatch.setattr(chronicle, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(cj, "ensure_worker", lambda: False)
    monkeypatch.setenv("CHRONICLE_ARCHIVE_DIR", str(tmp_path))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(chronicle.chronicle_bp, url_prefix="/api")
    with app.app_context():
        token = create_access_token(identity=str(ST))
    c = app.test_client()

    def call(url):
        return c.get(url, headers={"Authorization": f"Bearer {token}"})

    call.raw = raw
    return call


def test_a_night_across_midnight_counts_by_its_first_message(late_api):
    write(type("A", (), {"raw": late_api.raw})())
    one = late_api("/api/campaigns/10/chronicle/minutes.md?from=2026-10-01&to=2026-10-01&tz=UTC").get_data(as_text=True)
    assert "## Νύχτα 1" in one and "## Νύχτα 2" not in one
    # 2 Oct holds the end of night 1 (after midnight) and the start of night 2: only night 2 counts
    two = late_api("/api/campaigns/10/chronicle/minutes.md?from=2026-10-02&to=2026-10-02&tz=UTC").get_data(as_text=True)
    assert "## Νύχτα 2" in two and "## Νύχτα 1" not in two


def test_in_range_helper():
    from datetime import date, timezone
    from zoneinfo import ZoneInfo

    at = datetime(2026, 10, 1, 21, 30)  # naive = UTC
    assert cd.in_range(at, ZoneInfo("UTC"), date(2026, 10, 1), date(2026, 10, 1))
    assert not cd.in_range(at, ZoneInfo("Europe/Athens"), date(2026, 10, 1), date(2026, 10, 1))
    assert cd.in_range(at.replace(tzinfo=timezone.utc), ZoneInfo("America/New_York"), date(2026, 10, 1), date(2026, 10, 1))
    assert not cd.in_range(None, ZoneInfo("UTC"), date(2026, 10, 1), date(2026, 10, 1))


# --- session marks ---------------------------------------------------------------------------

MARKS = "/api/campaigns/10/chronicle/session-marks"


def test_who_may_mark_and_see_marks(api):
    assert api("GET", MARKS, OUTSIDER).status_code == 404
    assert api("GET", MARKS, PLAYER).get_json() == {"message_ids": []}
    for uid in (PLAYER, HELPER_IN):
        assert api("POST", MARKS, uid, {"message_id": 1003}).status_code == 403
    assert api("POST", MARKS, OUTSIDER, {"message_id": 1003}).status_code == 404
    assert api("POST", MARKS, ST, {"message_id": "x"}).status_code == 400
    assert api("POST", MARKS, ST, {"message_id": 999999}).status_code == 404
    assert api("POST", MARKS, ST, {"message_id": 1003}).get_json() == {"message_id": 1003, "marked": True}
    assert api("POST", MARKS, ST, {"message_id": 1003}).status_code == 200  # twice is fine
    assert api("GET", MARKS, PLAYER).get_json() == {"message_ids": [1003]}
    assert api("GET", MARKS, HELPER_IN).get_json() == {"message_ids": [1003]}
    for uid in (PLAYER, HELPER_IN):
        assert api("DELETE", f"{MARKS}/1003", uid).status_code == 403
    assert api("DELETE", f"{MARKS}/1003", ADMIN).get_json() == {"message_id": 1003, "marked": False}
    r = api("DELETE", f"{MARKS}/1003", ADMIN)  # no such mark any more
    assert r.status_code == 404 and r.get_json()["error"] == "not_found"
    assert api("GET", MARKS, ST).get_json() == {"message_ids": []}
    assert api("POST", MARKS, ADMIN, {"message_id": 1003}).status_code == 200


def test_marks_in_a_closed_room_are_not_listed_for_players(api):
    closed = api.raw.execute("SELECT id FROM messages WHERE location_id = 103 ORDER BY id LIMIT 1").fetchone()[0]
    assert api("POST", MARKS, ST, {"message_id": closed}).status_code == 200
    assert api("GET", MARKS, PLAYER).get_json() == {"message_ids": []}
    assert api("GET", MARKS, ST).get_json() == {"message_ids": [closed]}


def test_a_mark_makes_its_night_stale_and_removing_it_settles_again(api):
    write(api)
    cur = Conn(api.raw).cursor()
    assert cj.plan(cur, 10)["stale"] == []
    assert api("POST", MARKS, ST, {"message_id": 1003}).status_code == 200
    stale = cj.plan(cur, 10)["stale"]
    assert stale and all(ch["started_at"] < datetime(2026, 10, 2) for ch in stale)  # only night 1 is cut
    assert api("DELETE", f"{MARKS}/1003", ST).status_code == 200
    assert cj.plan(cur, 10)["stale"] == []


def test_a_mark_cuts_the_chapter_on_the_next_update(api):
    write(api)
    assert api("POST", MARKS, ST, {"message_id": 1003}).status_code == 200
    conn = Conn(api.raw)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, ST, "update", now=datetime(2020, 1, 1, 1))
    cur.execute("UPDATE chronicle_jobs SET status = 'running' WHERE id = %s", (jid,))
    conn.commit()
    assert cj.run_job(conn, cj.get_job(cur, 10, jid), generate=FakeModel(), sleep=lambda s: None, ctx_tokens=32768) == "done"
    story = [c for c in cj.stored_chapters(cur, 10, "el") if c["kind"] == "story"]
    assert any(c["last_id"] == 1003 for c in story) and any(c["first_id"] == 1004 for c in story)


def test_one_date_alone_is_open_ended(api):
    write(api)
    since = _minutes(api, "from=2026-10-02&tz=UTC").get_data(as_text=True)
    assert "## Νύχτα 1" not in since and "## Νύχτα 2" in since and "## Νύχτα 3" in since
    until = _minutes(api, "to=2026-10-01&tz=UTC").get_data(as_text=True)
    assert "## Νύχτα 1" in until and "## Νύχτα 2" not in until


def test_a_mark_on_a_hidden_roll_moves_to_what_the_player_can_see(api):
    hidden = api.raw.execute("SELECT id FROM messages WHERE ai_message_kind LIKE 'dice_roll_hidden%' LIMIT 1").fetchone()[0]
    room = api.raw.execute("SELECT location_id FROM messages WHERE id = ?", (hidden,)).fetchone()[0]
    seen = api.raw.execute(
        "SELECT id FROM messages WHERE location_id = ? AND id <= ? AND COALESCE(ai_message_kind, '') NOT LIKE '%hidden%' "
        "ORDER BY id DESC LIMIT 1", (room, hidden)).fetchone()[0]
    assert api("POST", MARKS, ST, {"message_id": hidden}).status_code == 200
    assert api("GET", MARKS, ST).get_json() == {"message_ids": [hidden]}
    assert api("GET", MARKS, PLAYER).get_json() == {"message_ids": [seen]}
    assert seen != hidden


def test_after_a_mark_the_range_counts_changed_nights_once(api):
    write(api)
    assert api("POST", MARKS, ST, {"message_id": 1003}).status_code == 200
    text = _minutes(api, "from=2026-10-01&to=2026-10-01&tz=UTC").get_data(as_text=True)
    # night 1 is now two nights: its first part changed, its second part is new
    assert "2 νύχτες σε αυτό το διάστημα δεν έχουν γραφτεί ακόμα ή άλλαξαν από τότε" in text
    assert text.count("## Νύχτα") == 1  # the stored night under the same key; nothing doubled


def test_range_in_the_other_language_says_what_is_not_translated(api):
    write(api)
    text = _minutes(api, "from=2026-10-01&to=2026-10-03&tz=UTC&lang=en").get_data(as_text=True)
    assert "4 nights in this range are still in Greek or not translated: press Translate." in text


def test_footer_link_shows_short_text_and_links_the_full_url(api):
    write(api)
    for lang, short in (("el", "lefteros.com/apps/shadowrealms-ai"), ("en", "lefteros.com/en/apps/shadowrealms-ai")):
        assert cd.footer_link_text(lang) == short
        url = cd.FOOTER_URL[lang]
        md = api("GET", f"/api/campaigns/10/chronicle/minutes.md?lang={lang}", ST).get_data(as_text=True)
        if lang == "el":
            assert f"[{short}]({url})" in md
            assert url not in cd.strip_footer(md)
        for look in ("sheet", "horror"):
            for what in ("chronicle.pdf", "chronicle/minutes.pdf"):
                data = api("GET", f"/api/campaigns/10/{what}?look={look}", ST).get_data()
                text = "\n".join(pdf_pages(data))
                assert "lefteros.com/apps/shadowrealms-ai" in text and "https://" not in text
                assert "shadowrealms-ai/" not in text
                assert pdf_links(data) == {EL_URL}
    en = build_pdf(cd.story_markdown({"name": "N"}, {"tldr": "S.", "so_far": ["O."]}, [], "en", "st"), "en", "letter",
                   look="horror")
    assert "lefteros.com/en/apps/shadowrealms-ai" in "\n".join(pdf_pages(en)) and pdf_links(en) == {cd.FOOTER_URL["en"]}
    # an edit copy saved with the old footer loses it too
    old = "# T\n\nText.\n\n---\n_Written by ShadowRealms AI_ · <https://lefteros.com/en/apps/shadowrealms-ai/>\n"
    assert cd.strip_footer(old) == "# T\n\nText.\n"


def test_the_paper_jpeg_goes_into_the_pdf_unchanged():
    import os

    from services.pdf_horror import PAPER_IMAGE

    for paper in ("a4", "letter"):
        data = build_pdf("# T\n\ntext\n\n## Two\n\n" + "Line.\n\n" * 200, "en", paper, look="horror")
        jpeg = open(PAPER_IMAGE[paper], "rb").read()
        assert data.count(jpeg) == 1  # the file's bytes, once, not re-encoded
        assert b"/Filter [ /DCTDecode ]" in data and f"/Length {os.path.getsize(PAPER_IMAGE[paper])}".encode() in data
        pypdf = pytest.importorskip("pypdf")
        for page in pypdf.PdfReader(io.BytesIO(data)).pages:  # every page lists it in its resources
            assert len(page["/Resources"]["/XObject"]) == 1

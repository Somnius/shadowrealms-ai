#!/usr/bin/env python3
"""
Security and feature regression tests (PostgreSQL — matches production SQL placeholders).

Run from repository root with database reachable (e.g. Docker Compose up):

    export DATABASE_TYPE=postgresql
    export DATABASE_HOST=127.0.0.1
    export DATABASE_PORT=5432
    export DATABASE_NAME=shadowrealms_db
    export DATABASE_USER=...
    export DATABASE_PASSWORD=...
    export JWT_SECRET_KEY="${JWT_SECRET_KEY:-test-jwt-secret-key-32bytes-minimum}"
    export FLASK_SECRET_KEY="${FLASK_SECRET_KEY:-test-flask-secret-key-32bytes-min}"
    python3 tests/test_security_and_features.py

Or use the helper script (loads .env when present):

    ./scripts/run_security_tests.sh

Tests mock ChromaDB/RAG init so Chroma does not need to be running.

Covered:
- Admin-only routes reject non-admin users (403).
- JWT required for protected routes (401).
- Campaign discover + join (listed / accepting).
- Messages API includes poster_role.
- Non-numeric campaign id → 404.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Force writable log path for host-side runs (.env may set LOG_FILE under /app).
os.environ["LOG_FILE"] = os.path.join(tempfile.gettempdir(), "sr_security_test.log")

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

# ChromaDB is not required for these route tests (patch after backend on path).
_RAG_PATCHER = patch(
    "services.llm_service.create_rag_service", return_value=MagicMock()
)
_RAG_PATCHER.start()

from main import create_app  # noqa: E402


def _invite_validator(code: str):
    if code == "TEST-PLAYER":
        return "player"
    if code == "TEST-ADMIN":
        return "admin"
    return None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _mock_rag():
    m = MagicMock()
    m.store_campaign_data.return_value = 1
    m.store_world_data.return_value = 1
    return m


def _pg_configured() -> bool:
    if os.getenv("DATABASE_TYPE", "").lower() != "postgresql":
        return False
    pwd = (os.getenv("DATABASE_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or "").strip()
    return bool(pwd)


@unittest.skipUnless(
    _pg_configured(),
    "Set DATABASE_TYPE=postgresql and DATABASE_* / POSTGRES_PASSWORD for integration tests",
)
class TestSecurityAndFeatures(unittest.TestCase):
    """Flask tests for auth boundaries and newer API behavior (PostgreSQL)."""

    @classmethod
    def setUpClass(cls):
        cls._suffix = uuid.uuid4().hex[:10]
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        with patch("routes.auth.validate_invite_code", side_effect=_invite_validator):
            with patch("routes.auth.use_invite_code"):
                with patch("services.mail_service.send_welcome_registration"):
                    for role_key, u, em in (
                        ("pa", f"sec_pa_{cls._suffix}", f"pa_{cls._suffix}@test.local"),
                        ("pb", f"sec_pb_{cls._suffix}", f"pb_{cls._suffix}@test.local"),
                        ("adm", f"sec_adm_{cls._suffix}", f"adm_{cls._suffix}@test.local"),
                    ):
                        inv = "TEST-ADMIN" if role_key == "adm" else "TEST-PLAYER"
                        r = cls.client.post(
                            "/api/auth/register",
                            json={
                                "username": u,
                                "email": em,
                                "password": "TestPass123!",
                                "invite_code": inv,
                            },
                        )
                        if r.status_code not in (200, 201):
                            raise RuntimeError(
                                f"Register failed for {u}: {r.status_code} {r.data!r}"
                            )

        def _tok(username: str) -> str:
            lr = cls.client.post(
                "/api/auth/login",
                json={"username": username, "password": "TestPass123!"},
            )
            assert lr.status_code == 200, lr.data
            return json.loads(lr.data)["access_token"]

        cls.user_a = f"sec_pa_{cls._suffix}"
        cls.user_b = f"sec_pb_{cls._suffix}"
        cls.user_adm = f"sec_adm_{cls._suffix}"

        cls.token_a = _tok(cls.user_a)
        cls.token_b = _tok(cls.user_b)
        cls.token_admin = _tok(cls.user_adm)

        me = cls.client.get("/api/users/me", headers=_auth_headers(cls.token_admin))
        assert me.status_code == 200
        cls.uid_admin = json.loads(me.data)["id"]

    def test_admin_debug_forbidden_for_player(self):
        r = self.client.get(
            f"/api/admin/users/{self.uid_admin}/debug",
            headers=_auth_headers(self.token_a),
        )
        self.assertEqual(r.status_code, 403)

    def test_admin_debug_ok_for_admin(self):
        r = self.client.get(
            f"/api/admin/users/{self.uid_admin}/debug",
            headers=_auth_headers(self.token_admin),
        )
        self.assertEqual(r.status_code, 200)
        body = json.loads(r.data)
        self.assertIn("user", body)
        self.assertEqual(body["user"]["username"], self.user_adm)

    def test_admin_route_rejects_no_token(self):
        r = self.client.get(f"/api/admin/users/{self.uid_admin}/debug")
        self.assertIn(r.status_code, (401, 422))

    def test_campaign_id_must_be_integer(self):
        r = self.client.get(
            "/api/campaigns/not-an-int",
            headers=_auth_headers(self.token_a),
        )
        self.assertEqual(r.status_code, 404)

    def test_join_rejects_nonexistent_campaign(self):
        r = self.client.post(
            "/api/campaigns/999999/join",
            headers=_auth_headers(self.token_a),
        )
        self.assertEqual(r.status_code, 404)

    def test_discover_and_join(self):
        with patch("routes.campaigns.get_rag_service", return_value=_mock_rag()):
            cr = self.client.post(
                "/api/campaigns/",
                headers=_auth_headers(self.token_a),
                json={
                    "name": f"Listed Chronicle {self._suffix}",
                    "description": "Test listing",
                    "game_system": "vampire",
                },
            )
        self.assertEqual(cr.status_code, 201, cr.data)
        cid = json.loads(cr.data)["campaign_id"]

        up = self.client.put(
            f"/api/campaigns/{cid}",
            headers=_auth_headers(self.token_a),
            json={"listing_visibility": "listed", "accepting_players": True},
        )
        self.assertIn(up.status_code, (200, 400), up.data)

        disc = self.client.get(
            "/api/campaigns/discover", headers=_auth_headers(self.token_b)
        )
        self.assertEqual(disc.status_code, 200)
        rows = json.loads(disc.data)
        ids = [x["id"] for x in rows]
        self.assertIn(cid, ids)

        jr = self.client.post(
            f"/api/campaigns/{cid}/join",
            headers=_auth_headers(self.token_b),
        )
        self.assertEqual(jr.status_code, 200)

    def test_messages_include_poster_role(self):
        with patch("routes.campaigns.get_rag_service", return_value=_mock_rag()):
            cr = self.client.post(
                "/api/campaigns/",
                headers=_auth_headers(self.token_a),
                json={
                    "name": f"Msg Chronicle {self._suffix}",
                    "description": "Test",
                    "game_system": "vampire",
                },
            )
        self.assertEqual(cr.status_code, 201)
        cid = json.loads(cr.data)["campaign_id"]

        ch = self.client.post(
            "/api/characters/",
            headers=_auth_headers(self.token_a),
            json={
                "name": f"Nosferatu {self._suffix}",
                "campaign_id": cid,
                "system_type": "vampire",
                "sheet_locked": False,
            },
        )
        self.assertEqual(ch.status_code, 201, ch.data)
        char_id = json.loads(ch.data)["character_id"]

        self.client.put(
            "/api/users/me",
            headers=_auth_headers(self.token_a),
            json={"active_character_id": char_id},
        )

        loc_res = self.client.get(
            f"/api/campaigns/{cid}/locations",
            headers=_auth_headers(self.token_a),
        )
        self.assertEqual(loc_res.status_code, 200)
        locs = json.loads(loc_res.data)
        self.assertTrue(locs)
        lid = locs[0]["id"]

        msg = self.client.post(
            f"/api/campaigns/{cid}/locations/{lid}",
            headers=_auth_headers(self.token_a),
            json={"content": "Hello IC", "message_type": "ic", "role": "user"},
        )
        self.assertIn(msg.status_code, (200, 201), msg.data)

        gr = self.client.get(
            f"/api/campaigns/{cid}/locations/{lid}",
            headers=_auth_headers(self.token_a),
        )
        self.assertEqual(gr.status_code, 200)
        arr = json.loads(gr.data)
        self.assertTrue(isinstance(arr, list))
        self.assertGreaterEqual(len(arr), 1)
        self.assertIn("poster_role", arr[-1])


def tearDownModule():
    _RAG_PATCHER.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)

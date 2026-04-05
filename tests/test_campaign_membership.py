#!/usr/bin/env python3
"""PostgreSQL integration tests: detach, join restriction, per-campaign playing character."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

os.environ["LOG_FILE"] = os.path.join(tempfile.gettempdir(), "sr_campaign_membership_test.log")

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

_RAG_PATCHER = patch(
    "services.llm_service.create_rag_service", return_value=MagicMock()
)
_RAG_PATCHER.start()

from main import create_app  # noqa: E402
from database import get_db  # noqa: E402


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
    "Set DATABASE_TYPE=postgresql and DATABASE_* / POSTGRES_PASSWORD",
)
class TestCampaignMembership(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._suffix = uuid.uuid4().hex[:10]
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        with patch("routes.auth.validate_invite_code", side_effect=_invite_validator):
            with patch("routes.auth.use_invite_code"):
                with patch("services.mail_service.send_welcome_registration"):
                    for u, em, inv in (
                        (f"cm_pa_{cls._suffix}", f"pa_{cls._suffix}@test.local", "TEST-PLAYER"),
                        (f"cm_pb_{cls._suffix}", f"pb_{cls._suffix}@test.local", "TEST-PLAYER"),
                    ):
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
                            raise RuntimeError(f"Register failed: {r.status_code} {r.data!r}")

        def _tok(username: str) -> str:
            lr = cls.client.post(
                "/api/auth/login",
                json={"username": username, "password": "TestPass123!"},
            )
            assert lr.status_code == 200, lr.data
            return json.loads(lr.data)["access_token"]

        cls.user_a = f"cm_pa_{cls._suffix}"
        cls.user_b = f"cm_pb_{cls._suffix}"
        cls.token_a = _tok(cls.user_a)
        cls.token_b = _tok(cls.user_b)

    def _clear_self_join_restrict(self, username: str) -> None:
        """Test isolation: detach in another test sets restrict_self_join_new_chronicles."""
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET restrict_self_join_new_chronicles = %s WHERE username = %s",
                (False, username),
            )
            conn.commit()
        finally:
            conn.close()

    def test_detach_then_cannot_join_unrelated_campaign_without_sheet(self):
        with patch("routes.campaigns.get_rag_service", return_value=_mock_rag()):
            cr = self.client.post(
                "/api/campaigns/",
                headers=_auth_headers(self.token_a),
                json={
                    "name": f"CM Alpha {self._suffix}",
                    "description": "t",
                    "game_system": "vampire",
                },
            )
        self.assertEqual(cr.status_code, 201, cr.data)
        c_alpha = json.loads(cr.data)["campaign_id"]

        up = self.client.put(
            f"/api/campaigns/{c_alpha}",
            headers=_auth_headers(self.token_a),
            json={"listing_visibility": "listed", "accepting_players": True},
        )
        self.assertIn(up.status_code, (200, 400), up.data)

        with patch("routes.campaigns.get_rag_service", return_value=_mock_rag()):
            cr2 = self.client.post(
                "/api/campaigns/",
                headers=_auth_headers(self.token_a),
                json={
                    "name": f"CM Beta {self._suffix}",
                    "description": "t",
                    "game_system": "vampire",
                },
            )
        self.assertEqual(cr2.status_code, 201, cr2.data)
        c_beta = json.loads(cr2.data)["campaign_id"]
        self.client.put(
            f"/api/campaigns/{c_beta}",
            headers=_auth_headers(self.token_a),
            json={"listing_visibility": "listed", "accepting_players": True},
        )

        jr = self.client.post(
            f"/api/campaigns/{c_alpha}/join",
            headers=_auth_headers(self.token_b),
        )
        self.assertEqual(jr.status_code, 200, jr.data)

        det = self.client.post(
            f"/api/campaigns/{c_alpha}/detach",
            headers=_auth_headers(self.token_b),
            json={},
        )
        self.assertEqual(det.status_code, 200, det.data)

        join_beta = self.client.post(
            f"/api/campaigns/{c_beta}/join",
            headers=_auth_headers(self.token_b),
        )
        self.assertEqual(join_beta.status_code, 403, join_beta.data)
        body = json.loads(join_beta.data)
        self.assertEqual(body.get("error_code"), "join_requires_storyteller_approval")

    def test_storyteller_can_set_playing_character_after_player_bound(self):
        self._clear_self_join_restrict(self.user_b)
        with patch("routes.campaigns.get_rag_service", return_value=_mock_rag()):
            cr = self.client.post(
                "/api/campaigns/",
                headers=_auth_headers(self.token_a),
                json={
                    "name": f"CM Gamma {self._suffix}",
                    "description": "t",
                    "game_system": "vampire",
                },
            )
        self.assertEqual(cr.status_code, 201, cr.data)
        cid = json.loads(cr.data)["campaign_id"]
        self.client.put(
            f"/api/campaigns/{cid}",
            headers=_auth_headers(self.token_a),
            json={"listing_visibility": "listed", "accepting_players": True},
        )
        jn = self.client.post(
            f"/api/campaigns/{cid}/join",
            headers=_auth_headers(self.token_b),
        )
        self.assertEqual(jn.status_code, 200, jn.data)

        ch1 = self.client.post(
            "/api/characters/",
            headers=_auth_headers(self.token_b),
            json={
                "name": f"PC1 {self._suffix}",
                "campaign_id": cid,
                "system_type": "vampire",
                "sheet_locked": False,
            },
        )
        self.assertEqual(ch1.status_code, 201, ch1.data)
        char1_id = json.loads(ch1.data)["character_id"]

        ch2 = self.client.post(
            "/api/characters/",
            headers=_auth_headers(self.token_b),
            json={
                "name": f"PC2 {self._suffix}",
                "campaign_id": cid,
                "system_type": "vampire",
                "sheet_locked": False,
            },
        )
        self.assertEqual(ch2.status_code, 201, ch2.data)
        char2_id = json.loads(ch2.data)["character_id"]

        sw = self.client.put(
            f"/api/campaigns/{cid}/my-playing-character",
            headers=_auth_headers(self.token_b),
            json={"character_id": char2_id},
        )
        self.assertEqual(sw.status_code, 403, sw.data)

        me_b = self.client.get("/api/users/me", headers=_auth_headers(self.token_b))
        self.assertEqual(me_b.status_code, 200, me_b.data)
        uid_b = json.loads(me_b.data)["id"]

        st = self.client.put(
            f"/api/campaigns/{cid}/players/{uid_b}/playing-character",
            headers=_auth_headers(self.token_a),
            json={"character_id": char2_id},
        )
        self.assertEqual(st.status_code, 200, st.data)


def tearDownModule():
    _RAG_PATCHER.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)

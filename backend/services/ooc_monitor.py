"""
OOC (Out of Character) Monitoring Service
Monitors OOC rooms for in-character discussions and warns/bans players.

- Staff are never moderated: site admins and helpers, the campaign owner (its Storyteller),
  and any post in staff voice.
- Warnings are per campaign (ooc_violations, last 7 days); WARNING_THRESHOLD warnings give a
  BAN_DURATION_HOURS ban from posting in that campaign only (campaign_bans). The monitor never
  touches users.banned_until / ban_type: site bans stay an admin decision (routes/admin.py).
- One classification per message: services.classifier.classify_cached, shared with the OOC
  moderation note of /api/ai/chat for the same text.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

WARNING_THRESHOLD = 3
BAN_DURATION_HOURS = 24
STAFF_SITE_ROLES = ("admin", "helper")


def _get_db():
    from database import get_db

    return get_db()


def is_exempt_from_ooc_moderation(site_role: Optional[str], is_campaign_owner: bool,
                                  speaker_mode: Optional[str] = None) -> bool:
    """Admins, helpers, the campaign owner (Storyteller) and staff-voice posts are never moderated."""
    if (site_role or "").strip().lower() in STAFF_SITE_ROLES:
        return True
    if is_campaign_owner:
        return True
    return (speaker_mode or "").strip().lower() == "staff"


def _as_datetime(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return v


def campaign_ban_state(row: Optional[dict], now: Optional[datetime] = None) -> Tuple[bool, str]:
    """(is_banned, message) from a campaign_bans row (or None)."""
    if not row:
        return (False, "")
    until = _as_datetime(row.get("banned_until"))
    now = now or datetime.now()
    if until is None or now >= until:
        return (False, "")
    left = until - now
    hours_left = int(left.total_seconds() // 3600)
    minutes_left = int((left.total_seconds() % 3600) // 60)
    return (True, (
        f"⛔ **You are temporarily banned from posting in this campaign.**\n\n"
        f"**Reason:** {row.get('reason') or 'OOC rules'}\n\n"
        f"**Time remaining:** {hours_left}h {minutes_left}m\n\n"
        f"**Ban expires:** {until.strftime('%Y-%m-%d %H:%M')}"
    ))


class OOCMonitor:
    """Monitors OOC rooms for rule violations"""

    def __init__(self, llm_service: Any = None):
        self.llm_service = llm_service  # unused; kept for the factory's signature
        self.warning_threshold = WARNING_THRESHOLD
        self.ban_duration_hours = BAN_DURATION_HOURS
        self.last_classification = None  # result of the last classifier call (for logs / tests)

    def check_message(self, message: str, user_id: int, campaign_id: int, location_type: str,
                      *, site_role: Optional[str] = None, is_campaign_owner: bool = False,
                      speaker_mode: Optional[str] = None) -> Tuple[bool, str, bool]:
        """
        Check if a message violates OOC rules.

        Returns (is_violation, warning_message, should_ban). should_ban means this message
        earned a campaign ban (already recorded).
        """
        # Only monitor OOC rooms (DB may vary casing)
        if str(location_type or "").strip().lower() != "ooc":
            return (False, '', False)
        if is_exempt_from_ooc_moderation(site_role, is_campaign_owner, speaker_mode):
            return (False, '', False)

        # Admin /ai diagnostics — never treat as IC roleplay for OOC moderation
        if re.match(r"^\s*/ai(\s|$)", message or "", re.IGNORECASE):
            return (False, '', False)
        # `/chat …` — explicit assistant prompt; not IC chatter for moderation
        if re.match(r"^\s*/chat(\s|$)", message or "", re.IGNORECASE):
            return (False, '', False)

        if not self._detect_ic_content(message, campaign_id):
            return (False, '', False)

        warning_count = self._log_violation(user_id, campaign_id)
        should_ban = warning_count >= self.warning_threshold
        until = None

        if should_ban:
            until = self._issue_campaign_ban(user_id, campaign_id)
            warning_msg = (
                f"⚠️ **OOC VIOLATION - TEMPORARY BAN ISSUED**\n\n"
                f"You can't post in this campaign for {self.ban_duration_hours} hours.\n\n"
                f"**Reason:** Multiple violations of OOC rules ({self.warning_threshold}+ warnings).\n\n"
                f"The OOC (Out of Character) Lobby is for discussing the game as players, not roleplaying as characters. "
                f"Please keep in-character discussions to the game locations.\n\n"
                f"Your ban will expire at: {until.strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            warnings_left = self.warning_threshold - warning_count
            warning_msg = (
                f"⚠️ **OOC VIOLATION WARNING ({warning_count}/{self.warning_threshold})**\n\n"
                f"Your message appears to contain in-character content. "
                f"The OOC (Out of Character) Lobby is for discussing the game as players, not roleplaying as characters.\n\n"
                f"**Please keep in-character discussions to the game locations.**\n\n"
                f"You have **{warnings_left} warning(s)** remaining before a temporary ban from this campaign."
            )

        # Structured form for the UI (translated there); warning_msg stays as the legacy text.
        self.last_warning = {
            'count': warning_count,
            'threshold': self.warning_threshold,
            'banned': bool(should_ban),
            'ban_hours': self.ban_duration_hours,
            'until': until.isoformat() if until else None,
        }
        logger.warning(f"OOC violation by user {user_id} in campaign {campaign_id}. Warning count: {warning_count}")
        return (True, warning_msg, should_ban)

    def _detect_ic_content(self, message: str, campaign_id: int) -> bool:
        """
        True when the message is in-character roleplay (a violation in an OOC room).

        Uses services.classifier (Laya / Jev / LLM prompt, per admin setting). Fails open:
        if no classifier works, nothing is flagged (never warn or ban on a guess).
        """
        from services.classifier import ClassifierUnavailable, classify_cached

        try:
            campaign_ctx = ooc_campaign_context(campaign_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"OOC check: could not load campaign {campaign_id}: {e}")
            return False
        if campaign_ctx is None:
            return False

        try:
            result = classify_cached(message, campaign_ctx)
        except ClassifierUnavailable as e:
            logger.error(f"OOC check: no classifier available, not flagging: {e}")
            return False
        self.last_classification = result
        verdict = result["ooc_violation"]
        if verdict["label"]:
            logger.info(
                f"IC content detected by {result['provider']} (P(in character)={verdict['score']}): {message[:50]}..."
            )
        return bool(verdict["label"])

    def _log_violation(self, user_id: int, campaign_id: int) -> int:
        """Log an OOC violation; return this user's warnings in this campaign (last 7 days)."""
        try:
            conn = _get_db()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ooc_violations (user_id, campaign_id) VALUES (%s, %s)",
                    (user_id, campaign_id),
                )
                cursor.execute(
                    """
                    SELECT COUNT(*) AS n FROM ooc_violations
                    WHERE user_id = %s AND campaign_id = %s
                      AND violated_at > NOW() - INTERVAL '7 days'
                    """,
                    (user_id, campaign_id),
                )
                warning_count = cursor.fetchone()['n']
                conn.commit()
                return warning_count
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error logging OOC violation: {e}")
            return 0

    def _issue_campaign_ban(self, user_id: int, campaign_id: int) -> datetime:
        """Ban the user from posting in this campaign (campaign_bans); returns the expiry."""
        until = datetime.now() + timedelta(hours=self.ban_duration_hours)
        try:
            conn = _get_db()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO campaign_bans (user_id, campaign_id, banned_until, reason, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (user_id, campaign_id) DO UPDATE
                    SET banned_until = GREATEST(campaign_bans.banned_until, EXCLUDED.banned_until),
                        reason = EXCLUDED.reason, created_at = NOW()
                    """,
                    (user_id, campaign_id, until,
                     "Repeated in-character posts in the OOC room (no in-character roleplay in OOC)."),
                )
                conn.commit()
            finally:
                conn.close()
            logger.warning(
                f"Issued {self.ban_duration_hours}h campaign ban to user {user_id} in campaign {campaign_id} for OOC violations"
            )
        except Exception as e:
            logger.error(f"Error issuing campaign ban: {e}")
        return until

    def check_user_ban(self, user_id: int, campaign_id: int) -> Tuple[bool, str]:
        """(is_banned, message) for posting in this campaign (campaign_bans only)."""
        try:
            conn = _get_db()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT banned_until, reason FROM campaign_bans WHERE user_id = %s AND campaign_id = %s",
                    (user_id, campaign_id),
                )
                row = cursor.fetchone()
            finally:
                conn.close()
            return campaign_ban_state(row)
        except Exception as e:
            logger.error(f"Error checking campaign ban: {e}")
            return (False, '')


def ooc_campaign_context(campaign_id: int) -> Optional[dict]:
    """Context the classifier gets for an OOC-room message (same dict for every caller, so
    the verdict cache in services.classifier is shared). None if the campaign is missing."""
    from services.rules_edition import edition_of, rules_edition_label

    conn = _get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, game_system, rules_edition FROM campaigns WHERE id = %s",
            (campaign_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "room": "OOC",
        "name": row['name'],
        "game_system": row['game_system'],
        "rules_label": rules_edition_label(edition_of(row)),
    }


def create_ooc_monitor(llm_service: Any = None) -> OOCMonitor:
    """Factory function to create OOC monitor instance"""
    return OOCMonitor(llm_service)

"""Shared payloads when a character's play is suspended by staff."""

CONTACT_HINT = (
    "Contact your Campaign Manager (chronicle owner) or a site Administrator "
    "for more information."
)

ALLOWED_REASON_CODES = frozenset(
    {"pending_downtime", "pending_more_information", "custom"}
)


def suspended_json(reason_code, message):
    return {
        "error": "Character play is suspended",
        "error_code": "character_suspended",
        "reason_code": reason_code,
        "message": (message or "").strip(),
        "contact_hint": CONTACT_HINT,
    }

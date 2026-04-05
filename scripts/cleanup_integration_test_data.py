#!/usr/bin/env python3
"""
Remove integration-test rows from PostgreSQL (tests/test_security_and_features.py).

Identifies test data by:
  - Email domain @test.local (tests register with *@test.local)
  - Usernames sec_pa_, sec_pb_, sec_adm_ plus exactly 10 hex chars
  - Campaign names Listed Chronicle % / Msg Chronicle %
  - Character names matching ^Nosferatu [0-9a-f]{10}$ (integration test PC name)

Run from repo root with DATABASE_TYPE=postgresql and DATABASE_* (or POSTGRES_*) set.

  Dry run (default):  python3 scripts/cleanup_integration_test_data.py
  Execute after review: python3 scripts/cleanup_integration_test_data.py --execute --yes

Does not reset ChromaDB / vector stores. Backup the DB before --execute.
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "backend"))

# Load .env before importing backend (which reads Config)
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass

os.environ.setdefault("DATABASE_TYPE", "postgresql")

from database import get_db  # noqa: E402


TEST_USER_PRED = """
    email LIKE %s OR username ~ %s
"""

TEST_USER_PARAMS = ("%@test.local", r"^sec_(pa|pb|adm)_[0-9a-f]{10}$")


def _pg_table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table,),
    )
    row = cursor.fetchone()
    return bool(row and (row.get("exists") if isinstance(row, dict) else row[0]))


def _delete_if_table(cursor, table: str, sql: str, params: tuple) -> int:
    if not _pg_table_exists(cursor, table):
        return 0
    cursor.execute(sql, params)
    return cursor.rowcount if cursor.rowcount is not None else 0


def preview(cursor, include_nosferatu_pattern: bool) -> None:
    tu = TEST_USER_PARAMS
    cursor.execute(
        f"""
        SELECT id, username, email, role, created_at
        FROM users
        WHERE {TEST_USER_PRED.strip()}
        ORDER BY id
        """,
        tu,
    )
    rows = cursor.fetchall()
    print(f"\n--- users matching test patterns ({len(rows)} rows) ---")
    for r in rows[:50]:
        print(dict(r) if hasattr(r, "keys") else r)
    if len(rows) > 50:
        print(f"... ({len(rows) - 50} more)")

    cursor.execute(
        """
        SELECT c.id, c.name, c.game_system, c.created_by, u.username AS creator_username
        FROM campaigns c
        LEFT JOIN users u ON u.id = c.created_by
        WHERE c.created_by IN (
            SELECT id FROM users WHERE """ + TEST_USER_PRED.strip() + """
        )
        OR c.name LIKE %s
        OR c.name LIKE %s
        ORDER BY c.id
        """,
        (*tu, "Listed Chronicle %", "Msg Chronicle %"),
    )
    crows = cursor.fetchall()
    print(f"\n--- campaigns matching test patterns ({len(crows)} rows) ---")
    for r in crows[:50]:
        print(dict(r) if hasattr(r, "keys") else r)
    if len(crows) > 50:
        print(f"... ({len(crows) - 50} more)")

    char_where = """
        u.id IN (SELECT id FROM users WHERE """ + TEST_USER_PRED.strip() + """)
    """
    params = list(tu)
    if include_nosferatu_pattern:
        char_where += " OR ch.name ~ %s"
        params.append(r"^Nosferatu [0-9a-f]{10}$")
    cursor.execute(
        f"""
        SELECT ch.id, ch.name, ch.user_id, ch.campaign_id, u.username, u.email
        FROM characters ch
        JOIN users u ON u.id = ch.user_id
        WHERE ({char_where})
        ORDER BY ch.id
        """,
        tuple(params),
    )
    chrows = cursor.fetchall()
    print(f"\n--- characters to delete ({len(chrows)} rows) ---")
    for r in chrows[:50]:
        print(dict(r) if hasattr(r, "keys") else r)
    if len(chrows) > 50:
        print(f"... ({len(chrows) - 50} more)")


def run_cleanup(cursor, include_nosferatu_pattern: bool) -> dict[str, int]:
    """
    Delete in an order safe for typical FKs. Uses subqueries on test-user predicate.
    Returns rowcounts for key steps (best-effort).
    """
    counts: dict[str, int] = {}
    tu = TEST_USER_PARAMS

    char_filter = (
        "user_id IN (SELECT id FROM users WHERE "
        + TEST_USER_PRED.strip()
        + ")"
    )
    char_params: list = list(tu)
    if include_nosferatu_pattern:
        char_filter += " OR name ~ %s"
        char_params.append(r"^Nosferatu [0-9a-f]{10}$")

    # 1) Clear active_character_id pointing at PCs we will remove
    cursor.execute(
        f"""
        UPDATE users SET active_character_id = NULL
        WHERE active_character_id IS NOT NULL
          AND active_character_id IN (
            SELECT id FROM characters WHERE ({char_filter})
          )
        """,
        tuple(char_params),
    )
    counts["users_active_character_nulled"] = cursor.rowcount or 0

    test_user_subq = (
        "SELECT id FROM users WHERE " + TEST_USER_PRED.strip()
    )

    # 2) Rows that reference users directly (before deleting users)
    counts["ai_interactions"] = _delete_if_table(
        cursor,
        "ai_interactions",
        f"DELETE FROM ai_interactions WHERE user_id IN ({test_user_subq})",
        tu,
    )
    counts["user_moderation_log"] = _delete_if_table(
        cursor,
        "user_moderation_log",
        f"""
        DELETE FROM user_moderation_log
        WHERE user_id IN ({test_user_subq}) OR admin_id IN ({test_user_subq})
        """,
        tu + tu,
    )
    counts["ooc_violations"] = _delete_if_table(
        cursor,
        "ooc_violations",
        f"DELETE FROM ooc_violations WHERE user_id IN ({test_user_subq})",
        tu,
    )
    counts["dice_rolls"] = _delete_if_table(
        cursor,
        "dice_rolls",
        f"DELETE FROM dice_rolls WHERE user_id IN ({test_user_subq})",
        tu,
    )
    counts["campaign_players"] = _delete_if_table(
        cursor,
        "campaign_players",
        f"DELETE FROM campaign_players WHERE user_id IN ({test_user_subq})",
        tu,
    )
    counts["dice_roll_templates"] = _delete_if_table(
        cursor,
        "dice_roll_templates",
        f"DELETE FROM dice_roll_templates WHERE created_by IN ({test_user_subq})",
        tu,
    )
    # character_moderation references characters and users(moderated_by)
    cm_sql = f"""
        DELETE FROM character_moderation
        WHERE moderated_by IN ({test_user_subq})
           OR character_id IN (SELECT id FROM characters WHERE ({char_filter}))
    """
    cm_params = tuple(tu) + tuple(char_params)
    counts["character_moderation"] = _delete_if_table(
        cursor, "character_moderation", cm_sql, cm_params
    )

    # 3) Characters (depends on campaigns/users; children often CASCADE)
    cursor.execute(
        f"DELETE FROM characters WHERE ({char_filter})",
        tuple(char_params),
    )
    counts["characters"] = cursor.rowcount or 0

    # 4) Campaigns created by test users or named in tests
    cursor.execute(
        f"""
        DELETE FROM campaigns
        WHERE created_by IN ({test_user_subq})
           OR name LIKE %s
           OR name LIKE %s
        """,
        (*tu, "Listed Chronicle %", "Msg Chronicle %"),
    )
    counts["campaigns"] = cursor.rowcount or 0

    counts["npcs"] = _delete_if_table(
        cursor,
        "npcs",
        f"DELETE FROM npcs WHERE created_by IN ({test_user_subq})",
        tu,
    )
    counts["location_deletion_log"] = _delete_if_table(
        cursor,
        "location_deletion_log",
        f"DELETE FROM location_deletion_log WHERE deleted_by IN ({test_user_subq})",
        tu,
    )

    # 5) Test users last
    cursor.execute(
        f"DELETE FROM users WHERE {TEST_USER_PRED.strip()}",
        tu,
    )
    counts["users"] = cursor.rowcount or 0

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete rows (default is dry-run preview only).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="With --execute, skip interactive confirmation.",
    )
    parser.add_argument(
        "--skip-nosferatu-pattern",
        action="store_true",
        help="Do not delete characters matching ^Nosferatu [0-9a-f]{10}$ unless owned by test users.",
    )
    args = parser.parse_args()

    if os.getenv("DATABASE_TYPE", "sqlite").lower() != "postgresql":
        print(
            "This cleanup targets PostgreSQL integration-test data. "
            "Set DATABASE_TYPE=postgresql and DATABASE_* credentials.",
            file=sys.stderr,
        )
        return 1

    include_nosferatu = not args.skip_nosferatu_pattern

    conn = get_db()
    try:
        cur = conn.cursor()
        preview(cur, include_nosferatu)
        if not args.execute:
            print(
                "\nDry run only. Re-run with --execute --yes after backup to apply deletes."
            )
            return 0

        if not args.yes:
            print(
                "\nRefusing to delete without --yes (or pass --yes to confirm).",
                file=sys.stderr,
            )
            return 2

        cur.execute("BEGIN")
        try:
            counts = run_cleanup(cur, include_nosferatu)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

        print("\n--- deleted rowcounts (best-effort) ---")
        for k, v in counts.items():
            print(f"  {k}: {v}")
        print("Done.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

# PostgreSQL: identify and remove integration-test data

This runbook helps you **inspect** rows that match **known test patterns** from the automated suite ([`tests/test_security_and_features.py`](../tests/test_security_and_features.py), [`tests/test_campaign_membership.py`](../tests/test_campaign_membership.py)) and similar manual runs, then **delete only those rows** while keeping real players.

**Automated cleanup:** [`scripts/cleanup_integration_test_data.py`](../scripts/cleanup_integration_test_data.py) (dry run by default; `--execute --yes` applies deletes). Wrapper: [`scripts/cleanup_test_data.sh`](../scripts/cleanup_test_data.sh). Campaign-membership tests register `cm_pa_*` / `cm_pb_*` with emails `*@test.local` — the script removes those the same way as `sec_*` rows.

**It does not add an `is_test` column** — identification is by **username / email / campaign name / character name** patterns. **Review every `SELECT` result** before running `DELETE`.

**Not test data:** The app may create an internal **archive** user when staff use *delete account (preserve chats)*. That account keeps in-character message rows and related history valid under foreign keys. Do **not** treat it as `sec_*` / `@test.local` noise or delete it unless you fully understand the impact (see `docs/CHANGELOG.md` preserve-chat deletion notes).

---

## 1. Where test data comes from

The security integration tests register **three users** per run with a random **10-character hex suffix** (`uuid.uuid4().hex[:10]`):

| Pattern | Example | Notes |
|--------|---------|--------|
| Player A username | `sec_pa_<suffix>` | |
| Player B username | `sec_pb_<suffix>` | |
| Admin username | `sec_adm_<suffix>` | Gets `role = admin` via invite `TEST-ADMIN` |
| Email | `pa_<suffix>@test.local`, `pb_<suffix>@test.local`, `adm_<suffix>@test.local` | **`@test.local` is the strongest signal** — real accounts should not use this domain. |
| Password | `TestPass123!` | Same for all three in tests |

Campaigns created in tests:

- `Listed Chronicle <suffix>` — discover/join test  
- `Msg Chronicle <suffix>` — messages / poster_role test  

Characters:

- Name `Nosferatu <suffix>` — created in the messages test (vampire, same suffix).

**If you see “extra” Nosferatu rows**, they are often from repeated test runs (new suffix each run) or manual API calls using the same naming.

[`tests/test_campaign_membership.py`](../tests/test_campaign_membership.py) registers **`cm_pa_<suffix>`** / **`cm_pb_<suffix>`** with emails **`pa_<suffix>@test.local`** / **`pb_<suffix>@test.local`**. The username pattern differs from `sec_pa_*`, but **`DELETE` / cleanup by `%@test.local`** still removes these accounts when you use the automated script or the SQL in this doc.

---

## 2. Connect to PostgreSQL

From the **repository root**, with Docker services up (`docker compose up -d`):

```bash
# Load credentials from .env without sourcing the whole file (avoids LOG_FORMAT etc. breaking bash)
export $(grep -E '^(POSTGRES_USER|POSTGRES_DB|POSTGRES_PASSWORD)=' .env | xargs)

docker compose exec -T postgresql psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"
```

Or from the host with `psql` installed:

```bash
export $(grep -E '^(DATABASE_HOST|DATABASE_PORT|DATABASE_NAME|DATABASE_USER|DATABASE_PASSWORD)=' .env | xargs)
PGPASSWORD="$DATABASE_PASSWORD" psql -h "$DATABASE_HOST" -p "${DATABASE_PORT:-5432}" -U "$DATABASE_USER" -d "$DATABASE_NAME"
```

---

## 3. Identification queries (read-only)

Run these and **save the output** before any delete. Adjust limits if needed.

**3.1 — Users that match test patterns**

```sql
-- Strong: emails used only by the integration test register flow
SELECT id, username, email, role, created_at
FROM users
WHERE email LIKE '%@test.local'
   OR username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
ORDER BY id;
```

**3.2 — Campaigns tied to those users or obvious test names**

```sql
SELECT c.id, c.name, c.game_system, c.created_by, u.username AS creator_username
FROM campaigns c
LEFT JOIN users u ON u.id = c.created_by
WHERE c.created_by IN (
    SELECT id FROM users
    WHERE email LIKE '%@test.local'
       OR username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
)
OR c.name LIKE 'Listed Chronicle %'
OR c.name LIKE 'Msg Chronicle %'
ORDER BY c.id;
```

**3.3 — Characters owned by test users or named like the test character**

```sql
SELECT ch.id, ch.name, ch.user_id, ch.campaign_id, u.username, u.email
FROM characters ch
JOIN users u ON u.id = ch.user_id
WHERE u.email LIKE '%@test.local'
   OR u.username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
   OR (ch.name ~ '^Nosferatu [0-9a-f]{10}$' AND u.email LIKE '%@test.local')
ORDER BY ch.id;
```

**3.4 — Clear `active_character_id` pointing at test PCs**

```sql
SELECT id, username, active_character_id
FROM users
WHERE active_character_id IS NOT NULL
  AND active_character_id IN (
    SELECT ch.id FROM characters ch
    JOIN users u ON u.id = ch.user_id
    WHERE u.email LIKE '%@test.local'
       OR u.username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
  );
```

---

## 4. Cleanup procedure (destructive — use a transaction)

**Prerequisites**

1. **Backup** the database (e.g. `pg_dump`) or snapshot the volume.
2. **Stop** other writers if possible (optional).
3. Run during maintenance.

**Recommended order** (respects typical FKs; your schema may include extra tables — if `DELETE` fails, read the error and delete dependent rows first or rely on `ON DELETE CASCADE` where present):

```sql
BEGIN;

-- 4a) Clear active character pointers to rows we are about to remove
UPDATE users SET active_character_id = NULL
WHERE active_character_id IN (
  SELECT ch.id FROM characters ch
  JOIN users u ON u.id = ch.user_id
  WHERE u.email LIKE '%@test.local'
     OR u.username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
);

-- 4b) Test-user IDs (reuse in next statements)
-- Optionally: CREATE TEMP TABLE test_user_ids AS SELECT id FROM users WHERE ... ;

-- 4c) Delete characters owned by test users (adjust if you use a stricter CTE)
DELETE FROM characters
WHERE user_id IN (
  SELECT id FROM users
  WHERE email LIKE '%@test.local'
     OR username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
);

-- 4d) Delete campaigns created in tests OR leftover by name (review SELECT first!)
DELETE FROM campaigns
WHERE created_by IN (
  SELECT id FROM users
  WHERE email LIKE '%@test.local'
     OR username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$'
)
OR name LIKE 'Listed Chronicle %'
OR name LIKE 'Msg Chronicle %';

-- 4e) Delete test users
DELETE FROM users
WHERE email LIKE '%@test.local'
   OR username ~ '^sec_(pa|pb|adm)_[0-9a-f]{10}$';

-- If everything looks right:
COMMIT;
-- If not:
-- ROLLBACK;
```

**Notes**

- If **`DELETE FROM users` fails** because another table references a test user without `ON DELETE CASCADE`, delete or null those rows first (e.g. `ai_interactions`, invites, etc.) or narrow scope to only users you are sure are isolated.
- **`OR name LIKE 'Listed Chronicle %'`** could match a real chronicle if someone copied that exact prefix — **remove those two `OR` lines** if you only want creator-based cleanup.
- **Real accounts must not use `@test.local`** — document that as a team rule.

---

## 5. Files in this repo

| File | Purpose |
|------|---------|
| [`scripts/sql/test_data_candidates.sql`](../scripts/sql/test_data_candidates.sql) | Copy-paste `SELECT` blocks for `psql` |
| [`scripts/cleanup_integration_test_data.py`](../scripts/cleanup_integration_test_data.py) | List or delete integration-test rows (see `--help`) |
| [`scripts/cleanup_test_data.sh`](../scripts/cleanup_test_data.sh) | Loads env safely; runs the cleanup script |
| This doc | Procedure and safety notes |

---

## 6. What this does *not* do

- Does not wipe **ChromaDB** / vector data — see ops docs if you need to reset RAG per campaign.
- Does not remove users who **only** share a display name with tests but use a **real** email domain.
- Does not replace **version** strings or commit anything — operational only.

---

## 7. Re-run tests after cleanup

Integration tests expect PostgreSQL and will **create new** `sec_*` users each run:

```bash
./scripts/run_security_tests.sh
```

See [`docs/SECURITY_AND_TESTING.md`](SECURITY_AND_TESTING.md).

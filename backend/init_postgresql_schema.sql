-- =============================================================================
-- ShadowRealms AI - PostgreSQL schema (fresh install)
--
-- Reconstructed from code on 2026-10-04. The original file was never committed
-- and was lost. Column sets, types and constraints were derived from the SQL
-- in backend/ (routes, services, database.py ensure_* helpers), with the SQLite
-- definitions in database.py and the docs as secondary reference.
--
-- Loaded by docker-compose into /docker-entrypoint-initdb.d/01-schema.sql, so
-- it only runs against an EMPTY data volume. After that, backend migrate_db()
-- runs the ensure_* helpers (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT
-- EXISTS); every column they add is already defined here with the same type,
-- so they are no-ops on a fresh install.
--
-- Conventions (matching what the PostgreSQL code paths send):
--   * flags are BOOLEAN (queries use = TRUE / IS TRUE and pass Python bools),
--     except dice_roll_templates.is_system which is INTEGER (code: is_system = 1)
--   * JSON payloads are TEXT (code json.dumps()/json.loads() them itself)
--   * timestamps are TIMESTAMP WITHOUT TIME ZONE (code writes naive datetimes)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                                SERIAL PRIMARY KEY,
    username                          TEXT NOT NULL UNIQUE,
    email                             TEXT NOT NULL UNIQUE,
    password_hash                     TEXT NOT NULL,
    role                              TEXT NOT NULL DEFAULT 'player',   -- 'admin' | 'helper' | 'player'
    is_active                         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login                        TIMESTAMP,
    -- profile
    display_timezone                  TEXT,                              -- IANA name
    player_avatar_url                 TEXT,
    active_character_id               INTEGER,                           -- FK added after characters
    -- admin grants / restrictions
    allow_multi_campaign_play         BOOLEAN NOT NULL DEFAULT FALSE,
    self_switch_playing_character     BOOLEAN NOT NULL DEFAULT FALSE,
    restrict_self_join_new_chronicles BOOLEAN NOT NULL DEFAULT FALSE,
    -- admin bans (routes/admin.py)
    ban_type                          TEXT,                              -- 'temporary' | 'permanent'
    ban_until                         TIMESTAMP,
    ban_reason                        TEXT,
    banned_by                         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    banned_at                         TIMESTAMP,
    -- automatic OOC-abuse temp ban (services/ooc_monitor.py uses this name)
    banned_until                      TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- campaigns (chronicles)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaigns (
    id                    SERIAL PRIMARY KEY,
    name                  TEXT NOT NULL,
    description           TEXT,
    game_system           TEXT NOT NULL DEFAULT 'd20',
    status                TEXT NOT NULL DEFAULT 'active',
    max_players           INTEGER DEFAULT 6,
    created_by            INTEGER NOT NULL REFERENCES users(id),
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    listing_visibility    TEXT NOT NULL DEFAULT 'private',              -- 'private' | 'listed'
    accepting_players     BOOLEAN NOT NULL DEFAULT FALSE,
    admin_inactive_reason TEXT,
    admin_inactive_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_campaigns_created_by ON campaigns(created_by);
CREATE INDEX IF NOT EXISTS idx_campaigns_listing ON campaigns(is_active, listing_visibility, accepting_players);

-- -----------------------------------------------------------------------------
-- locations (rooms inside a campaign; type 'ooc' = OOC lobby)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    id                  SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    type                TEXT NOT NULL DEFAULT 'custom',
    description         TEXT,
    created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    is_open             BOOLEAN NOT NULL DEFAULT TRUE,
    closure_reason      TEXT,
    dice_leniency_floor INTEGER                                          -- NULL = normal RNG
);

CREATE INDEX IF NOT EXISTS idx_locations_campaign ON locations(campaign_id, is_active);

-- -----------------------------------------------------------------------------
-- characters
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS characters (
    id                          SERIAL PRIMARY KEY,
    name                        TEXT NOT NULL,
    user_id                     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id                 INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    system_type                 TEXT NOT NULL DEFAULT 'd20',
    attributes                  TEXT NOT NULL DEFAULT '{}',
    skills                      TEXT NOT NULL DEFAULT '{}',
    background                  TEXT NOT NULL DEFAULT '',
    merits_flaws                TEXT NOT NULL DEFAULT '{}',
    wod_meta                    TEXT NOT NULL DEFAULT '{}',
    portrait_url                TEXT,
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    is_npc                      BOOLEAN NOT NULL DEFAULT FALSE,
    sheet_locked                BOOLEAN NOT NULL DEFAULT FALSE,
    -- legacy d20 fields still read by routes/ai.py character context
    character_class             TEXT,
    level                       INTEGER DEFAULT 1,
    character_data              TEXT,
    -- location tracking (routes/locations.py enter/leave)
    current_location_id         INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    last_location_id            INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    -- admin play suspension
    play_suspended              BOOLEAN NOT NULL DEFAULT FALSE,
    play_suspension_reason_code TEXT,
    play_suspension_message     TEXT,
    play_suspended_at           TIMESTAMP,
    play_suspended_by           INTEGER REFERENCES users(id) ON DELETE SET NULL,
    play_suspension_updated_at  TIMESTAMP,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_characters_user ON characters(user_id);
CREATE INDEX IF NOT EXISTS idx_characters_campaign ON characters(campaign_id);

-- users.active_character_id -> characters (circular, so added afterwards)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_active_character_id_fkey'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT users_active_character_id_fkey
            FOREIGN KEY (active_character_id) REFERENCES characters(id) ON DELETE SET NULL;
    END IF;
END $$;

-- -----------------------------------------------------------------------------
-- campaign_players (membership; ON CONFLICT (campaign_id, user_id) in code)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_players (
    id                  SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role                TEXT DEFAULT 'player',                           -- 'owner' | 'player'
    joined_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active_character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    UNIQUE (campaign_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_campaign_players_user ON campaign_players(user_id);

-- -----------------------------------------------------------------------------
-- character_locations (presence history)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS character_locations (
    id           SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    location_id  INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    entered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entry_reason TEXT,
    exited_at    TIMESTAMP,
    exit_reason  TEXT
);

CREATE INDEX IF NOT EXISTS idx_character_locations_char ON character_locations(character_id, exited_at);
CREATE INDEX IF NOT EXISTS idx_character_locations_loc ON character_locations(location_id, exited_at);

-- -----------------------------------------------------------------------------
-- messages (chat)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id              SERIAL PRIMARY KEY,
    campaign_id     INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    location_id     INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id    INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    message_type    TEXT NOT NULL DEFAULT 'ic',                          -- 'ic' | 'ooc' | 'system' ...
    content         TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',                        -- 'user' | 'assistant' ...
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ai_message_kind TEXT,
    speaker_mode    TEXT                                                 -- 'character' | 'player' | 'staff'
);

CREATE INDEX IF NOT EXISTS idx_messages_location ON messages(campaign_id, location_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_location_id ON messages(campaign_id, location_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);

-- -----------------------------------------------------------------------------
-- location_reads (unread tracking; same shape as routes/messages.py creates)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS location_reads (
    id                   SERIAL PRIMARY KEY,
    character_id         INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    location_id          INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    last_read_message_id INTEGER,
    last_read_at         TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (character_id, location_id)
);

-- -----------------------------------------------------------------------------
-- AI tables
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_interactions (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id),
    campaign_id      INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
    interaction_type TEXT NOT NULL,
    prompt           TEXT NOT NULL,
    response         TEXT NOT NULL,
    performance_mode TEXT DEFAULT 'medium',
    tokens_used      INTEGER,
    response_time_ms INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_user ON ai_interactions(user_id);

CREATE TABLE IF NOT EXISTS ai_memory (
    id          SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL,
    content     TEXT NOT NULL,
    context     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_memory_campaign ON ai_memory(campaign_id, created_at DESC);

-- Same definition as services/ai_runtime_settings.ensure_app_settings_table
CREATE TABLE IF NOT EXISTS app_settings (
    key        VARCHAR(255) PRIMARY KEY,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- Moderation / audit
-- -----------------------------------------------------------------------------
-- No FKs on purpose: audit rows must never block a write (actions can be
-- logged for ids that are later deleted; delete code reassigns them anyway).
CREATE TABLE IF NOT EXISTS user_moderation_log (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER,                    -- subject of the action
    admin_id   INTEGER,                    -- actor
    action     TEXT NOT NULL,
    details    TEXT,                       -- JSON string
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_moderation_log_user ON user_moderation_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_moderation_log_created ON user_moderation_log(created_at DESC);

CREATE TABLE IF NOT EXISTS character_moderation (
    id                SERIAL PRIMARY KEY,
    character_id      INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    action            TEXT NOT NULL,       -- 'convert_to_npc' | 'kill'
    death_type        TEXT,                -- 'soft' | 'mid' | 'horrible'
    death_description TEXT,
    moderated_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    moderated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_character_moderation_char ON character_moderation(character_id, moderated_at DESC);

CREATE TABLE IF NOT EXISTS ooc_violations (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    violated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ooc_violations_lookup ON ooc_violations(user_id, campaign_id, violated_at);

-- Same definition as database.ensure_character_downtime_requests_table
CREATE TABLE IF NOT EXISTS character_downtime_requests (
    id           BIGSERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    campaign_id  INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    request_text TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',   -- 'pending' | 'approved' | 'rejected'
    admin_reason TEXT,
    resolved_at  TIMESTAMP,
    resolved_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_downtime_user ON character_downtime_requests(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_downtime_status ON character_downtime_requests(status);

CREATE TABLE IF NOT EXISTS location_deletion_log (
    id                   SERIAL PRIMARY KEY,
    location_id          INTEGER NOT NULL,                       -- no FK: kept as history
    campaign_id          INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    location_name        TEXT NOT NULL,
    location_type        TEXT NOT NULL,
    location_description TEXT,
    deleted_by           INTEGER NOT NULL REFERENCES users(id),  -- reassigned on account delete
    deleted_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count        INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_deletion_log_campaign ON location_deletion_log(campaign_id, deleted_at DESC);

-- -----------------------------------------------------------------------------
-- Dice (same definitions as database.ensure_dice_tables, so it keeps them)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dice_roll_templates (
    id                 BIGSERIAL PRIMARY KEY,
    campaign_id        INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    name               TEXT NOT NULL DEFAULT '',
    description        TEXT,
    dice_pool_formula  TEXT,
    default_difficulty INTEGER DEFAULT 6,
    created_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    is_system          INTEGER NOT NULL DEFAULT 0,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dice_roll_templates_campaign ON dice_roll_templates(campaign_id);

CREATE TABLE IF NOT EXISTS dice_rolls (
    id                 BIGSERIAL PRIMARY KEY,
    campaign_id        INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    location_id        INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id       INTEGER REFERENCES characters(id) ON DELETE SET NULL,
    roll_type          TEXT NOT NULL,
    action_description TEXT NOT NULL,
    dice_pool          INTEGER NOT NULL,
    difficulty         INTEGER NOT NULL,
    results            TEXT NOT NULL,
    successes          INTEGER NOT NULL,
    is_botch           BOOLEAN NOT NULL DEFAULT FALSE,
    is_critical        BOOLEAN NOT NULL DEFAULT FALSE,
    modifiers          TEXT,
    rolled_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dice_rolls_location ON dice_rolls(campaign_id, location_id, rolled_at DESC);

-- -----------------------------------------------------------------------------
-- NPCs, combat, relationships, location graph (read by routes/ai.py context)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS npcs (
    id          SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    type        TEXT,
    description TEXT,
    personality TEXT,
    faction     TEXT,
    npc_data    TEXT,                                            -- JSON string
    created_by  INTEGER NOT NULL REFERENCES users(id),           -- reassigned on account delete
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_npcs_location ON npcs(campaign_id, location_id);

CREATE TABLE IF NOT EXISTS npc_messages (
    id          SERIAL PRIMARY KEY,
    npc_id      INTEGER NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    context     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_npc_messages ON npc_messages(npc_id, created_at DESC);

CREATE TABLE IF NOT EXISTS combat_encounters (
    id               SERIAL PRIMARY KEY,
    campaign_id      INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    location_id      INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    status           TEXT NOT NULL DEFAULT 'active',
    initiative_order TEXT,                                       -- JSON string
    round_number     INTEGER DEFAULT 1,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at         TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_combat_encounters_location ON combat_encounters(campaign_id, location_id, status);

CREATE TABLE IF NOT EXISTS combat_participants (
    id           SERIAL PRIMARY KEY,
    encounter_id INTEGER NOT NULL REFERENCES combat_encounters(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    npc_id       INTEGER REFERENCES npcs(id) ON DELETE CASCADE,
    initiative   INTEGER DEFAULT 0,
    current_hp   INTEGER,
    max_hp       INTEGER,
    conditions   TEXT                                            -- JSON string
);

CREATE INDEX IF NOT EXISTS idx_combat_participants_encounter ON combat_participants(encounter_id);

CREATE TABLE IF NOT EXISTS relationships (
    id                SERIAL PRIMARY KEY,
    campaign_id       INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    entity1_type      TEXT NOT NULL,                             -- 'character' | 'npc' ...
    entity1_id        INTEGER NOT NULL,
    entity2_type      TEXT NOT NULL,
    entity2_id        INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,
    strength          INTEGER DEFAULT 0,
    notes             TEXT,
    last_interaction  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relationships ON relationships(campaign_id, entity1_type, entity1_id);

CREATE TABLE IF NOT EXISTS location_connections (
    id               SERIAL PRIMARY KEY,
    location1_id     INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    location2_id     INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    connection_type  TEXT DEFAULT 'path',
    description      TEXT,
    is_bidirectional BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_location_connections_1 ON location_connections(location1_id);
CREATE INDEX IF NOT EXISTS idx_location_connections_2 ON location_connections(location2_id);

COMMIT;

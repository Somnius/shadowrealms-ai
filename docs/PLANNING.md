# Planning & Phase Documentation

**Last Updated**: 2026-04-03  
**Version**: 0.7.17

This document consolidates planning documentation and phase summaries.

---

## Table of Contents

1. [Overview](#overview)
2. [Phase model (refreshed)](#phase-model-refreshed)
3. [Delivered through v0.7.17](#delivered-through-v0717)
4. [Next priorities](#next-priorities)
5. [Phase 3B specification (north star)](#phase-3b-specification-north-star)

---

## Overview

**Phase 2** (RAG, ChromaDB, books) and **Phase 3A** (auth, React shell, campaigns, themes) are **complete**. **Phase 3B** is the ongoing “tabletop platform” track.

Older text in this file claimed locations were **hardcoded** and APIs **missing**. That is **obsolete**: the app now uses **PostgreSQL**, **REST routes** for locations, characters, messages, dice, and AI, and a **polling-based** chat UI. The long sections below are a **north-star** spec; trust the [Delivered](#delivered-through-v0717) section and [CHANGELOG](CHANGELOG.md) for what actually ships.

---

## Phase model (refreshed)

| Track | Scope | Status |
|-------|--------|--------|
| **Phase 2** | RAG, vector memory, rule-book pipeline | Complete |
| **Phase 3A** | Login/register, dashboard, campaign CRUD, gothic UI, admin shell | Complete |
| **3B — Foundation** | Security helpers, Jest tests, Postgres migration, Docker stack, `docker-up.sh` | Complete |
| **3B — Core loop (shipped)** | DB **locations** (CRUD, suggest/batch, enter/leave), **characters** (CRUD + selection + portraits), **location-scoped messages** + read state, **OOC AI moderation**, **IC storyteller**, **campaign stats**, **WoD dice** (sidebar + `/ai` + overlay + hidden rolls), **message timestamps** | **Delivered** (through v0.7.16) |
| **3B — Next** | **WebSockets** (or SSE) for live chat, typing/presence, notification layer, multi-step character wizard / sheet depth, campaign setting UX polish | **In planning** |

Chat uses **HTTP polling** today; there is **no** WebSocket server in the repository yet.

---

## Delivered through v0.7.17

- **v0.7.17 (docs)**: Version-stamp alignment across the repo; release notes emphasize **next milestone** readiness for **users**, **players**, and **characters** before deeper Phase **3B** features (see `docs/CHANGELOG.md` `[0.7.17]`).
- **Stack**: Docker Compose; PostgreSQL; backend `backend/routes/*` for campaigns, locations, characters, messages, dice, AI, admin.
- **Locations**: `locations.py` — list/create/update/delete, AI suggest/batch, enter/leave; OOC behavior documented in `AI_SYSTEMS.md`.
- **Characters**: `characters.py` — campaign character lists, CRUD; **WoD wizard** (vampire/werewolf/mage), `wod_meta`, **7/5/3** attributes, `sheet_locked`, `is_active`; **Nature/Demeanor** presets + custom text; stricter create payload validation; portraits on messages where applicable.
- **Users / profile**: `users.active_character_id`, `player_avatar_url`; extended **`GET /api/users/me`**; dashboard **filter by active PC** (`for_active_character`).
- **Campaigns**: **Discover/join** (`listing_visibility`, `accepting_players`); **play suspension** flags on characters; admin **membership** overrides and user **debug** tooling; **one locked PC** per player unless `allow_multi_campaign_play`.
- **Messages**: Per-location threads, read-state, dice marker kinds (`dice_animation*`, `dice_roll*`, hidden variants filtered by role); **`player_avatar_url`** (OOC vs IC avatars).
- **AI**: `POST /api/ai/chat`, `POST /api/ai/slash` for admin `/ai` tools; OOC moderation path.
- **Dice**: `dice.py` + WoD services; UI theatre and storyteller-only visibility (`SimpleApp.js`, `messages.py` filters).
- **Downtime**: `character_downtime_requests` + admin review UI.
- **Data layout**: Local WoD bulk archive **`data/World_of_Darkness.tar`** (gitignored); helper `scripts/move-wod-archive-to-data.sh` (`books/README.md`).
- **Docs**: `CHANGELOG.md`, `dice-old-wod.md`, `character-creation-world-of-darkness.md`, `DOCKER_ENV_SETUP.md` (incl. `docker-up.sh`).

---

## Next priorities

Use this as the **default backlog** for continuing the project (re-order as needed):

1. **Real-time layer** — WebSocket (preferred) or SSE; room/channel per location; backoff/reconnect; optional: reduce polling once stable.
2. **Presence & typing** — Only after (1); show “who is here” / typing in location.
3. **Notifications** — In-app toasts/modals for ST actions, announcements, mentions.
4. **Character depth** — Physical/mental status, equipment/relationships JSON, guided creation wizard (see schema ideas in the north-star sections below).
5. **Campaign richness** — Structured setting fields + AI location flows (partial: suggest/batch routes exist).
6. **Quality** — E2E coverage for login → campaign → chat → roll; load notes for concurrent users.

---

## Phase 3B specification (north star)

The sections below (from the next heading onward) are the **original Phase 3B design**: target UX, schema ideas, week-style outline. They are **not** a literal status report. **Implemented vs planned** gaps include: WebSockets, full notification matrix, full character wizard, several `/api/users/me/...` route shapes (actual routes live under `/api/campaigns/...` and `/api/characters/...` — verify in code before implementing clients).

---

## 🚀 Phase 3B: Advanced Campaign & Character Systems

**Status:** 🚧 IN PROGRESS — **core loop shipped** (locations, characters, chat, dice, AI); **WebSockets & advanced UX** not yet  
**Version:** 0.7.17  
**Start Date:** 2025-10-24

### Overview
Phase 3B extends Phase 3A with **playable campaigns**: database-backed **locations** and **characters**, **location-scoped chat** (polling), **WoD dice**, **AI storyteller** and **OOC moderation**, and **admin `/ai` tools**. **Real-time** delivery (WebSockets), a full **notification** layer, and the **multi-step character wizard** described below remain **aspirational** until implemented.

---

### 🔐 Security & Testing (Week 1) - ✅ COMPLETE

#### Security Utilities Created
**File:** `frontend/src/utils/security.js` (400+ lines)

**Input Sanitization:**
- `sanitizeHtml()` - XSS prevention with HTML entity encoding
- `sanitizeUrl()` - URL-safe encoding
- `sanitizeName()` - Character/campaign names (100 char limit)
- `sanitizeDescription()` - Campaign settings (10k char limit, script removal)
- `sanitizeSearchQuery()` - SQL injection prevention (200 char limit)

**Validation:**
- `isValidEmail()` - RFC-compliant email validation
- `isValidUsername()` - 3-20 chars, alphanumeric + underscore/hyphen
- `validatePassword()` - 8+ chars, uppercase, lowercase, number
- `validateChatMessage()` - Max 2000 chars, sanitized
- `validateCampaignData()` - Complete campaign form validation

**Security Features:**
- `RateLimiter` class - Client-side spam prevention
- `secureStorage` - Obfuscated localStorage (Base64)
- `generateCSRFToken()` - Crypto-random tokens
- `detectClickjacking()` - Iframe detection

#### Test Suite Created
**Files:** 
- `frontend/src/utils/__tests__/security.test.js` (350+ lines)
- `frontend/src/__tests__/integration/userFlow.test.js` (280+ lines)

**Test Coverage:**
- 40+ unit tests for security functions
- XSS injection attempt tests
- SQL injection prevention tests
- Rate limiting verification
- Authentication flow tests
- Campaign management tests
- Navigation tests
- Security tests (token storage, logout)

---

### 📍 Location System — **delivered** (API + UI); optional extras below remain north-star

#### Database Schema
```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'ooc', 'tavern', 'dungeon', 'city', 'custom'
    description TEXT,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

#### Key Features
1. **Auto-create OOC Room**: Every campaign starts with "Out of Character" lobby
2. **AI-Suggested Locations**: Based on campaign setting description
3. **Dynamic Creation**: Admins add/edit/remove locations during gameplay
4. **Entry Requirements**: Players must provide reason when entering locations:
   - "Just visited"
   - "Based on previous actions"
   - "Background tasks"
   - "Custom" (free-form text)

#### OOC Room Special Rules
- Players talk as themselves (not as characters)
- Online status visibility (unless user profile set to invisible)
- Temporary visits allowed while in another location
- **AI Monitoring**:
  - Warns players about campaign-relevant spoilers in OOC
  - Reports repeated OOC abuse to admin
  - Does NOT reveal other characters' secrets/abilities

#### Admin Location Powers
- Move/remove characters from locations with logged reasons
- Reasons visible to affected player + logged for AI context
- System messages appear in old/new locations
- Immediate modal notification to affected player

---

### 👤 Character Selection & Creation — **partially delivered** (CRUD + selection + portraits); wizard/status depth below is mostly north-star

#### Extended Character Schema
```sql
ALTER TABLE characters ADD COLUMN physical_status TEXT; -- dropdown + custom
ALTER TABLE characters ADD COLUMN mental_status TEXT;   -- dropdown + custom
ALTER TABLE characters ADD COLUMN current_location_id INTEGER;
ALTER TABLE characters ADD COLUMN last_location_id INTEGER;
ALTER TABLE characters ADD COLUMN equipment TEXT;       -- JSON array
ALTER TABLE characters ADD COLUMN relationships TEXT;    -- JSON object
ALTER TABLE characters ADD COLUMN background TEXT;
ALTER TABLE characters ADD COLUMN description TEXT;
```

#### Status Tracking

**Physical Status (Dropdown + Custom):**
- None / Healthy
- Minor Injury (scratches, bruises)
- Major Injury (broken limb, severe wounds)
- Critical Condition (near death)
- Custom (admin/AI can set any text)

**Mental Status (Dropdown + Custom):**
- Stable
- Anxious
- Thoughtful
- Happy
- Unhappy
- Traumatized
- Inspired
- Custom (based on last location events)

#### Character Selection Flow
1. **Player enters campaign**
2. **System displays previous characters:**
   - Name, game system
   - Physical status (icon + color)
   - Mental status (based on last location)
   - Last played date
3. **Options:**
   - Select existing character → Enter campaign
   - Create new character → Show BIG warning modal

#### Character Creation Warning
```
⚠️ CREATING A NEW CHARACTER

This will NOT reset your other characters' progress.
You must complete the ENTIRE character creation process.
If you leave before finishing, your character will NOT be saved.

Are you sure you want to create a new character?
[Cancel] [Yes, Create Character]
```

#### Character Creation Process

**Step 1: Character Type**
- Based on campaign game system
- **Vampire**: Full Vampire / Ghoul / Human
- **Mage**: Awakened Mage / Human with knowledge / Plain Human
- **Werewolf**: Garou / Human with enhanced instincts / Plain Human

**Steps 2-N: System-Specific Stats**
- Game-system appropriate fields
- **AI Assistance Box** (side panel):
  - "For this step, admins frequently do X. Would you like suggestions?"
  - Pagination-style interaction
  - **"Check with AI" button** at each step
  - AI validates against campaign setting

**Final Step: Background & Equipment**
- Background story (AI-assisted narrative)
- Physical description
- Relationships (who character knows, how they met)
- Starting equipment (wallet, glasses, weapons, tools, etc.)
- **"Check with AI" button** for full validation:
  - Setting consistency check
  - Lore accuracy validation
  - Balance suggestions
  - Rule compliance

---

### 💬 Real-Time Chat System (Week 3) — **not implemented**; production uses **HTTP polling** + REST messages

#### Database Schema
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER,
    message TEXT NOT NULL,
    message_type TEXT NOT NULL, -- 'ic', 'ooc', 'system', 'action', 'dice'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);

CREATE TABLE character_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entry_reason TEXT, -- Why character entered this location
    exit_reason TEXT,
    exited_at TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);
```

#### Message Types
- **IC** (In Character): Normal roleplay messages
- **OOC**: Out of character discussion (only in OOC room)
- **System**: Automated notifications (player joined/left)
- **Action**: `/me` style actions (e.g., "/me draws sword")
- **Dice**: Automated dice roll results

#### WebSocket Features
- Real-time message delivery (<1s latency)
- Room-based subscriptions (per location)
- Typing indicators
- Online status updates
- Auto-reconnection on disconnect
- Heartbeat/ping-pong for connection health

#### Character Presence Display
- **Format:** "John (as Marcus the Vampire) is here"
- **Right sidebar** shows character list per location with status
- **Cannot be in multiple locations** (except OOC temporary visit)
- **Auto-Disconnect System:**
  - After 30min inactivity + browser inactive status
  - Character marked as "Disconnected"
  - On return: Auto-resume to previous location
  - Message: "You have been resumed to [Location] due to disconnection"

---

### 🏰 Enhanced Campaign Management (Week 1)

#### Extended Campaign Schema
```sql
ALTER TABLE campaigns ADD COLUMN setting_description TEXT;
ALTER TABLE campaigns ADD COLUMN setting_genre TEXT;
ALTER TABLE campaigns ADD COLUMN setting_era TEXT;
ALTER TABLE campaigns ADD COLUMN setting_location TEXT;
ALTER TABLE campaigns ADD COLUMN setting_tone TEXT;
ALTER TABLE campaigns ADD COLUMN setting_themes TEXT;
ALTER TABLE campaigns ADD COLUMN admin_notes TEXT; -- Private, admin-only
```

#### Campaign Creation Flow

**Step 1: Basic Information**
- Name, Description
- Game System (Vampire, Werewolf, Mage, D&D, etc.)

**Step 2: Setting Description**
Detailed narrative format (example: "Ashes of the Aegean"):
```
Setting:
[Detailed world description - time period, location, atmosphere]

Premise:
[Main conflict, power dynamics, current state]

Tone:
[Dark, Political, Mythic, etc.]

Player Hook:
[Why players are involved, their role]

Themes:
[Core themes of the campaign]
```

**Step 3: Structured Fields**
- Genre (Urban Gothic, High Fantasy, Cyberpunk, etc.)
- Era (Modern 2025, Medieval 1450, Future 2150, etc.)
- Location (Athens Greece, Forgotten Realms, Mars Colony, etc.)
- Tone (Dark/Light, Serious/Humorous, Political/Action, etc.)
- Themes (Decay, Survival, Heroism, Corruption, etc.)

**Step 4: AI-Assisted Location Creation**
- AI reads setting description
- Suggests 3-5 thematic locations
- Admin can approve, edit, or add custom locations
- Option to skip and add locations later

**Step 5: Admin Notes**
- Private section for:
  - Plot secrets
  - NPC stats and motivations
  - Planned twists
  - Sensitive information
- **Only visible to admin**
- AI can access if explicitly asked by admin

#### Campaign Deletion
- "Delete Campaign" button in campaign details
- Confirmation modal with warning
- Soft delete (mark inactive) vs hard delete option
- Option to archive data before deletion

---

### 🔔 Notification System (Week 3)

#### Notification Types

**1. Admin Actions (Modal Dialog)**
```
Admin Action Notification
─────────────────────────
Your character has been moved to [New Location]

Reason: [Admin's stated reason]

[OK]
```

**2. Enter/Leave (Toast + In-Chat)**
- Toast notification in corner (3s duration)
- System message in chat
- Format: "Marcus (John) has entered/left [Location Name]"

**3. Global Admin Broadcasts (Modal + In-Chat)**
```
📢 Admin Announcement
─────────────────────────
[Admin's message text]

[Auto-close in 60 seconds] [OK]
```

**4. Important Updates (Full Modal)**
- Disconnection notifications
- Character status changes (injury, death, etc.)
- Campaign-wide events
- Requires acknowledgment

#### Implementation Details
- Unified notification system component
- Severity levels: `info`, `warning`, `error`, `admin-action`
- Color-coded borders: Blue, Yellow, Red, Purple
- Queue system for multiple notifications
- Z-index management for proper layering
- Accessibility (keyboard navigation, screen reader support)

---

### 🤖 AI Integration Points

#### Campaign Creation AI
- **Setting Analysis**: Reads setting description, suggests:
  - Thematic locations
  - NPC archetypes
  - Plot hooks
  - Potential conflicts
- **Genre Detection**: Identifies tone, themes automatically
- **Location Generation**: Creates descriptions for suggested locations

#### Character Creation AI
- **Step-by-Step Validation**:
  - Rule compliance checking
  - Setting consistency
  - Balance analysis
  - Lore accuracy
- **Background Assistance**:
  - Suggests character motivations
  - Proposes relationships based on setting
  - Validates equipment choices
  - Helps with physical descriptions

#### Gameplay AI
- **OOC Monitoring**:
  - Detects campaign-relevant spoilers
  - Warns about inappropriate OOC discussion
  - Reports repeated abuse to admin
- **Dynamic Responses**:
  - Context from character location
  - Awareness of recent events
  - Relationship considerations
  - Campaign history integration

---

### 📊 API Endpoints (Week 1-3)

#### Locations
```
POST   /api/campaigns/:id/locations          - Create location
GET    /api/campaigns/:id/locations          - List campaign locations
GET    /api/locations/:id                    - Get location details
PUT    /api/locations/:id                    - Update location
DELETE /api/locations/:id                    - Delete location (soft)
POST   /api/locations/:id/enter              - Enter location (with reason)
POST   /api/locations/:id/leave              - Leave location (with reason)
GET    /api/locations/:id/characters         - List characters in location
```

#### Characters
```
POST   /api/campaigns/:id/characters         - Create character
GET    /api/campaigns/:id/characters         - List campaign characters
GET    /api/users/me/characters              - List user's characters
GET    /api/users/me/characters/:campaignId  - User's chars in campaign
GET    /api/characters/:id                   - Get character details
PUT    /api/characters/:id                   - Update character
PUT    /api/characters/:id/status            - Update physical/mental status
PUT    /api/characters/:id/location          - Change location
DELETE /api/characters/:id                   - Delete character (soft)
POST   /api/characters/:id/validate          - AI validation check
```

#### Messages
```
POST   /api/locations/:id/messages           - Send message
GET    /api/locations/:id/messages           - Get message history
GET    /api/locations/:id/messages?since=:ts - Get messages since timestamp
WS     /ws/locations/:id                     - WebSocket connection
```

#### Admin
```
POST   /api/admin/characters/:id/move        - Move character to location
POST   /api/admin/characters/:id/status      - Set character status
POST   /api/admin/notifications/broadcast    - Send global notification
GET    /api/admin/activity                   - View player activity
GET    /api/admin/campaigns/:id/stats        - Campaign statistics
```

---

### 🧪 Testing Strategy

#### Unit Tests
- Security utility functions (40+ tests) ✅
- Validation helpers ✅
- Sanitization functions ✅
- Rate limiters ✅

#### Integration Tests
- User authentication flow ✅
- Campaign creation/management ✅
- Character selection flow ✅ (manual; automate in CI when stable)
- Chat message posting ✅ (manual; automate in CI)
- Location navigation ✅ (manual)
- WebSocket connections (n/a until implemented)

#### Security Tests
- XSS injection attempts ✅
- SQL injection prevention ✅
- Rate limiting verification ✅
- CSRF token validation (pending)
- Session management (pending)

#### E2E Tests (Week 4)
- Complete user journey: registration → gameplay
- Admin moderation workflows
- Multi-user real-time chat
- Character creation full flow
- Campaign lifecycle

---

### 📅 Rolling roadmap (replaces fixed “Week N” schedule)

**Done (v0.7.17):** Security baseline, PostgreSQL, locations, characters, messages, dice, AI chat + slash commands, OOC moderation, timestamps, docker-up workflow.

**Next (typical order):**
1. **WebSockets** (or SSE) for chat + presence hooks
2. **Notifications** (toasts/modals; ST broadcasts)
3. **Character sheet depth** + **creation wizard** (per north-star sections above)
4. **Campaign setting** UX + AI location flows (extend suggest/batch)
5. **E2E / load** testing as features land

Older “Week 1–4” labels below in this file are **historical**; do not use them for scheduling.

---

### ✅ Success Criteria

- ✅ Security tests pass with 100% coverage
- ✅ All inputs sanitized and validated
- Players can create comprehensive characters
- Real-time chat works with <1s latency
- AI provides helpful suggestions without delays
- Mobile users can participate fully
- Admin tools are intuitive and powerful
- System handles 10+ concurrent players per campaign
- No data loss on disconnection/reconnection
- Character status accurately reflects gameplay

---

### 📈 Performance Targets

- **Chat Latency**: <1s for message delivery
- **AI Response**: <5s for suggestions, <30s for complex validation
- **Page Load**: <2s for dashboard, <3s for character creation
- **WebSocket Reconnection**: <3s on disconnect
- **Database Queries**: <100ms for most operations
- **Security Functions**: <1ms for typical inputs

---

### 🔒 Security Guarantees

- **XSS Protection**: All user inputs sanitized before display
- **SQL Injection**: Parameterized queries, input validation
- **CSRF Protection**: Tokens on all state-changing operations
- **Rate Limiting**: Prevents spam and DoS attempts
- **Session Security**: 6-hour expiration, secure storage
- **Data Privacy**: Admin notes never exposed to players
- **AI Safety**: Cannot reveal other characters' secrets

---

### 📚 User Requirements Documented

From extensive user conversation (2025-10-24), all specifications archived in:
- `docs/PHASE3B_IMPLEMENTATION.md` (full details)
- `docs/CHANGELOG.md` through **v0.7.17** (summary)
- This document (integration into main planning)

Key user requirements:
1. Character status system (physical + mental)
2. Campaign setting structure (narrative + structured)
3. Comprehensive character creation with AI assistance
4. OOC room special rules and monitoring
5. Character tracking and presence display
6. Admin powers and notification system
7. Message types and WebSocket implementation
8. AI integration at all key touch points

---

**Last Updated:** 2026-04-03  
**Next milestone:** Real-time messaging layer (WebSockets or SSE); keep **users / players / characters** data accurate for upcoming location and sheet-depth work; see [Next priorities](#next-priorities).  
**Version:** 0.7.17


# Planning & Phase Documentation

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates planning documentation and phase summaries.

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 3A Next Steps](#phase-3a-next-steps)
3. [Phase 3B Summary](#phase-3b-summary)

---


## Phase 3A Next Steps

## Current Status

### ✅ Completed
- **3A.1 Authentication**: Login, register, invite codes, admin panel
- **3A.2 Campaign Management**: Dashboard, creation, settings view
- **Chat UI**: Discord-like interface with sidebar layout

### 🔄 Partially Complete
- **Chat System**: Basic AI chat works, but not location-aware in database
- **Location System**: Hardcoded 4 locations (OOC, Elysium, Downtown, Haven)
- **Character System**: Database schema exists, but no UI/API

### ❌ Not Started
- **Persistent Locations**: Locations stored in database per campaign
- **Character Creation**: No character creation wizard
- **Character Selection**: No way to select active character
- **Location Management**: Admin can't create/edit/delete locations
- **Message Persistence**: Messages are stored but not filtered by location
- **Character-based Chat**: Messages tied to user, not character

## What Needs to Be Built (Phase 3A.4)

### 1. Location System (Backend + Frontend)

#### Backend API (New Routes)
```
POST   /api/campaigns/<id>/locations       - Admin creates location
GET    /api/campaigns/<id>/locations       - Get all locations for campaign
PUT    /api/campaigns/<id>/locations/<id>  - Admin updates location
DELETE /api/campaigns/<id>/locations/<id>  - Admin deletes location
```

#### Database Schema
```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    location_type TEXT DEFAULT 'location',  -- 'ooc', 'location', 'private'
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

#### Frontend UI
- **Admin**: Location management page in campaign settings
  - Add/Edit/Delete locations
  - Set location types
  - Enable/disable locations
- **Players**: Location browser in chat sidebar
  - Dynamic list from database
  - Move between locations
  - See which location they're in

### 2. Character System (Basic Implementation)

#### Backend API
```
POST   /api/campaigns/<id>/characters      - Create character
GET    /api/campaigns/<id>/characters      - Get user's characters
GET    /api/characters/<id>                - Get character details
PUT    /api/characters/<id>                - Update character
DELETE /api/characters/<id>                - Delete character
POST   /api/characters/<id>/select         - Set as active character
```

#### Database Schema (Already Exists)
```sql
-- characters table exists, verify schema:
- id, name, user_id, campaign_id
- character_type (vampire, werewolf, mage)
- is_npc, is_active
- current_location_id  -- NEW FIELD NEEDED
- sheet_data (JSON with stats)
```

#### Frontend UI
- **Character Selection Modal**: Before entering campaign
  - List user's characters for this campaign
  - "Create New Character" button
  - Select character to enter with
- **Simple Character Creator**: Basic form
  - Name
  - Character type (Vampire, Werewolf, Mage)
  - Brief description
  - Starting location
  - (Full wizard comes later in Phase 3A.3)
- **Character Sidebar**: Shows active character
  - Name, type
  - Current location
  - Basic stats (placeholder for now)

### 3. Message System Updates

#### Backend Changes
```sql
-- Update messages table:
ALTER TABLE messages ADD COLUMN location_id INTEGER;
ALTER TABLE messages ADD COLUMN character_id INTEGER;

-- Messages now associated with:
- user_id (who sent it)
- character_id (which character sent it)
- campaign_id (which campaign)
- location_id (which location/channel)
```

#### API Updates
```
POST /api/chat/send
  - Requires: character_id, location_id, message
  - Validates character is in that location
  
GET /api/chat/messages?campaign_id=X&location_id=Y
  - Returns messages for specific location
  - Includes character info with each message
```

#### Frontend Changes
- Load messages per location (not global)
- When switching locations, load that location's history
- Display character name + username with messages
- Filter messages by current location

### 4. Character Movement

#### Backend API
```
POST /api/characters/<id>/move
  - Body: { location_id: X }
  - Updates character.current_location_id
  - Logs movement in moderation log
```

#### Frontend
- Click location in sidebar → move character
- Confirmation: "Move to [Location]?"
- Update current location indicator
- Load new location's messages

## Implementation Order

### Week 1: Foundation
1. ✅ **Day 1-2**: Location database schema + API
2. ✅ **Day 3**: Character database updates + basic API
3. ✅ **Day 4-5**: Message system updates (location + character association)

### Week 2: Frontend
1. **Day 1-2**: Character selection modal + simple creator
2. **Day 3-4**: Location management UI (admin)
3. **Day 5**: Location-filtered chat + movement
4. **Day 6-7**: Testing + bug fixes

## Technical Decisions

### Location System
- **Default Locations**: Every campaign gets OOC automatically
- **OOC Special**: Always accessible, no location restrictions
- **Admin Only**: Only admins can create/manage locations
- **Character Required**: Must have active character to enter non-OOC locations

### Character System
- **One Active Character**: User can only have one active character per campaign at a time
- **Character Switching**: Can switch characters from dashboard (not in-game)
- **Character Required**: Must create/select character before entering campaign chat
- **NPC Characters**: Admin-created, can post as NPCs

### Message System
- **Character Association**: All messages tied to character (not just user)
- **Location Filtering**: Only see messages from current location
- **History Loading**: Load last 50 messages per location initially
- **Real-time**: WebSocket for live updates (Phase 3B)

## Database Migration Script

```sql
-- Add missing fields
ALTER TABLE characters ADD COLUMN current_location_id INTEGER;
ALTER TABLE messages ADD COLUMN location_id INTEGER;
ALTER TABLE messages ADD COLUMN character_id INTEGER;

-- Create locations table
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    location_type TEXT DEFAULT 'location',
    is_active BOOLEAN DEFAULT 1,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Create default OOC location for existing campaigns
INSERT INTO locations (campaign_id, name, description, location_type, is_active)
SELECT id, '💬 OOC Chat', 'Out-of-character discussion', 'ooc', 1
FROM campaigns;
```

## Testing Checklist

### Location System
- [ ] Admin can create new location
- [ ] Admin can edit location
- [ ] Admin can delete location
- [ ] Players see location list
- [ ] Players can move between locations
- [ ] OOC location always visible

### Character System
- [ ] User can create simple character
- [ ] User can select character before entering campaign
- [ ] User cannot enter without character
- [ ] Character shows in sidebar when in campaign
- [ ] Admin can see all characters in admin panel

### Chat System
- [ ] Messages filtered by location
- [ ] Messages show character name
- [ ] Switching locations loads correct messages
- [ ] Can't send message without character
- [ ] Character location updates when moving

## UI Flow Example

```
1. User logs in → Dashboard
2. User clicks "Enter Campaign" on card
3. Modal appears: "Select your character"
   - List of user's characters
   - "Create New Character" button
4. User selects character (or creates one)
5. User enters campaign chat
   - Starts in OOC location
   - Can see all locations in sidebar
   - Character info in right sidebar
6. User clicks "🏛️ Elysium" location
   - Confirmation: "Move Marcus to Elysium?"
   - Character moves
   - Chat loads Elysium messages
   - Other players see Marcus is now in Elysium (Phase 3B)
```

## Next Phase (3B) - Future

After 3A.4 is complete, Phase 3B adds:
- Real-time updates (WebSocket)
- Character status indicators (online/offline)
- Dice rolling system
- Advanced character creation wizard
- Character relationships
- Rule command system (`/rules`)
- Admin command system

## Current Focus

**Let's start with Day 1-2: Location System**
1. Create locations table
2. Build location API routes
3. Seed default locations for existing campaigns
4. Add admin UI for location management

Ready to begin?


---

## Phase 3B Summary

**This file will be integrated into SHADOWREALMS_AI_COMPLETE.md**

---

## 🚀 Phase 3B: Advanced Campaign & Character Systems

**Status:** 🚧 IN PROGRESS (Week 1: Security & Testing Complete)  
**Version:** 0.7.8  
**Start Date:** 2025-10-24

### Overview
Phase 3B builds upon Phase 3A's foundation (login, dashboard, basic campaign management) by implementing the core gameplay systems: locations, comprehensive character management, real-time chat with WebSocket, and AI-assisted content creation.

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

### 📍 Location System (Week 1) - 🚧 NEXT

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

### 👤 Character Selection & Creation (Week 2)

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

### 💬 Real-Time Chat System (Week 3)

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
- Character selection flow (pending)
- Chat message posting (pending)
- Location navigation (pending)
- WebSocket connections (pending)

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

### 📅 Implementation Timeline

**Week 1: Foundation** (Current)
1. ✅ Security utilities & testing
2. 📍 Location system (database + API)
3. 🏰 Enhanced campaign management (extended fields)

**Week 2: Characters**
1. 👤 Character selection screen with status display
2. 🎭 Character creation wizard (multi-step form)
3. 📊 Character status tracking system

**Week 3: Real-Time Features**
1. 💬 WebSocket infrastructure setup
2. 💬 Chat system with message types
3. 🔔 Notification system implementation

**Week 4: Polish & Integration**
1. 🤖 AI assistance integration (all touch points)
2. 🎨 UI/UX refinements (gothic theme, animations)
3. 🧪 Comprehensive testing (E2E, load testing)
4. 📖 Documentation updates (API docs, user guides)

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
- `docs/CHANGELOG.md` v0.7.6 (summary)
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

**Last Updated:** 2025-10-24  
**Next Milestone:** Location System Implementation (Week 1)  
**Version:** 0.7.8


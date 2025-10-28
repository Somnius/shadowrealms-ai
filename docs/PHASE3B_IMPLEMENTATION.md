# Phase 3B: Advanced Campaign & Character Systems

**Version:** 0.7.8  
**Status:** 🚧 IN PROGRESS  
**Start Date:** 2025-10-24  
**Target Completion:** TBD

---

## Overview

Phase 3B focuses on implementing the core gameplay systems that transform ShadowRealms AI from a simple dashboard into a fully functional tabletop RPG platform. This phase introduces locations, comprehensive character management, real-time chat with WebSocket, and AI-assisted content creation.

---

## 🎯 Implementation Philosophy

### Quality Over Speed

**All Phase 3B features are built on the core principle: Never rush the process.**

Every feature implementation follows these standards:

#### **Deliberate Pacing**
- ✅ Complete one step before starting the next
- ✅ Wait for operations to finish (no assumptions)
- ✅ Show loading states for all async operations
- ✅ Confirm success before proceeding

#### **AI Integration Standards**
When integrating AI features:
- **Show Intent**: User knows AI is being consulted
- **Show Progress**: Loading screen with time estimates (5-15 seconds typical)
- **Handle Failures**: Graceful fallbacks if AI unavailable
- **Validate Results**: Check AI output before presenting to user

Example: Location Suggestions
```
1. User creates campaign
2. Backend creates campaign + OOC room
3. ✅ Confirm success
4. Show location suggestions modal
5. Display "AI is crafting your world..." loading screen
6. Backend sends campaign data to AI (5-15 seconds)
7. AI generates 5 location suggestions
8. Display suggestions with checkboxes (all pre-selected)
9. User selects desired locations
10. User clicks "Create X Locations"
11. Batch create locations
12. ✅ Return to dashboard
```

#### **User Confirmation Requirements**
Critical actions require explicit confirmation:
- **Type "CONFIRM"**: For destructive actions (delete campaign, ban user, kill character)
- **Custom Dialogs**: No browser `alert()` or `confirm()` - use gothic-themed modals
- **Clear Warnings**: List all impacts (locations, characters, messages deleted)
- **No Surprises**: User always knows what will happen

#### **Feedback & Transparency**
Every operation provides clear feedback:
- **Visual**: Pulsing animations (🎲), bouncing dots (⚫⚫⚫), progress indicators
- **Console Logs**: Detailed debugging info for developers (F12)
- **Error Handling**: Show exact errors, provide fallbacks, never fail silently
- **Time Estimates**: "This may take 5-15 seconds..." for long operations

**Result**: Professional, reliable, polished user experience.

---

## Core Features

### 1. 📍 **Location System**

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

#### Features
- **Auto-create OOC Room**: Every campaign starts with an "Out of Character" lobby
- **AI-Suggested Locations**: Based on campaign setting, AI suggests thematic locations
- **Dynamic Location Creation**: Admins can add/edit/remove locations during gameplay
- **Location Requirements**: Players must provide a reason when entering non-OOC locations
  - "Just visited"
  - "Based on previous actions"
  - "Background tasks"
  - "Custom" (free-form text)

#### Special Rules
- **OOC Room**:
  - Players talk as themselves (not as characters)
  - Players can see who's online (unless user set to invisible)
  - Players can temporarily visit OOC while in another location
  - AI monitors for campaign-relevant discussion and warns about OOC abuse
  - AI does NOT reveal other characters' secrets/abilities
- **Admin Powers**:
  - Move/remove characters from locations with logged reasons
  - Reasons visible to affected player and logged for AI context
  - System messages in old/new locations when character moved

---

### 2. 👤 **Character Selection & Creation System**

#### Character Status Tracking
```sql
ALTER TABLE characters ADD COLUMN physical_status TEXT; -- dropdown + custom
ALTER TABLE characters ADD COLUMN mental_status TEXT;   -- dropdown + custom
ALTER TABLE characters ADD COLUMN current_location_id INTEGER;
ALTER TABLE characters ADD COLUMN last_location_id INTEGER;
ALTER TABLE characters ADD COLUMN equipment TEXT;       -- JSON array
ALTER TABLE characters ADD COLUMN relationships TEXT;    -- JSON object
```

#### Physical Status Options (Dropdown + Custom)
- None / Healthy
- Minor Injury (scratches, bruises)
- Major Injury (broken limb, severe wounds)
- Critical Condition (near death)
- Custom (admin/AI can set free-form)

#### Mental Status Options (Dropdown + Custom)
- Stable
- Anxious
- Thoughtful
- Happy
- Unhappy
- Traumatized
- Inspired
- Custom (based on last location events)

#### Character Selection Flow
1. Player enters campaign
2. System shows list of their previous characters in that campaign
3. Each character displays:
   - Name, game system
   - Physical status (with icon/color)
   - Mental status (based on last location)
   - Last played date
4. Options:
   - **Select existing character** → Enter campaign
   - **Create new character** → Show BIG warning modal

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

**Step 1: Character Type Selection**
- Based on campaign game system (Vampire/Werewolf/Mage)
- Options:
  - **Vampire**: Full Vampire, Ghoul, Human
  - **Mage**: Awakened Mage, Human with knowledge, Plain Human
  - **Werewolf**: Garou, Human with enhanced instincts, Plain Human

**Step 2-N: System-Specific Stats**
- Game-system appropriate character sheet fields
- **AI Assistance Box** (side panel):
  - "For this step, admins frequently do X. Would you like suggestions?"
  - Pagination-style AI interaction
  - "Check with AI" button at each step
  - AI validates choices against campaign setting

**Final Step: Background & Equipment**
- **Background Story**: AI-assisted narrative creation
- **Physical Description**: Free-form text
- **Relationships**: Who character knows, how they met
- **Starting Equipment**: Context-appropriate items (wallet, glasses, weapons, etc.)
- **AI Validation**: "Check with AI" button reviews entire character
  - Checks for setting consistency
  - Suggests corrections/improvements
  - Validates against campaign lore

---

### 3. 💬 **Real-Time Chat System**

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
    exit_reason TEXT,
    exited_at TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);
```

#### Message Types
- **IC** (In Character): Normal roleplay messages
- **OOC**: Out of character discussion
- **System**: Automated notifications (player joined/left)
- **Action**: `/me` style actions
- **Dice**: Automated dice roll results

#### WebSocket Implementation
- Real-time message delivery
- Room-based subscriptions (per location)
- Typing indicators
- Online status updates
- Auto-reconnection on disconnect

#### Character Presence Display
- Format: `John (as Marcus the Vampire) is here`
- Right sidebar shows character list per location
- Displays character status icons
- Cannot be in multiple locations (except OOC temporary visit)

#### Auto-Disconnect System
- After 30min inactivity + browser inactive status
- Character marked as "Disconnected"
- On return: Auto-resume to previous location
- Message: "You have been resumed to [Location] due to disconnection"

---

### 4. 🏰 **Enhanced Campaign Management**

#### Extended Campaign Schema
```sql
ALTER TABLE campaigns ADD COLUMN setting_description TEXT;
ALTER TABLE campaigns ADD COLUMN setting_genre TEXT;
ALTER TABLE campaigns ADD COLUMN setting_era TEXT;
ALTER TABLE campaigns ADD COLUMN setting_location TEXT;
ALTER TABLE campaigns ADD COLUMN setting_tone TEXT;
ALTER TABLE campaigns ADD COLUMN setting_themes TEXT;
ALTER TABLE campaigns ADD COLUMN admin_notes TEXT; -- Private admin notes
```

#### Campaign Creation Flow

**Step 1: Basic Information**
- Name, Description
- Game System selection

**Step 2: Setting Description**
Example format (like "Ashes of the Aegean"):
```
Setting:
[Detailed world description - time period, location, atmosphere]

Premise:
[Main conflict, power dynamics, current state of the world]

Tone:
[Dark, Political, Mythic, etc.]

Player Hook:
[Why players are involved, their role in the story]

Themes:
[Core themes of the campaign]
```

**Step 3: Structured Setting Fields**
- Genre (dropdown or custom)
- Era (Modern, Medieval, Future, etc.)
- Location (City, Region, World)
- Tone keywords
- Themes list

**Step 4: AI-Assisted Location Creation**
- Based on setting description, AI suggests 3-5 thematic locations
- Admin can approve, edit, or add custom locations
- Option to skip and add locations later

**Step 5: Admin Notes**
- Private section for plot secrets, NPC stats, planned twists
- Only visible to admin, never to players or AI (unless explicitly queried)

#### Campaign Deletion
- New "Delete Campaign" button in campaign details
- Confirmation modal with warning
- Soft delete (mark as inactive) vs hard delete option
- Archive campaign data before deletion

---

### 5. 🔔 **Notification System**

#### Notification Types

**1. Admin Actions** (Modal Dialog)
```
Admin Action Notification
─────────────────────────
Your character has been moved to [New Location]

Reason: [Admin's reason]

[OK]
```

**2. Enter/Leave** (Toast + In-Chat)
- Toast notification in corner
- System message in chat
- Format: "Marcus (John) has entered/left the location"

**3. Global Admin Broadcasts** (Modal + In-Chat)
```
📢 Admin Announcement
─────────────────────────
[Admin's message]

[Auto-close in 60 seconds] [OK]
```

**4. Important Updates** (Full Modal)
- Disconnection notifications
- Character status changes
- Campaign updates

#### Implementation
- Unified notification system with different severity levels:
  - `info`: Blue border, informational
  - `warning`: Yellow border, requires attention
  - `error`: Red border, critical
  - `admin-action`: Purple border, admin-initiated

---

### 6. 🤖 **AI Integration Points**

#### Campaign Creation
- **Setting Analysis**: AI reads setting description and suggests:
  - Appropriate locations
  - NPC archetypes
  - Plot hooks
  - Potential conflicts

#### Character Creation
- **Step-by-Step Validation**: AI checks each field for:
  - Rule compliance
  - Setting consistency
  - Balance issues
  - Lore accuracy

#### Gameplay
- **OOC Monitoring**: AI watches OOC for:
  - Campaign-relevant spoilers
  - Rule discussions that should be private
  - Player conflicts
- **Dynamic Responses**: AI generates contextual responses based on:
  - Character location
  - Recent events
  - Character relationships
  - Campaign history

---

## Security Enhancements

### Input Sanitization
- XSS prevention on all text inputs
- SQL injection protection
- HTML tag stripping in names
- Script tag removal in descriptions
- Event handler blocking

### Validation
- Email format validation
- Username alphanumeric + length check
- Password strength requirements (8+ chars, uppercase, lowercase, number)
- Campaign data validation
- Message length limits (2000 chars)

### Rate Limiting
- Client-side rate limiter for chat messages
- API rate limiting on backend
- Spam prevention mechanisms

### CSRF Protection
- CSRF tokens for all state-changing operations
- Token validation on backend

### Secure Storage
- Obfuscated localStorage for sensitive data
- Automatic token expiration
- Session management with 6-hour timeout

---

## API Endpoints

### Locations
```
POST   /api/campaigns/:id/locations          - Create location
GET    /api/campaigns/:id/locations          - List locations
GET    /api/locations/:id                    - Get location details
PUT    /api/locations/:id                    - Update location
DELETE /api/locations/:id                    - Delete location
POST   /api/locations/:id/enter              - Enter location (with reason)
POST   /api/locations/:id/leave              - Leave location
```

### Characters
```
POST   /api/campaigns/:id/characters         - Create character
GET    /api/campaigns/:id/characters         - List campaign characters
GET    /api/users/me/characters              - List user's characters
GET    /api/characters/:id                   - Get character details
PUT    /api/characters/:id                   - Update character
PUT    /api/characters/:id/status            - Update status
DELETE /api/characters/:id                   - Delete character
```

### Messages
```
POST   /api/locations/:id/messages           - Send message
GET    /api/locations/:id/messages           - Get message history
WS     /ws/locations/:id                     - WebSocket connection
```

### Admin
```
POST   /api/admin/characters/:id/move        - Move character to location
POST   /api/admin/notifications/broadcast    - Send global notification
GET    /api/admin/activity                   - View player activity
```

---

## Testing Strategy

### Unit Tests
- Security utility functions
- Validation helpers
- Sanitization functions

### Integration Tests
- User authentication flow
- Campaign creation process
- Character creation wizard
- Chat message posting
- Location navigation

### Security Tests
- XSS injection attempts
- SQL injection prevention
- Rate limiting verification
- CSRF token validation

### E2E Tests
- Complete user journey from registration to gameplay
- Admin moderation workflows
- Multi-user real-time chat

---

## Implementation Priority

### Week 1: Foundation
1. ✅ Security utilities & testing
2. 📍 Location system (database + API)
3. 🏰 Enhanced campaign management

### Week 2: Characters
1. 👤 Character selection screen
2. 🎭 Character creation wizard
3. 📊 Character status tracking

### Week 3: Real-Time Features
1. 💬 WebSocket infrastructure
2. 💬 Chat system with message types
3. 🔔 Notification system

### Week 4: Polish & Integration
1. 🤖 AI assistance integration
2. 🎨 UI/UX refinements
3. 🧪 Comprehensive testing
4. 📖 Documentation updates

---

## Known Challenges

1. **WebSocket State Management**: Ensuring connection stability and reconnection logic
2. **Character Status Updates**: Real-time sync across multiple clients
3. **AI Response Time**: Balancing thoroughness with performance
4. **Mobile WebSocket**: Handling connection drops on mobile networks
5. **Database Migrations**: Safely updating existing campaign data

---

## Success Criteria

- ✅ Players can create and manage characters with full stats
- ✅ Real-time chat works reliably with <1s latency
- ✅ AI provides helpful suggestions without slowing gameplay
- ✅ All security tests pass with 100% coverage
- ✅ Mobile users can participate without issues
- ✅ Admin tools are intuitive and powerful
- ✅ System handles 10+ concurrent players per campaign

---

## Files Modified/Created

### Backend
- `backend/database.py` - Extended schema migrations
- `backend/routes/locations.py` - Location CRUD endpoints
- `backend/routes/messages.py` - Message handling
- `backend/routes/characters.py` - Character management
- `backend/services/websocket_service.py` - WebSocket handling
- `backend/services/notification_service.py` - Notification dispatch

### Frontend
- `frontend/src/utils/security.js` - Security utilities ✅
- `frontend/src/utils/__tests__/security.test.js` - Security tests ✅
- `frontend/src/__tests__/integration/userFlow.test.js` - Integration tests ✅
- `frontend/src/components/CharacterSelection.js` - Character picker
- `frontend/src/components/CharacterCreation.js` - Creation wizard
- `frontend/src/components/LocationManagement.js` - Location admin
- `frontend/src/components/NotificationSystem.js` - Unified notifications
- `frontend/src/services/websocket.js` - WebSocket client

### Documentation
- `docs/PHASE3B_IMPLEMENTATION.md` - This file ✅
- `docs/CHANGELOG.md` - Version history
- `README.md` - Updated status

---

**Last Updated:** 2025-10-24  
**Next Review:** After Week 1 completion


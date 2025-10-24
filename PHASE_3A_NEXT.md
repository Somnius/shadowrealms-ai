# Phase 3A.4: Location-Based Chat & Character System

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


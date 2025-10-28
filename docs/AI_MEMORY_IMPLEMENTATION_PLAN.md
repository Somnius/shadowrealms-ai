# 🧠 AI Memory System - Full Implementation Plan (Option C)

**Date:** October 28, 2025  
**Status:** 🚀 IN PROGRESS  
**Approach:** Phased implementation with testing at each step

---

## 🎯 Complete Vision

AI that remembers and understands:
- ✅ All conversation history (recent + semantic search)
- ✅ Location context (where, what's there, atmosphere)
- ✅ Character information (who's talking, their background)
- ✅ NPC interactions (who said what, relationships)
- ✅ Character-to-Character interactions
- ✅ Character-to-NPC interactions
- ✅ NPC-to-NPC interactions
- ✅ Location-to-Location relationships (connected areas)
- ✅ Combat context (ongoing fights, initiative, wounds)
- ✅ World data (campaign events, lore, rules)

---

## 📋 Implementation Phases

### **PHASE 1: Foundation - Message History & Location Context** ⏱️ 1.5 hours
**Goal:** AI sees recent messages and knows where conversation happens

#### Step 1.1: Create Location Context Function (20 min)
- Function: `get_location_context(location_id, campaign_id)`
- Fetches: location name, type, description
- Returns: formatted location info

#### Step 1.2: Create Message History Function (20 min)
- Function: `get_recent_messages(location_id, campaign_id, limit=15)`
- Fetches: last N messages from this location
- Formats: chronological conversation history
- Includes: username, timestamp, role

#### Step 1.3: Update AI Response Functions (30 min)
- Modify: `generate_efficient_response()`
- Modify: `generate_balanced_response()`
- Modify: `generate_full_response()`
- Add: location_id parameter
- Integrate: location context + message history into prompt

#### Step 1.4: Update Frontend to Pass location_id (20 min)
- Modify: `handleSendMessage()` in SimpleApp.js
- Pass: `location: currentLocation.id` to AI API

#### Step 1.5: Test Phase 1 (10 min)
- Send messages in different locations
- Verify AI remembers recent conversation
- Verify AI knows current location

**Output:** AI can recall recent messages and knows location context

---

### **PHASE 2: Character Awareness** ⏱️ 1 hour
**Goal:** AI knows who's talking and their background

#### Step 2.1: Create Character Context Function (25 min)
- Function: `get_character_context(user_id, campaign_id)`
- Fetches: character name, system_type, attributes, skills, background
- Returns: formatted character info

#### Step 2.2: Integrate Character Context into AI Prompt (20 min)
- Modify: AI response functions
- Add: character data to prompt
- Format: "Character: [name], Clan: [clan], Background: [summary]"

#### Step 2.3: Character-Aware Responses (15 min)
- Update: system prompts to be character-aware
- Example: "Respond as if speaking to [character name], a [clan] vampire..."

**Output:** AI addresses player by character name, considers character background

---

### **PHASE 3: NPC System & Interactions** ⏱️ 1.5 hours
**Goal:** Track NPCs per location, their statements, and interactions

#### Step 3.1: Create NPCs Table (20 min)
- Migration: Add `npcs` table
```sql
CREATE TABLE npcs (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    location_id INTEGER,
    name TEXT NOT NULL,
    type TEXT,  -- 'bartender', 'guard', 'vampire', etc.
    description TEXT,
    personality TEXT,
    faction TEXT,
    created_by INTEGER,
    created_at TIMESTAMP
)
```

#### Step 3.2: Create NPC_Messages Table (20 min)
- Migration: Add `npc_messages` table
```sql
CREATE TABLE npc_messages (
    id INTEGER PRIMARY KEY,
    npc_id INTEGER,
    location_id INTEGER,
    campaign_id INTEGER,
    content TEXT NOT NULL,
    context TEXT,  -- What prompted this
    created_at TIMESTAMP,
    FOREIGN KEY (npc_id) REFERENCES npcs(id)
)
```

#### Step 3.3: NPC Context Function (25 min)
- Function: `get_location_npcs(location_id)`
- Returns: NPCs present at location
- Function: `get_npc_history(npc_id, limit=5)`
- Returns: Recent NPC statements/actions

#### Step 3.4: Track NPC Interactions in Messages (25 min)
- Add: `npc_id` reference to messages table (optional)
- Function: `store_npc_interaction(npc_id, message, context)`
- Tracks: What NPCs said/did based on AI responses

**Output:** AI knows NPCs at location, remembers what they said

---

### **PHASE 4: Semantic Search (RAG Integration)** ⏱️ 1 hour
**Goal:** AI can search ALL past messages, not just recent

#### Step 4.1: Embed Messages into ChromaDB (30 min)
- Function: `embed_message(message_id, content, metadata)`
- Called: When message is saved to database
- Metadata: {campaign_id, location_id, user_id, timestamp}

#### Step 4.2: Semantic Message Retrieval (20 min)
- Function: `retrieve_relevant_messages(query, location_id, limit=5)`
- Uses: RAG service to search message embeddings
- Returns: Most relevant past messages

#### Step 4.3: Integrate Semantic Search into AI Prompt (10 min)
- Add: Relevant historical messages to context
- Format: "Relevant Past Context: [semantic results]"

**Output:** AI can recall details from days/weeks ago

---

### **PHASE 5: Combat & Conflict Context** ⏱️ 1 hour
**Goal:** AI understands ongoing fights, initiative, wounds

#### Step 5.1: Create Combat_Encounters Table (20 min)
```sql
CREATE TABLE combat_encounters (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    location_id INTEGER,
    status TEXT,  -- 'active', 'resolved'
    initiative_order TEXT,  -- JSON array
    round_number INTEGER,
    created_at TIMESTAMP
)
```

#### Step 5.2: Create Combat_Participants Table (20 min)
```sql
CREATE TABLE combat_participants (
    id INTEGER PRIMARY KEY,
    encounter_id INTEGER,
    character_id INTEGER,
    npc_id INTEGER,
    current_hp INTEGER,
    max_hp INTEGER,
    conditions TEXT,  -- JSON array
    initiative INTEGER,
    FOREIGN KEY (encounter_id) REFERENCES combat_encounters(id)
)
```

#### Step 5.3: Combat Context Function (20 min)
- Function: `get_active_combat(location_id)`
- Returns: Current fight status if active
- Includes: Participants, HP, initiative order, conditions

**Output:** AI knows about ongoing combat, adjusts responses

---

### **PHASE 6: Relationship & Interaction Tracking** ⏱️ 45 min
**Goal:** Track character-character, character-NPC, NPC-NPC relationships

#### Step 6.1: Create Relationships Table (20 min)
```sql
CREATE TABLE relationships (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER,
    entity1_type TEXT,  -- 'character' or 'npc'
    entity1_id INTEGER,
    entity2_type TEXT,
    entity2_id INTEGER,
    relationship_type TEXT,  -- 'ally', 'enemy', 'neutral', 'lover', etc.
    strength INTEGER,  -- -10 to +10
    notes TEXT,
    last_interaction TIMESTAMP
)
```

#### Step 6.2: Relationship Context Function (25 min)
- Function: `get_entity_relationships(entity_type, entity_id)`
- Returns: All relationships for character/NPC
- Function: `update_relationship(entity1, entity2, change)`
- Updates: Relationship based on interactions

**Output:** AI knows who likes/hates whom, adjusts dialogue

---

### **PHASE 7: Location Connections & World Context** ⏱️ 30 min
**Goal:** AI understands connected locations and campaign world

#### Step 7.1: Add Location Connections (15 min)
```sql
CREATE TABLE location_connections (
    id INTEGER PRIMARY KEY,
    location1_id INTEGER,
    location2_id INTEGER,
    connection_type TEXT,  -- 'door', 'path', 'teleport', 'hidden'
    description TEXT,
    FOREIGN KEY (location1_id) REFERENCES locations(id),
    FOREIGN KEY (location2_id) REFERENCES locations(id)
)
```

#### Step 7.2: World Context Function (15 min)
- Function: `get_world_context(campaign_id)`
- Fetches: Recent campaign events, active plots
- Returns: Current state of the world

**Output:** AI knows connected areas, ongoing campaign events

---

### **PHASE 8: Context Manager & Token Optimization** ⏱️ 45 min
**Goal:** Smart context assembly, stay within token limits

#### Step 8.1: Create Context Manager Class (30 min)
- Class: `AIContextManager`
- Method: `build_context(message, location_id, user_id, campaign_id)`
- Logic: Prioritize context based on relevance
- Token counting: Ensure doesn't exceed LLM limits
- Prioritization:
  1. Current location & immediate messages (always include)
  2. Active combat (if any)
  3. NPCs present
  4. Character info
  5. Relevant semantic history
  6. Relationships (if mentioned)
  7. World events

#### Step 8.2: Integrate Context Manager (15 min)
- Replace: Manual context building
- Use: AIContextManager.build_context()
- Result: Optimized, intelligent context

**Output:** AI has all relevant context without exceeding limits

---

### **PHASE 9: Testing & Refinement** ⏱️ 30 min
**Goal:** Verify everything works together

#### Test Scenarios:
1. ✅ Multi-location conversation continuity
2. ✅ Character recognition and appropriate responses
3. ✅ NPC interaction memory
4. ✅ Combat situation awareness
5. ✅ Relationship-aware dialogue
6. ✅ Semantic recall of old events
7. ✅ Character-to-character interactions
8. ✅ NPC-to-NPC interactions

**Output:** Fully functional AI memory system

---

## 📊 Total Estimated Time: 6-7 hours

Breaking down by category:
- Foundation (Phase 1): 1.5 hours
- Character System (Phase 2): 1 hour
- NPC System (Phase 3): 1.5 hours
- RAG/Semantic (Phase 4): 1 hour
- Combat (Phase 5): 1 hour
- Relationships (Phase 6): 45 min
- World Context (Phase 7): 30 min
- Optimization (Phase 8): 45 min
- Testing (Phase 9): 30 min

---

## 🎯 Immediate Next Steps

**START NOW:**
1. Phase 1, Step 1.1: Create location context function
2. Phase 1, Step 1.2: Create message history function
3. Phase 1, Step 1.3: Update AI response functions
4. Test Phase 1
5. Move to Phase 2

**Progress Tracking:**
- I'll update this document after each phase
- You can test each phase independently
- Each phase builds on the previous

---

## 🔄 Context Assembly Priority

When building AI prompt (Phase 8), include in this order:

**CRITICAL (Always Include):**
1. Current location name & description
2. Last 5-10 messages from this location
3. Current user's character info

**HIGH PRIORITY (Usually Include):**
4. NPCs present at location
5. Active combat status (if any)
6. Recent NPC interactions (last 2-3)

**MEDIUM PRIORITY (Include if tokens allow):**
7. Semantically relevant old messages (3-5)
8. Character relationships with present NPCs
9. Connected locations

**LOW PRIORITY (Include if tokens allow):**
10. Campaign world events
11. Extended NPC histories
12. Distant relationships

---

## 🎮 Example Final AI Prompt

```
=== SYSTEM ===
You are an AI storyteller for Vampire: The Masquerade.
Campaign: The Debt of Blood
Current Round: 15
Game System: Vampire: The Masquerade 20th Anniversary

=== CURRENT LOCATION ===
Location: The Gathering Place (tavern)
Type: Tavern
Description: A dimly lit tavern where vampires gather. The smell of old blood mingles with tobacco smoke.

NPCs Present:
- Marcus (Bartender) - Toreador, friendly but cautious
- Suspicious Hooded Figure (Unknown) - Watching from corner

=== ACTIVE COMBAT ===
None

=== CHARACTER ===
Player Character: Viktor Drago
User: adminator
Clan: Ventrue
Generation: 10th
Background: Former mobster turned vampire, struggling with Beast
Current Status: Blood Pool 7/10, no injuries
Relationships:
- Marcus (Bartender): Friendly (+3)
- Prince Alexandros: Cautious (-1)

=== RECENT CONVERSATION (Last 10 messages) ===
[5 min ago] Viktor: "I enter the tavern and nod to Marcus."
[4 min ago] AI: "Marcus nods back, his eyes briefly glowing red in recognition."
[3 min ago] Viktor: "The usual spot available?"
[2 min ago] AI: "Marcus gestures to your booth in the back. 'Always for you, Viktor.'"
[1 min ago] Viktor: "I notice someone watching me. Who is it?"

=== RELEVANT HISTORY (Semantic) ===
[3 days ago] Viktor asked Marcus about Prince Alexandros
[3 days ago] Marcus warned: "The prince has eyes everywhere. Be careful."
[1 week ago] Suspicious disappearances of vampires questioning the prince

=== CURRENT MESSAGE ===
Viktor: "I approach Marcus and ask about the figure in the corner."

=== INSTRUCTIONS ===
Respond as the AI storyteller. Consider:
- Viktor's Ventrue nature (commanding, political)
- His relationship with Marcus (friendly)
- The tavern atmosphere
- The suspicious figure's presence
- The ongoing political tension with the prince

Keep responses immersive, descriptive, and true to Vampire: The Masquerade lore.
```

---

## 🚀 Ready to Start?

**I'll begin with Phase 1 immediately.**

After each phase, I'll:
1. ✅ Implement the code
2. ✅ Test it works
3. ✅ Show you what to test
4. ✅ Move to next phase

**Estimated completion: 6-7 hours of focused work**

**Let's build the ultimate AI memory system!** 🧠🦇


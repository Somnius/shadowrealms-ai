# 🧠 AI Context & Memory System - Proposals

**Date:** October 28, 2025  
**Issue:** AI doesn't remember previous discussions when responding  
**Goal:** Make AI aware of location history, characters, and world data

---

## 🔍 Current State Analysis

### What's Already Working ✅
1. **Messages saved to database** - All conversations stored per location
2. **RAG Service** - ChromaDB for semantic search (retrieve_memories)
3. **AI Memory Table** - Stores conversation summaries
4. **Campaign Context** - AI gets basic campaign info (name, description, game system)

### What's Missing ❌
1. **No message history in AI prompts** - AI doesn't see previous messages
2. **No location-specific context** - AI doesn't know where the conversation is happening
3. **No character awareness** - AI doesn't know who's talking
4. **No world data retrieval** - AI can't reference location details

---

## 💡 Proposed Solutions (Choose Your Approach)

### **Option A: Simple Context Window (Recommended for Start)**
**Complexity:** 🟢 Low  
**Performance:** 🟢 Fast  
**Memory:** 🟢 Efficient  

#### How It Works
When user sends a message:
1. Fetch **last N messages** from this location (e.g., last 10-20)
2. Add messages to AI prompt as "conversation history"
3. Include location name and description
4. Send to AI with full context

#### Example Prompt Structure
```
System: You are an AI storyteller for a Vampire: The Masquerade game.

Campaign: The Debt of Blood
Location: The Gathering Place (tavern) - A common meeting location for the characters.
Game System: Vampire: The Masquerade

Recent Conversation History:
[10 minutes ago] User (adminator): "I enter the tavern and look around."
[9 minutes ago] AI: "The tavern is dimly lit, with the smell of old blood..."
[5 minutes ago] User (adminator): "I approach the bartender."

Current Message: "What can you tell me about the local prince?"
```

#### Pros
- ✅ Simple to implement (1-2 hours)
- ✅ Works immediately
- ✅ No complex infrastructure
- ✅ Easy to debug
- ✅ Predictable behavior

#### Cons
- ⚠️ Limited to recent messages only (no long-term memory)
- ⚠️ Sends same history every time (slight inefficiency)
- ⚠️ Can't search old conversations semantically

#### Implementation Steps
1. Modify `generate_*_response()` functions
2. Add `get_location_context(location_id)` function
3. Fetch last N messages from database
4. Format as conversation history
5. Add to AI prompt

---

### **Option B: RAG-Enhanced Context (Best Balance)**
**Complexity:** 🟡 Medium  
**Performance:** 🟡 Good  
**Memory:** 🟡 Smart  

#### How It Works
When user sends a message:
1. Use **semantic search** on message history for this location
2. Find the **most relevant past messages** related to current query
3. Fetch location details from database
4. Combine: relevant history + location data + current message
5. Send to AI

#### Example Flow
```
User asks: "What did the bartender tell me about the prince?"

Step 1: Semantic search in messages
  → Finds: "The bartender mentioned the prince is paranoid..."
  → Finds: "Local vampires fear the prince's wrath..."
  
Step 2: Get location context
  → The Gathering Place (tavern)
  → Description: Common meeting location
  → NPCs present: Bartender (Marcus), 3 patrons
  
Step 3: Combine & send to AI
  → Relevant history (semantically matched)
  → Location details
  → Current question
  
AI Response: "As you recall, the bartender Marcus mentioned that the prince..."
```

#### Pros
- ✅ Retrieves **relevant** context, not just recent
- ✅ Can remember details from days ago
- ✅ Semantic understanding (asks "what did he say?" → finds the actual statement)
- ✅ Scales better for long campaigns
- ✅ More natural AI responses

#### Cons
- ⚠️ Requires ChromaDB integration for messages
- ⚠️ Slightly more complex (2-3 hours)
- ⚠️ Need to embed messages into vector database
- ⚠️ Slight delay for semantic search

#### Implementation Steps
1. Store messages in ChromaDB when saved (embed content)
2. Create `retrieve_location_messages(location_id, query)` function
3. Use RAG service to find relevant messages
4. Fetch location details (description, NPCs, etc.)
5. Build enhanced context for AI
6. Add to AI prompt

---

### **Option C: Hybrid Approach (Maximum Quality)**
**Complexity:** 🔴 High  
**Performance:** 🟡 Good but resource-intensive  
**Memory:** 🔴 Most demanding  

#### How It Works
Combines both approaches:
1. **Always include**: Last 5-10 messages (recency)
2. **Semantic search**: Additional relevant messages from history
3. **Location data**: Full details (description, NPCs, items)
4. **Character data**: Who's speaking, their background
5. **World data**: Related lore, rules, campaign events

#### Example Context
```
=== IMMEDIATE CONTEXT ===
Last 5 messages in this location...

=== RELEVANT HISTORY ===
[3 days ago] In this tavern, the bartender warned about...
[1 week ago] You learned that the prince is...

=== LOCATION ===
The Gathering Place
Type: Tavern
Description: ...
NPCs: Marcus (Bartender), suspicious hooded figure
Atmosphere: Tense, vampire politics

=== CHARACTER ===
Player: adminator
Character: Marcus the Ventrue
Clan: Ventrue
Background: Noble lineage, political ambitions
Current Status: Blood pool 7/10, investigating prince

=== WORLD DATA ===
Campaign Setting: Modern Chicago, Camarilla controlled
Recent Events: Prince declared martial law
Key NPCs: Prince Alexandros (paranoid), Sheriff Victoria (ruthless)
```

#### Pros
- ✅ Most intelligent responses
- ✅ AI remembers everything
- ✅ Character-aware roleplay
- ✅ Location-specific details
- ✅ Campaign continuity

#### Cons
- ⚠️ Complex implementation (4-6 hours)
- ⚠️ More tokens = higher latency
- ⚠️ Requires character system integration
- ⚠️ Need to manage context window limits
- ⚠️ Ongoing maintenance

#### Implementation Steps
1. Implement Option B (RAG)
2. Add `get_character_context(user_id, campaign_id)`
3. Add `get_location_details(location_id)`
4. Add `get_world_context(campaign_id)`
5. Create context manager to combine all data
6. Implement token limit checks
7. Prioritize context based on relevance

---

## 📊 Comparison Matrix

| Feature | Option A | Option B | Option C |
|---------|----------|----------|----------|
| **Implementation Time** | 1-2 hours | 2-3 hours | 4-6 hours |
| **Complexity** | Low | Medium | High |
| **Short-term Memory** | ✅ Good | ✅ Good | ✅ Excellent |
| **Long-term Memory** | ❌ No | ✅ Yes | ✅ Yes |
| **Semantic Search** | ❌ No | ✅ Yes | ✅ Yes |
| **Location Awareness** | 🟡 Basic | ✅ Good | ✅ Excellent |
| **Character Awareness** | ❌ No | 🟡 Minimal | ✅ Full |
| **Performance** | ✅ Fast | 🟡 Good | ⚠️ Slower |
| **Token Usage** | 🟢 Low | 🟡 Medium | 🔴 High |
| **Maintenance** | ✅ Easy | 🟡 Moderate | ⚠️ Complex |
| **Scalability** | 🟡 Limited | ✅ Good | ✅ Excellent |

---

## 🎯 My Recommendation

### **Start with Option A, Then Migrate to Option B**

**Phase 1 (Now):** Option A - Simple Context Window
- Quick to implement
- Immediate improvement
- Learn what works
- **Time**: 1-2 hours

**Phase 2 (Later):** Option B - RAG-Enhanced
- Proven simple approach works
- Add semantic search for old messages
- Better long-term memory
- **Time**: +2 hours

**Phase 3 (Future):** Option C - Full System
- Character system fully implemented
- Location management complete
- World building tools ready
- **Time**: +4 hours when features exist

### Why This Approach?
1. ✅ **Quick wins** - Users see improvement today
2. ✅ **Learn by doing** - Discover what context matters most
3. ✅ **Iterative** - Build on working foundation
4. ✅ **Less risk** - Don't over-engineer before testing
5. ✅ **Budget-friendly** - Spread work over time

---

## 🛠️ Implementation Preview

### What I Would Build (Option A)

**New Function:**
```python
def get_location_context(location_id: int, campaign_id: int, limit: int = 10) -> dict:
    """Get context for a specific location"""
    db = get_db()
    cursor = db.cursor()
    
    # Get location details
    cursor.execute("""
        SELECT name, type, description
        FROM locations
        WHERE id = ? AND campaign_id = ?
    """, (location_id, campaign_id))
    location = cursor.fetchone()
    
    # Get recent messages from this location
    cursor.execute("""
        SELECT m.content, m.role, m.created_at, u.username
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.campaign_id = ? AND m.location_id = ?
        ORDER BY m.created_at DESC
        LIMIT ?
    """, (campaign_id, location_id, limit))
    messages = cursor.fetchall()
    
    # Format conversation history
    history = []
    for msg in reversed(messages):  # Chronological order
        timestamp = format_timestamp(msg['created_at'])
        role = "User" if msg['role'] == 'user' else "AI"
        history.append(f"[{timestamp}] {role} ({msg['username']}): {msg['content']}")
    
    return {
        'location': location,
        'history': '\n'.join(history),
        'message_count': len(messages)
    }
```

**Updated AI Prompt:**
```python
def generate_full_response(message: str, context: dict, campaign_id: int, location_id: int = None) -> str:
    llm_service = get_llm_service()
    
    # Get campaign context
    campaign_context = get_campaign_context(campaign_id)
    
    # Get location context if provided
    location_context = ""
    if location_id:
        loc_data = get_location_context(location_id, campaign_id, limit=10)
        location_context = f"\nLocation: {loc_data['location']['name']} ({loc_data['location']['type']})"
        location_context += f"\nDescription: {loc_data['location']['description']}"
        location_context += f"\n\nRecent Conversation History ({loc_data['message_count']} messages):\n{loc_data['history']}"
    
    # Build enhanced prompt
    llm_context = {
        'system_prompt': f'''You are an AI storyteller for a tabletop RPG.
        
{campaign_context}
{location_context}

Current player message: {message}

Respond as the AI storyteller, taking into account the conversation history and location context.''',
        'campaign_context': campaign_context
    }
    
    llm_config = {
        'max_tokens': 1024,
        'temperature': 0.8,
        'top_p': 0.95
    }
    
    return llm_service.generate_response(message, llm_context, llm_config)
```

---

## 🎮 Example Results

### Before (Current)
```
User: "What did the bartender tell me about the prince?"
AI: "I don't have information about previous conversations. Could you provide more context?"
```

### After (Option A)
```
User: "What did the bartender tell me about the prince?"
AI: "As you recall from your earlier conversation, the bartender Marcus mentioned that Prince Alexandros has become increasingly paranoid since the recent disappearances..."
```

### After (Option B)
```
User: "What did the bartender tell me about the prince?"
AI: "Three days ago in this very tavern, Marcus the bartender warned you that Prince Alexandros has eyes everywhere. He also mentioned that two vampires who questioned the prince's authority disappeared last week..."
```

---

## ❓ Questions to Help You Decide

1. **How soon do you want this feature?**
   - Today/Tomorrow → Option A
   - This week → Option B
   - When character system is done → Option C

2. **How important is long-term memory?**
   - Not critical yet → Option A
   - Important → Option B
   - Essential → Option C

3. **Do you have characters implemented?**
   - No → Option A or B only
   - Partially → Option B
   - Fully → Option C possible

4. **How long are your play sessions?**
   - Short (1-2 hours) → Option A fine
   - Medium (2-4 hours) → Option B better
   - Long campaigns → Option C ideal

---

## 🚀 Next Steps

**Tell me which option you prefer, or ask questions!**

I can implement:
- ✅ **Option A** in 1-2 hours (ready today)
- ✅ **Option B** in 2-3 hours (ready today/tomorrow)
- ✅ **Option C** in 4-6 hours (ready this week)

Or we can discuss a **custom hybrid** that fits your exact needs! 🦇


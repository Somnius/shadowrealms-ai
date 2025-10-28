# OOC (Out of Character) Monitoring System

## Overview

The OOC Monitoring System ensures that players maintain proper roleplay boundaries in Out of Character rooms by using AI to detect and prevent in-character discussions.

## Features

### 1. **OOC Room Protection**
- Every campaign MUST have an OOC (Out of Character) Lobby
- OOC rooms CANNOT be deleted by admins
- OOC rooms are automatically created when a campaign is created
- Missing OOC rooms can be fixed with `backend/fix_missing_ooc_rooms.py`

### 2. **AI-Powered Detection**
The system uses a lightweight AI model (`llama3.2:3b`) to detect in-character content in OOC rooms.

**What is detected as IC (In-Character)?**
- Character actions in first person ("I draw my sword")
- Roleplay actions with asterisks ("*sneaks through shadows*")
- Speaking as your character without clarification
- Describing character actions as if playing them

**What is ALLOWED in OOC?**
- Discussing the game as a player
- Asking rules questions
- Coordinating schedules
- Discussing character plans in third person ("My character should...")
- General chat and banter

### 3. **Warning System**
```
1st Violation → ⚠️  Warning (1/3)
2nd Violation → ⚠️  Warning (2/3)
3rd Violation → ⛔ 24-Hour Ban
```

**Warning Message Example:**
```
⚠️ OOC VIOLATION WARNING (2/3)

Your message appears to contain in-character content. 
The OOC (Out of Character) Lobby is for discussing the game as players, 
not roleplaying as characters.

Please keep in-character discussions to the game locations.

You have 1 warning(s) remaining before a temporary ban is issued.
```

### 4. **Temporary Bans**
- **Duration**: 24 hours
- **Trigger**: 3 OOC violations within 7 days
- **Effect**: User cannot send messages in ANY campaign
- **Message**: Clear explanation of why they were banned and when it expires

**Ban Message Example:**
```
⛔ You are temporarily banned from this campaign.

Reason: Temporary ban for repeated OOC violations in campaign ID 7. 
Please review the OOC room rules: No in-character roleplay in OOC.

Time remaining: 23h 45m

Ban expires: 2025-10-29 14:30 UTC
```

### 5. **Violation Tracking**
- Violations are tracked per user per campaign
- Rolling 7-day window (old violations don't count after 7 days)
- Violations are logged in `ooc_violations` table
- Ban history is stored in `users` table

## Database Schema

### `ooc_violations` Table
```sql
CREATE TABLE ooc_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    campaign_id INTEGER NOT NULL,
    violated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
)
```

### `users` Ban Fields
```sql
ban_type TEXT DEFAULT NULL,          -- 'temp' or 'permanent'
ban_until TIMESTAMP DEFAULT NULL,    -- When ban expires
ban_reason TEXT DEFAULT NULL,        -- Why user was banned
banned_by INTEGER DEFAULT NULL,      -- Admin who issued ban
banned_at TIMESTAMP DEFAULT NULL     -- When ban was issued
```

## Implementation

### Backend Components

**1. `backend/services/ooc_monitor.py`**
- Core OOC monitoring logic
- AI-powered IC content detection
- Warning and ban management
- Violation tracking

**2. `backend/routes/messages.py`**
- Integrated OOC checking before saving messages
- Returns OOC warnings in API response
- Blocks banned users from sending messages

**3. `backend/fix_missing_ooc_rooms.py`**
- Utility script to create OOC rooms for campaigns that don't have them
- Should be run when adding this feature to existing campaigns

### API Integration

**Message Endpoint**: `POST /api/campaigns/{campaign_id}/locations/{location_id}`

**Response with OOC Warning:**
```json
{
  "message": "Message saved successfully",
  "data": {
    "id": 123,
    "content": "My character draws his sword",
    "role": "user",
    ...
  },
  "ooc_warning": "⚠️ OOC VIOLATION WARNING (1/3)\\n\\nYour message appears to contain in-character content..."
}
```

**Response when Banned:**
```json
{
  "error": "OOC violation - temporarily banned",
  "warning": "⚠️ OOC VIOLATION - TEMPORARY BAN ISSUED\\n\\n...",
  "violation": true
}
```
Status Code: `403 Forbidden`

### Frontend Integration

**1. Display OOC Warnings**
```javascript
const response = await fetch(`/api/campaigns/${campaignId}/locations/${locationId}`, {
  method: 'POST',
  body: JSON.stringify({ content: message })
});

const data = await response.json();

if (data.ooc_warning) {
  // Display warning prominently to user
  showModal({
    title: '⚠️ OOC Violation Warning',
    message: data.ooc_warning,
    type: 'warning'
  });
}
```

**2. Handle Bans**
```javascript
if (response.status === 403 && data.violation) {
  // User has been banned
  showModal({
    title: '⛔ Temporarily Banned',
    message: data.warning,
    type: 'error'
  });
  
  // Optionally redirect user out of chat
  navigateToDashboard();
}
```

## Configuration

### Tuning Parameters

In `backend/services/ooc_monitor.py`:

```python
class OOCMonitor:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.warning_threshold = 3  # Change number of warnings before ban
        self.ban_duration_hours = 24  # Change ban duration
```

### AI Model Configuration

The OOC monitor uses a fast, lightweight model for detection:

```python
config = {
    'model': 'llama3.2:3b',  # Fast detection model
    'temperature': 0.3,       # Low for consistent detection
    'max_tokens': 100,
    'task_type': 'moderation'
}
```

**Why llama3.2:3b?**
- Fast response time (<1 second)
- Good at classification tasks
- Low GPU usage
- Consistent results with low temperature

## Testing

### Manual Testing

1. **Create a test campaign** with OOC room
2. **Send IC messages in OOC**:
   - "I draw my sword and attack!"
   - "*sneaks through the shadows*"
   - "My vampire feeds on the mortal"

3. **Verify warnings** appear after each violation
4. **Verify ban** triggers after 3rd violation
5. **Verify ban expires** after 24 hours

### Automated Testing

```bash
# Check all campaigns have OOC rooms
cd /home/lef/dev/shadowrealms-ai_dev/shadowrealms-ai
docker compose exec backend python3 /app/fix_missing_ooc_rooms.py

# Run OOC monitoring tests
docker compose exec backend python3 /app/tests/test_ooc_monitor.py
```

## Monitoring

### Check OOC Violations

```sql
-- Recent violations
SELECT 
    u.username,
    c.name as campaign,
    COUNT(*) as violations,
    MAX(ov.violated_at) as last_violation
FROM ooc_violations ov
JOIN users u ON ov.user_id = u.id
JOIN campaigns c ON ov.campaign_id = c.id
WHERE ov.violated_at > datetime('now', '-7 days')
GROUP BY ov.user_id, ov.campaign_id
ORDER BY violations DESC;

-- Currently banned users
SELECT 
    id, username, ban_until, ban_reason
FROM users
WHERE ban_until IS NOT NULL
AND ban_until > datetime('now');
```

### Logs

OOC violations are logged with:
```
⚠️  OOC violation by user {user_id} in campaign {campaign_id}. Warning count: {count}
✅ Issued {ban_duration}h temp ban to user {user_id} for OOC violations
```

## Admin Override

Admins can manually clear bans:

```sql
-- Clear a specific user's ban
UPDATE users
SET ban_until = NULL, ban_reason = NULL
WHERE id = ?;

-- Clear all expired bans
UPDATE users
SET ban_until = NULL, ban_reason = NULL
WHERE ban_until < datetime('now');
```

## Edge Cases

### 1. AI Service Unavailable
- **Behavior**: Fail open - don't block legitimate messages
- **Logged**: `⚠️  Error checking OOC violation: {error}`

### 2. False Positives
- Messages discussing character actions in third person should be allowed
- "My character should investigate the temple" → ALLOWED
- "I investigate the temple" → VIOLATION

### 3. Multiple Campaigns
- Violations are tracked PER CAMPAIGN
- A user can be banned in one campaign but not another
- Future enhancement: global bans across all campaigns

### 4. Ban Expiry
- Bans are checked on every message attempt
- Expired bans are automatically cleared
- No manual intervention needed

## Philosophy

The OOC monitoring system embodies the **"Quality Over Speed"** principle:

- **AI Detection** ensures accurate violation detection
- **Warning System** gives players a chance to learn the rules
- **Temporary Bans** are educational, not punitive
- **Clear Messages** explain what went wrong and how to fix it
- **Automatic Cleanup** prevents accumulation of old violations

The goal is to **maintain roleplay boundaries** while being **fair and educational** to players.

## Future Enhancements

1. **Configurable thresholds per campaign** (some campaigns may want stricter rules)
2. **Admin dashboard** to view violations and manage bans
3. **Appeal system** for disputed bans
4. **Global ban list** for severe repeat offenders
5. **Whitelist phrases** that admins mark as acceptable
6. **AI training** on campaign-specific examples

---

**Last Updated**: 2025-10-28  
**Version**: 0.7.5


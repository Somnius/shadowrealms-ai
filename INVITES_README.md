# ShadowRealms AI - Invite Code System

## Overview

ShadowRealms AI uses an invite-only registration system to control access. Users must have a valid invite code to register.

## Invite Code Types

- **Admin**: Full administrative access to all campaigns and settings
- **Player**: Standard player access to join campaigns

## File Structure

### `backend/invites.json` (Gitignored - Real Codes)
This file contains your actual invite codes and is **NOT** committed to Git for security.

```json
{
  "invites": {
    "YOUR-ADMIN-CODE-HERE": {
      "type": "admin",
      "description": "Admin access",
      "max_uses": 1,
      "uses": 0,
      "created_at": "2025-01-01T00:00:00",
      "created_by": "system"
    }
  }
}
```

### `backend/invites.template.json` (Template - In Git)
This is a template showing the structure. Copy this to `invites.json` and add your own codes.

## Initial Setup

1. Copy the template:
```bash
cp backend/invites.template.json backend/invites.json
```

2. Edit `backend/invites.json` with your custom invite codes
3. The `invites.json` file is automatically gitignored

## Current Active Invites

The project comes with these **example** invite codes in `backend/invites.json`:

- **ADMIN-SHADOWREALM-2025**: Admin access (1 use)
- **PLAYER-WELCOME-2025**: Player access (5 uses)

**⚠️ CHANGE THESE CODES** for production use!

## Invite Code Format

Each invite code entry has:
- `type`: "admin" or "player"
- `description`: Human-readable description
- `max_uses`: Maximum number of times the code can be used
- `uses`: Current number of uses (auto-incremented)
- `created_at`: ISO timestamp of creation
- `created_by`: Who created the invite

## Adding New Invite Codes

Edit `backend/invites.json` manually:

```json
{
  "invites": {
    "YOUR-CUSTOM-CODE-123": {
      "type": "player",
      "description": "For my friend John",
      "max_uses": 1,
      "uses": 0,
      "created_at": "2025-10-24T12:00:00",
      "created_by": "admin"
    }
  }
}
```

## Security Best Practices

1. **Never commit `invites.json`** to Git (already in `.gitignore`)
2. **Use strong, unique codes** (long, random strings)
3. **Limit max_uses** to prevent abuse
4. **Track who uses what** via the description field
5. **Rotate codes** regularly for sensitive roles

## Checking Invite Usage

The system automatically tracks:
- How many times each code has been used
- When codes reach their `max_uses` limit, they become invalid

## Future Enhancements

Planned features:
- Admin UI to manage invites
- Expiration dates for codes
- Email-based invites
- Invite code generation API endpoint


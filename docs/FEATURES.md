# Feature Documentation

**Last Updated**: 2026-10-04  
**Version**: 0.10.0

Feature notes for ShadowRealms AI that don't have their own document. The full list of changes per release is in [CHANGELOG.md](CHANGELOG.md); the plans are in [ROADMAP_v0.9.md](ROADMAP_v0.9.md) and [ROADMAP_v0.10.md](ROADMAP_v0.10.md).

---

## Table of Contents

1. [What's new in v0.9.2 to v0.10.0](#whats-new-in-v092-to-v0100)
1. [What's new in v0.9.0](#whats-new-in-v090)
2. [Admin user management, play suspension, discover/join](#admin-user-management-play-suspension-discoverjoin)
3. [Chronicle detach, join restrictions, per-campaign playing character](#chronicle-detach-join-restrictions-per-campaign-playing-character)
4. [Dice theatre and hidden rolls](#dice-theatre-and-hidden-rolls)
5. [Chat message actions and older history](#chat-message-actions-and-older-history)
6. [Gothic theme and design system](#gothic-theme-and-design-system)
7. [Character sheet PDF](#character-sheet-pdf)
8. [Invite Code System](#invite-code-system)

---

## What's new in v0.9.2 to v0.10.0

- **Dice pools from the sheet.** The Storyteller asks for a roll with a tag like `[[roll: Dexterity + Stealth, difficulty 6]]`; the server works out the pool from the speaking character's sheet (specialties, Hunger, impairment, Classic or V5) and the chat shows a roll chip that fills in the dice dialog. See [dice-v5.md](dice-v5.md) and [dice-old-wod.md](dice-old-wod.md).
- **Chat message actions and older history.** Copy, reply and delete, with the rights described [below](#chat-message-actions-and-older-history).
- **Admin: Logins & lockouts.** Lift a lockout by username or one exact IP address; a paged, filterable login audit. See [SECURITY_MODEL.md](SECURITY_MODEL.md).
- **Admin: Laya.** Label player chat (in character or not, and the intent) and run an evaluation of the Laya classifier against those labels; reports are kept and can be re-run, also from the CLI. See [laya/HOWTO.md](laya/HOWTO.md) and [laya/EVALUATION.md](laya/EVALUATION.md).
- **Under the hood (0.10.0).** The frontend builds with Vite (react-router 7, motion, i18next 26, Jest 30, lint with no warnings), the backend runs on Python 3.12, and ChromaDB is pinned to 1.5.9. Access tokens last 30 minutes and log lines are escaped.

---

## What's new in v0.9.0

- **Rules editions.** Every chronicle is **Classic** (oWoD Revised: Vampire, Werewolf, Mage) or **V5** (Vampire: The Masquerade 5th edition only), chosen at creation and locked. Each edition has its own dice engine, character forge and sheet, and rule-book search. See [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md), [rules/V5.md](rules/V5.md), [dice-old-wod.md](dice-old-wod.md), [dice-v5.md](dice-v5.md) and [CHARACTER_SHEET_BLOCKS.md](CHARACTER_SHEET_BLOCKS.md).
- **New app shell.** Real URLs: `/chronicles` (the hall), `/chronicles/new`, `/chronicles/:id` (chronicle settings), `/c/:id/:locationId` (play), `/profile`, `/profile/characters/new`, `/admin/:section`. Discord-style chat with grouped messages, unread counts, dice cards, slash command autocomplete and a **Speaking as** control; live updates over Server-Sent Events.
- **English and Greek.** The whole interface in both languages, saved per account; the Storyteller answers in the player's language.
- **AI.** Provider roles (LM Studio, Ollama, optional Anthropic / OpenAI keys), bge-m3 embeddings for English and Greek, the Laya classifier for OOC moderation. See [AI_SYSTEMS.md](AI_SYSTEMS.md).
- **Security.** Login hardening, server-side logout, rate limits, gunicorn and a production frontend build. See [SECURITY_MODEL.md](SECURITY_MODEL.md).

---

## Admin user management, play suspension, discover/join

**Status:** Shipped  
**Scope:** Admin panel (`/admin`), chronicle hall, chronicle settings

- **Suspend character play**: Staff can set a hold with reason templates and a player-visible message; the player cannot play that PC or open its chronicle until cleared.
- **Admin debug profile**: JSON aggregate of user, memberships, characters, downtime, and moderation slices.
- **Campaign membership override**: Admins can add or remove `campaign_players` rows by user and campaign ID.
- **All chronicles (v0.7.18+)**: Admin tab lists every campaign (`GET /api/admin/campaigns`) with creator metadata and opens any of them in the play view. Site **`admin`** may open any chronicle for support (messages, dice, read-state); not granted to helpers or players by default.
- **Preserve-chat account delete**: Removes a user while keeping location IC history; related rows reassigned per `docs/CHANGELOG.md` `[0.7.18]`.
- **Listed chronicles**: Storytellers mark a game **listed** and **accepting players** on the chronicle settings page; others see it in the chronicle hall and can self-join (subject to `max_players`).
- **Single locked sheet rule**: By default a player may only commit one locked character across chronicles; admins can grant `allow_multi_campaign_play` per account.

### Profile (`/profile`)

- **Account**: time zone, out-of-character portrait, password change, and **Sign out everywhere**. The interface language and the atmosphere (motion) setting are in the user menu.
- **Characters**: your characters with their portraits (change a portrait here), and **New character** (`/profile/characters/new`), which opens the forge for the chronicle's edition.
- **Downtime**: requests for changes to a locked sheet, reviewed by an admin.

---

## Chronicle detach, join restrictions, per-campaign playing character

**Status:** Shipped  
**Scope:** Campaign API, `users` / `campaign_players` columns, chronicle settings page

**Full reference:** [CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md](CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md)

- **Leave chronicle (`POST .../detach`)**: Removes `campaign_players` membership; does not delete characters. Sets `restrict_self_join_new_chronicles` on that user so **self-join to a new chronicle** requires a storyteller/staff add, or an existing sheet to **rejoin** the same campaign.
- **Per-campaign playing character**: `campaign_players.active_character_id`; IC messages use `effective_playing_character_id()`. The old global `users.active_character_id` is legacy and not used by the v0.9 interface. Switching to another PC **in the same chronicle** requires storyteller or admin/helper approval.
- **Storyteller tools**: the chronicle creator, a site admin or a helper can add a member by username and set a player's playing character on the chronicle settings page (`POST .../members`, `PUT .../players/<id>/playing-character`).

---

## Dice theatre and hidden rolls

**Status:** Shipped (v0.7.14, reworked in v0.9.0)  
**Scope:** Play view

- **Rolls** are made by the server (`POST /api/campaigns/:id/roll`), which also posts the result to chat, so nobody can post a result that wasn't rolled. The play view shows an animated roll before the result card appears.
- **Hidden rolls:** `/ai roll-hidden` (admins) and the **Hide this roll from players** option in the roll dialog (admin, helper, or chronicle owner) store results without showing them to other players.
- **V5:** Hunger dice, Willpower rerolls (which cost Willpower) and Rouse checks.
- **Details:** [dice-old-wod.md](dice-old-wod.md), [dice-v5.md](dice-v5.md).

---

## Chat message actions and older history

**Status:** v0.10 phase 3  
**Scope:** Play view (`frontend/src/features/chat/MessageActions.jsx` and `messageRules.js`, `backend/routes/messages.py`, `backend/services/message_actions.py`)

- **Actions on a message:** hover or keyboard focus shows a small toolbar (Copy, Reply, Delete). On touch screens each message has a **…** button, and a long press opens the toolbar too. Every button has a label for screen readers; Esc closes an open toolbar.
- **Copy** puts the message text on the clipboard (the Storyteller's roll tags are copied as their label).
- **Reply** (everyone): the composer shows "Replying to …" with a short excerpt and a cancel button (Esc cancels too). The sent line shows a compact quote above it; clicking the quote scrolls to the original and highlights it if it is loaded. The message is saved with `reply_to_id`, which must be a message in the same room that the poster can see; a deleted original leaves the reply without a quote (`ON DELETE SET NULL`).
- **Delete** (with a confirm dialog; the row disappears at once and comes back if the server refuses):
  - players delete **their own** messages; there is no editing;
  - the chronicle's owner (its Storyteller) and site admins delete **any** message;
  - players can't delete **dice rows** (roll results, Rouse lines) or **Storyteller (AI) messages**, even ones their action produced. Deleting a roll result also deletes its dice animation marker.
  - `DELETE /api/messages/<id>` returns `{"deleted_ids": [...]}`, or 403 with `code` `message_not_yours`, `dice_message_staff_only` or `ai_message_staff_only`. Other clients drop the row through the live stream (the room's reset counter). The message's AI memory embedding is removed too.
- **Older history:** the room opens with the newest 150 messages. Scrolling near the top, or the **Load older messages** button there, loads the 50 before them (`GET /api/campaigns/<c>/locations/<l>?before_id=<id>&limit=<n>`, n up to 100, answers `{"messages": [...], "has_more": bool}` in chronological order) without moving what you are reading. When there is nothing older, the list shows "The beginning of <room>". Hidden rolls are filtered in the query, so pages count only messages you can see.

---

## Gothic theme and design system

v0.9.0 replaced the old gothic theme with a design system: original SVG glyphs and clan sigils, motion, an atmosphere layer (fog, candle glow, blood effects on botches) with a Full / Subtle / Off setting, and accessible contrast.

- Reference: [frontend/src/design/README.md](../frontend/src/design/README.md).
- Guided theme preview: **`/showcase`**, and the component playground at **`/showcase/design`** (both open without signing in).
- The pre-0.9 theme description (`gothic-theme.css`, `GothicDecorations`, `SimpleApp.js`) is archived in [archive/GOTHIC_THEME_V06.md](archive/GOTHIC_THEME_V06.md).

---

## Character sheet PDF

**Export PDF** on the "Your character" card in the play panel (next to Character sheet and Portrait) and in the sheet window downloads the sheet as `<name>.pdf`, a fillable two-page form made for black-and-white printers.

- **Endpoint:** `GET /api/characters/<id>/sheet.pdf`, `?paper=letter` for US Letter (A4 otherwise; the button picks Letter for en-US/CA/MX/PH browsers). Allowed for the character's owner, the chronicle's Storyteller (its creator) and admins/helpers; anyone else gets 404. Rate limited to 20 a minute. Code: `backend/services/character_sheet_pdf.py`.
- **Editions:** V5 (identity, attributes, skills with specialties, disciplines with powers, advantages and flaws, health/willpower with superficial and aggravated rows, humanity, stains, hunger, blood potency, convictions and touchstones, chronicle tenets, background and notes) and Classic Revised for Vampire, Werewolf and Mage (attributes, abilities with custom rows, disciplines/backgrounds/virtues or gifts/spheres, humanity or path, willpower, blood pool by generation, health levels, merits and flaws, combat, description, possessions). `wod_meta.rituals` and `wod_meta.experience` (total, spent, unspent, log) print when the sheet has them.
- **Fillable:** every value is a form field pre-filled from the saved sheet: text fields for words, one checkbox per dot or tracker box. On a crowded V5 sheet, entries that don't get a row of their own are listed under Notes, and long text shrinks to fit its box.
- **Look:** black ink on white only (no grey, so mono printers print it clean): hairline frames, ornamental rules, the sigil as line art. Headings and labels are Cinzel; everything a player wrote is EB Garamond, Greek included. Both fonts are SIL OFL and live in `backend/assets/fonts` with their licences.
- **Greek in the fields:** the pre-filled values are drawn into each field with the embedded EB Garamond, so they show correctly everywhere. When a player types into a field, the viewer redraws it with the field's own font, an embedded Latin + monotonic Greek cut of EB Garamond (`backend/scripts/build_form_font.py`). Tested: poppler redraws typed Greek in that font; PDFium (Chrome, Edge) shows typed Greek correctly but in a fallback sans. Not tested yet: Acrobat, macOS Preview, Firefox. Polytonic Greek and other characters outside the cut (e.g. ×) have no glyph in it.

---

## Invite Code System

### Overview

ShadowRealms AI uses an invite-only registration system to control access. Users must have a valid invite code to register.

### Invite Code Types

- **Admin**: Full administrative access to all campaigns and settings
- **Player**: Standard player access to join campaigns

### File Structure

#### `backend/invites.json` (gitignored, real codes)
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

#### `backend/invites.template.json` (template, in git)
This is a template showing the structure. Copy this to `invites.json` and add your own codes.

### Initial Setup

1. Copy the template:
```bash
cp backend/invites.template.json backend/invites.json
```

2. Edit `backend/invites.json` with your custom invite codes
3. The `invites.json` file is automatically gitignored

The template only contains placeholder codes (`EXAMPLE-ADMIN-CODE-12345`, `EXAMPLE-PLAYER-CODE-67890`). Replace them with your own long, random codes before anyone registers.

### Invite Code Format

Each invite code entry has:
- `type`: "admin" or "player"
- `description`: Human-readable description
- `max_uses`: Maximum number of times the code can be used
- `uses`: Current number of uses (auto-incremented)
- `created_at`: ISO timestamp of creation
- `created_by`: Who created the invite

#### Adding New Invite Codes

Admins can list and create invite codes in the app under **Admin → Invite codes** (`/admin/invites`; `GET`/`POST /api/admin/invites`). You can also edit `backend/invites.json` by hand:

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

### Security Best Practices

1. **Never commit `invites.json`** to Git (already in `.gitignore`)
2. **Use strong, unique codes** (long, random strings)
3. **Limit max_uses** to prevent abuse
4. **Track who uses what** via the description field
5. **Rotate codes** regularly for sensitive roles

### Checking Invite Usage

The system automatically tracks:
- How many times each code has been used
- When codes reach their `max_uses` limit, they become invalid

Claims are atomic across threads and gunicorn workers, so two sign-ups can't use the same last slot of a code. Wrong invite codes count toward a lockout (see [SECURITY_MODEL.md](SECURITY_MODEL.md)), and if SMTP and `MAIL_ADMIN_ALERT_EMAIL` are set, invalid sign-up attempts send the admin an email.

### Possible later additions

- Expiration dates for codes
- Email-based invites


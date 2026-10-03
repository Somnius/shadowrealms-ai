# Roadmap v0.9 — "Into the Night"

Started 2026-10-04. Each phase: research → build → at least 2 reviews → commit + push → docs, wiki and project board updated. Status here is kept current while the work runs.

| # | Phase | Status |
|---|---|---|
| 1 | Rules: classic oWoD done properly + V5 per campaign | in progress |
| 2 | AI: better local models, optional cloud providers, Laya/Jev classification, Greek replies | todo |
| 3 | UI/UX: one clear navigation, Discord-style chat, EN/EL interface | todo |
| 4 | Gothic theme redesign: animated SVG glyphs, motion, atmosphere | todo |
| 5 | Security + public site: hardened login, production server, srai.srv-box.com behind a gate | todo |
| 6 | Theme preview page rebuilt (last on purpose) | todo |

## Decisions

- A campaign uses exactly one ruleset: **Classic (oWoD Revised)** or **V5**. It's picked when the campaign is created and can't be mixed. V5 applies to Vampire: The Masquerade.
- Glyphs and symbols are original art, not the official White Wolf / Paradox clan logos (the repo is public).
- Local models first. Anthropic / OpenAI only via API keys, set by an admin, off by default. Subscriptions are not API access.
- Classification: Laya (open weights, local) first; Typesafe Jev (hosted) optional with an API key.
- Greek: full EN/EL interface plus Storyteller replies in the player's language.
- Public access at `srai.srv-box.com` stays behind an HTTP basic-auth gate until it's been tested.

## Phase details

### Phase 1 — Rules
- Per-campaign `rules_edition` (`classic` | `v5`), chosen at creation, shown everywhere.
- Classic: Revised Storyteller d10 pools, difficulty 2–10, 1s cancel, botch, specialties (10s count double), Willpower auto-success.
- V5: d10 pools vs successes needed, 6+ success, pairs of 10s = critical (+2 each pair), Hunger dice, messy critical, bestial failure, Rouse checks, Willpower rerolls (up to 3 normal dice).
- Character sheet + creation per edition (V5: Hunger, Humanity, Blood Potency, Predator type, disciplines as levels, skills instead of abilities).
- Storyteller prompt + rule-book RAG set follow the campaign's edition.

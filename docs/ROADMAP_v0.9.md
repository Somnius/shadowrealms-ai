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
- Classic: Revised Storyteller d10 pools, difficulty 2–10, 1s cancel successes, botch only when no successes were rolled at all and a 1 shows (core p. ~185), specialties re-roll 10s for extra successes (Revised), Willpower = 1 automatic success that can't be cancelled.
- V5: d10 pools vs successes needed, 6+ success, pairs of 10s = critical (+2 each pair), Hunger dice, messy critical, bestial failure, Rouse checks, Willpower rerolls (up to 3 normal dice).
- Character sheet + creation per edition (V5: Hunger, Humanity, Blood Potency, Predator type, disciplines as levels, skills instead of abilities).
- Storyteller prompt + rule-book RAG set follow the campaign's edition.

### Phase 2 — AI (research done, see findings)
- Greek: the current chat model `google/gemma-4-e2b` answers Greek prompts in English or with errors. `llama-krikri-8b-instruct` (ILSP, already installed) writes clean Greek. Plan: route by the player's language (Krikri for Greek).
- Embeddings: `nomic-embed-text-v1.5` can't separate Greek texts (a Greek question scored an unrelated Greek text 0.785 vs 0.795 for the right one). `bge-m3` (downloaded, 635 MB) ranks the right passage first in both languages and across languages. `Qwen3-Embedding-0.6B` was the first pick but fails to load in LM Studio's current llama.cpp runtime (2.51.0).
- Switching embedders means re-embedding what's already in ChromaDB.
- Qwen3.5 needs `reasoning_effort: none` or it spends the whole budget thinking.
- Laya: train one multi-task classifier (OOC vs in-character, message intent) with the recmeets recipe (`~/dev/recmeets/scripts/laya/`), serve it as ONNX on CPU. Jev (Typesafe, `POST https://api.typesafe.ai/v1/systemone`, Bearer key) as the optional hosted alternative with the same request shape.
- Cloud (optional, admin-set API keys): Anthropic Messages API, OpenAI Responses API.

### Phase 5 — public site infrastructure (done early, 2026-10-04 ~03:05)
- `srai.srv-box.com` → DietPi `snikket-proxy` nginx (`/mnt/ext_data/snikket/proxy-srai.conf`, mounted in its `docker-compose.yml`; backups `docker-compose.yml.bak-srai-*`, `renewal/srv-box.com.conf.bak-srai-*`) → `http://10.0.0.3:80` (this machine's nginx; ufw allows the LAN).
- TLS: the shared Let's Encrypt cert `srv-box.com` was expanded to 20 names including `srai.srv-box.com` (dry run first, then real; renews with the others).
- Gate: HTTP basic auth (`/mnt/ext_data/snikket/auth/srai.htpasswd`). Credentials are only in `.srai-gate-credentials.txt` in the repo folder (gitignored, mode 600).
- Verified: no auth/wrong password → 401, with gate creds the app + API answer over HTTPS with a valid cert, HTTP → HTTPS redirect, and all 19 existing subdomains answer exactly as before the change (5 of them were already returning 502 before: ag, bz, f, git, vw).
- Still to do in phase 5: production frontend build + gunicorn instead of the dev servers, login hardening.

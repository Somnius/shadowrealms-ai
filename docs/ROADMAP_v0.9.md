# Roadmap v0.9 — "Into the Night"

Started 2026-10-04. Each phase: research → build → at least 2 reviews → commit + push → docs, wiki and project board updated. Status here is kept current while the work runs.

| # | Phase | Status |
|---|---|---|
| 1 | Rules: classic oWoD done properly + V5 per campaign | **done** (merged 2026-10-04 ~03:25) |
| 2 | AI: better local models, optional cloud providers, Laya/Jev classification, Greek replies | **done** |
| 3 | UI/UX: one clear navigation, Discord-style chat, EN/EL interface | **done** |
| 4 | Gothic theme redesign: animated SVG glyphs, motion, atmosphere | **done** |
| 5 | Security + public site: hardened login, production server, the maintainer's test instance behind a gate | **done** (gate removed 2026-10-04) |
| 6 | Theme preview page rebuilt (last on purpose) | **done** |

## Decisions

- A campaign uses exactly one ruleset: **Classic (oWoD Revised)** or **V5**. It's picked when the campaign is created and can't be mixed. V5 applies to Vampire: The Masquerade.
- Glyphs and symbols are original art, not the official White Wolf / Paradox clan logos (the repo is public).
- Local models first. Anthropic / OpenAI only via API keys, set by an admin, off by default. Subscriptions are not API access.
- Classification: Laya (open weights, local) first; Typesafe Jev (hosted) optional with an API key.
- Greek: full EN/EL interface plus Storyteller replies in the player's language.
- Public access to the maintainer's test instance stays behind an HTTP basic-auth gate until it's been tested (removed 2026-10-04; the site is open with the app's own login).

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
- Laya: train one multi-task classifier (OOC vs in-character, message intent) with the recipe from another local project (recmeets), serve it as ONNX on CPU. Jev (Typesafe, `POST https://api.typesafe.ai/v1/systemone`, Bearer key) as the optional hosted alternative with the same request shape.
- Cloud (optional, admin-set API keys): Anthropic Messages API, OpenAI Responses API.

Built (2026-10-04, details in `docs/AI_SYSTEMS.md` → "v0.9: providers, …"):
- Provider layer (`services/ai_providers.py`, `ai_roles.py`): LM Studio (default), Ollama, Anthropic Messages API, OpenAI Chat Completions behind one `generate(messages, params)`. Roles per admin panel: Storyteller EN, Storyteller EL, utility, classifier. Fallback cloud → local → Ollama; a model LM Studio can't load is skipped for 5 min. Cloud keys: admin-entered, Fernet-encrypted (HKDF from `FLASK_SECRET_KEY`), only shown masked (`••••abcd`), with a test button. Off by default.
- Greek: language detection (Greek-letter ratio; Greeklish = EN for now; short messages fall back to the new `users.ui_language`), Greek → `llama-krikri-8b-instruct`, explicit reply-language instruction.
- Embeddings: all ChromaDB collections were on Chroma's default English MiniLM (384 dims), not nomic. Now one embedder for all reads/writes, `text-embedding-bge-m3` (`EMBEDDING_MODEL`), with an idempotent re-embed (startup, admin button, `reembed_rag.py`). Live data re-embedded (campaign_memory 5, message_memory 1, others empty).
- Classifier (`services/classifier.py`): Laya (local ONNX, loads `data/laya/model` + `infer.py` when present), Typesafe Jev (admin key), LLM prompt fallback. Used by the OOC monitor and for intent routing. Measured: `llama3.2:3b` flagged 7/7 OOC messages as in character, so the LLM fallback uses the loaded LM Studio model (gemma-4-e2b: 16/16 on a small EN/EL set).
- Security: players could post as the AI Storyteller (`role: assistant`) and so also skip the OOC monitor. Now only admins, dice markers, or text the AI endpoints handed that user for that room (one-time grant) can be saved as assistant.
- Measured VRAM: with ComfyUI holding 7.1 GB and gemma-4-e2b loaded, LM Studio can't also load Krikri (the Greek reply then falls back to gemma). Krikri alone fits. Running Krikri as the single model (both languages) is the workable setup while ComfyUI is resident.
- Still open: the trained Laya model (separate work in `ml/laya/`); Greek reply quality with Krikri actually loaded (see the phase 2 report); Greeklish detection; the storyteller prompt can exceed an 8k context in busy rooms (pre-existing).

### Phase 5 — public site infrastructure (done early, 2026-10-04 ~03:05)
- The test instance's subdomain → nginx on a reverse proxy on another host on the LAN → this machine's nginx on port 80 (the firewall allows the LAN). The proxy's config was backed up before the change.
- TLS: a shared Let's Encrypt certificate was expanded to include the subdomain (dry run first, then real; renews with the others).
- Gate: HTTP basic auth on the reverse proxy (the preview gate, removed 2026-10-04). The credentials are not in version control.
- Verified: no auth/wrong password → 401, with gate creds the app + API answer over HTTPS with a valid cert, HTTP → HTTPS redirect, and all 19 existing subdomains answer exactly as before the change (5 of them were already returning 502 before: ag, bz, f, git, vw).
- Still to do in phase 5: production frontend build + gunicorn instead of the dev servers, login hardening.

### Phase 5 — login hardening + production backend server (2026-10-04)
Details: `docs/SECURITY_MODEL.md`.
- Audit of `routes/auth.py` and related code. Fixed: no brute-force protection at all; login said "Account is deactivated" before checking the password (enumeration of disabled accounts) and took less time for unknown usernames; logout did nothing server-side and tokens stayed valid for 6 h after logout, ban, deactivation or a password reset; passwords over 72 bytes made login answer 500 (bcrypt 5); the welcome email contained the plaintext password; `CORS(app)` allowed every origin; the backend trusted a client-supplied `X-Forwarded-For` for the invite alert; exception text in several responses (rule books, AI health, health check, README, re-embed); `Config.debug_env_vars()` printed the secrets; invite use was check-then-write (two signups could overuse a code); the backend ran Flask's dev server and listened on all interfaces.
- Now: password policy (12+ characters, max 72 bytes, common-password list), bcrypt cost 12 with rehash on login, generic login errors with a dummy hash for unknown users, time-limited lockouts per account+IP / account / IP / wrong invites (Redis), Flask-Limiter limits with a JSON 429, server-side revocation (token_version trigger + jti blocklist + refresh rotation with reuse detection in an HttpOnly SameSite=Strict cookie), logout / logout-all / change-password endpoints, admin unlock + `auth_events` audit log, security headers and no-store on the API, CORS allow-list (`CORS_ORIGINS`, empty by default), generic 500s, nginx realip for the real client IP with one trusted hop.
- Production server: gunicorn gthread (2 workers × 48 threads, preload, 127.0.0.1:5000), `APP_SERVER=flask` keeps the dev server. SSE streams capped at 20 per worker.
- Frontend changes (refresh on 401, server logout, 429/503 handling, change-password screen): done, see `frontend/src/app/http.js` and `AuthContext.jsx`. Access tokens still default to 360 minutes in `docker-compose.yml` (`JWT_ACCESS_TOKEN_MINUTES`); lowering it to 30 is listed under "Open / next".

### Dependency security (2026-10-04)
- 8 Python security PRs from Dependabot merged (all checks green).
- npm: `npm audit fix` applied (lockfile only, tested with a clean install, tests and build). The remaining npm audit findings are react-scripts (Create React App) build tooling that never ships to the browser. Proper fix: move the frontend from CRA to Vite (planned, after v0.9).

### Phase 2 — closing checks (2026-10-04 ~05:25)
- Laya classifier live in the backend (gunicorn workers load it lazily, ~0.23 s/message): IC "*draws my fangs…*" → 0.965, OOC "what time do we play friday?" → 0.034.
- Krikri verified live through `/api/ai/chat`: a Greek message got a natural, grammatical Greek reply (no foreign-script characters, no fallback); English works too. With ComfyUI holding ~7 GB of VRAM, LM Studio runs **Krikri as the only chat model** (plus bge-m3), and the English role follows the loaded model.


### Phase 5 — production frontend (2026-10-04 ~06:10)
- nginx serves the static build (`./scripts/build-frontend.sh`) instead of the React dev server, with a strict CSP (scripts only from the site), gzip, and long caching for hashed assets. Checked in Chromium with no CSP violations.

## Open / next
- ~~Remove the preview gate once tested (one block in the reverse proxy's site config).~~ Done 2026-10-04.
- Label 300–500 real chat messages and re-check the Laya thresholds on them.
- Server-computed dice pools from the character sheet; message actions (reply/copy/delete) and older-history paging in chat.
- Move the frontend from Create React App to Vite (most remaining npm audit findings are CRA build tooling).
- `JWT_ACCESS_TOKEN_MINUTES=30` now that the frontend refreshes tokens (compose still has 360).
- Have a person compare the 16 original clan sigils side by side with the official marks.

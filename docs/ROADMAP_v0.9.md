# Roadmap v0.9 — "Into the Night"

Started 2026-10-04. Each phase: research → build → at least 2 reviews → commit + push → docs, wiki and project board updated. Status here is kept current while the work runs.

| # | Phase | Status |
|---|---|---|
| 1 | Rules: classic oWoD done properly + V5 per campaign | **done** (merged 2026-10-04 ~03:25) |
| 2 | AI: better local models, optional cloud providers, Laya/Jev classification, Greek replies | in progress |
| 3 | UI/UX: one clear navigation, Discord-style chat, EN/EL interface | todo |
| 4 | Gothic theme redesign: animated SVG glyphs, motion, atmosphere | todo |
| 5 | Security + public site: hardened login, production server, srai.srv-box.com behind a gate | infra done, app hardening todo |
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

Built (2026-10-04, details in `docs/AI_SYSTEMS.md` → "v0.9: providers, …"):
- Provider layer (`services/ai_providers.py`, `ai_roles.py`): LM Studio (default), Ollama, Anthropic Messages API, OpenAI Chat Completions behind one `generate(messages, params)`. Roles per admin panel: Storyteller EN, Storyteller EL, utility, classifier. Fallback cloud → local → Ollama; a model LM Studio can't load is skipped for 5 min. Cloud keys: admin-entered, Fernet-encrypted (HKDF from `FLASK_SECRET_KEY`), only shown masked (`••••abcd`), with a test button. Off by default.
- Greek: language detection (Greek-letter ratio; Greeklish = EN for now; short messages fall back to the new `users.ui_language`), Greek → `llama-krikri-8b-instruct`, explicit reply-language instruction.
- Embeddings: all ChromaDB collections were on Chroma's default English MiniLM (384 dims), not nomic. Now one embedder for all reads/writes, `text-embedding-bge-m3` (`EMBEDDING_MODEL`), with an idempotent re-embed (startup, admin button, `reembed_rag.py`). Live data re-embedded (campaign_memory 5, message_memory 1, others empty).
- Classifier (`services/classifier.py`): Laya (local ONNX, loads `data/laya/model` + `infer.py` when present), Typesafe Jev (admin key), LLM prompt fallback. Used by the OOC monitor and for intent routing. Measured: `llama3.2:3b` flagged 7/7 OOC messages as in character, so the LLM fallback uses the loaded LM Studio model (gemma-4-e2b: 16/16 on a small EN/EL set).
- Security: players could post as the AI Storyteller (`role: assistant`) and so also skip the OOC monitor. Now only admins, dice markers, or text the AI endpoints handed that user for that room (one-time grant) can be saved as assistant.
- Measured VRAM: with ComfyUI holding 7.1 GB and gemma-4-e2b loaded, LM Studio can't also load Krikri (the Greek reply then falls back to gemma). Krikri alone fits. Running Krikri as the single model (both languages) is the workable setup while ComfyUI is resident.
- Still open: the trained Laya model (separate work in `ml/laya/`); Greek reply quality with Krikri actually loaded (see the phase 2 report); Greeklish detection; the storyteller prompt can exceed an 8k context in busy rooms (pre-existing).

### Phase 5 — public site infrastructure (done early, 2026-10-04 ~03:05)
- `srai.srv-box.com` → DietPi `snikket-proxy` nginx (`/mnt/ext_data/snikket/proxy-srai.conf`, mounted in its `docker-compose.yml`; backups `docker-compose.yml.bak-srai-*`, `renewal/srv-box.com.conf.bak-srai-*`) → `http://10.0.0.3:80` (this machine's nginx; ufw allows the LAN).
- TLS: the shared Let's Encrypt cert `srv-box.com` was expanded to 20 names including `srai.srv-box.com` (dry run first, then real; renews with the others).
- Gate: HTTP basic auth (`/mnt/ext_data/snikket/auth/srai.htpasswd`). Credentials are only in `.srai-gate-credentials.txt` in the repo folder (gitignored, mode 600).
- Verified: no auth/wrong password → 401, with gate creds the app + API answer over HTTPS with a valid cert, HTTP → HTTPS redirect, and all 19 existing subdomains answer exactly as before the change (5 of them were already returning 502 before: ag, bz, f, git, vw).
- Still to do in phase 5: production frontend build + gunicorn instead of the dev servers, login hardening.

### Dependency security (2026-10-04)
- 8 Python security PRs from Dependabot merged (all checks green).
- npm: `npm audit fix` applied (lockfile only, tested with a clean install, tests and build). The remaining npm audit findings are react-scripts (Create React App) build tooling that never ships to the browser. Proper fix: move the frontend from CRA to Vite (planned, after v0.9).

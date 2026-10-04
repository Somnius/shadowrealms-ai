<div align="center">

# ShadowRealms AI

![ShadowRealms AI](assets/logos/shadowrealms-banner.png)

### Self-hosted AI Storyteller for World of Darkness chronicles

[![Version](https://img.shields.io/badge/version-0.10.0-blue.svg)](docs/CHANGELOG.md)
[![CI](https://github.com/Somnius/shadowrealms-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Somnius/shadowrealms-ai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Somnius/shadowrealms-ai/actions/workflows/codeql.yml/badge.svg)](https://github.com/Somnius/shadowrealms-ai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

![A V5 chronicle in play: dice cards, a Rouse check, the AI Storyteller's reply and the character panel](assets/screenshots/v0.9/play-v5.webp)

| Sign-in | Chronicle hall | Bestial failure |
|---|---|---|
| ![Sign-in page with the animated sigil](assets/screenshots/v0.9/login-desktop.webp) | ![Chronicle hall with a Classic and a V5 chronicle](assets/screenshots/v0.9/hall.webp) | ![A V5 bestial failure with the blood-drip effect](assets/screenshots/v0.9/dice-bestial-failure.webp) |

| V5 character sheet | Playing in Greek | Theme preview |
|---|---|---|
| ![Read-only V5 character sheet](assets/screenshots/v0.9/character-sheet-v5.webp) | ![The play view with the interface and the Storyteller in Greek](assets/screenshots/v0.9/play-greek.webp) | ![The theme preview page at /showcase](assets/screenshots/v0.9/showcase-hero.webp) |

More: [all v0.9 screenshots with captions](assets/screenshots/v0.9/README.md) and [a V5 roll, animated](assets/screenshots/v0.9/dice-roll-v5-animated.webp).

---

## What it is

ShadowRealms AI is a web app for running World of Darkness chronicles with an AI Storyteller. You host it yourself: Docker for the app, and local language models through LM Studio and Ollama, so the stories stay on your machine. Every chronicle is either Classic (oWoD Revised) or V5, and the interface and the Storyteller work in English and Greek.

## Features

### Rules editions

- Each chronicle picks **Classic** (Vampire, Werewolf, Mage on the Revised rules) or **V5** (Vampire: The Masquerade 5th edition) when it's created, and keeps it.
- Classic dice follow Revised: difficulty 2 to 10, 1s cancel successes, a botch only when nothing succeeded, specialties re-roll 10s, Willpower as one uncancellable success.
- V5 dice: Hunger dice, pairs of 10s, messy criticals, bestial and total failures, Willpower rerolls, Rouse checks.
- The Storyteller's prompt and the rule-book search follow the chronicle's edition. The rules as the app implements them: [Classic](docs/rules/CLASSIC_REVISED.md) and [V5](docs/rules/V5.md).

### Play

- Discord-style chat: grouped messages, unread counts, jump to present, in-character and out-of-character rooms.
- Live updates over server-sent events (falls back to polling).
- Dice cards: rolls are made and posted by the server, so a dice card in the chat is always a real roll.
- Slash commands with autocomplete: `/roll`, `/me`, `/chat` for everyone, and `/ai` commands for admins (`/ai help` lists them).
- One "Speaking as" control: your character, yourself out of character, or the Storyteller voice for staff.

### Characters

- A character forge per edition: Classic with the Revised budgets (7/5/3, 13/9/5, virtues, 15 freebies), V5 with attribute and skill spreads, Predator type, disciplines, advantages and flaws.
- Read-only sheets with trackers (Hunger, Willpower, Humanity), portraits, and one playing character per chronicle.
- Sheets lock after creation; later changes go through downtime requests the Storyteller approves.

### AI

- Roles instead of one model: English Storyteller, Greek Storyteller, utility and classifier, each set in the admin panel.
- Greek replies with `llama-krikri-8b-instruct`; the Storyteller answers in the player's language.
- Long-term memory and rule-book search with multilingual `bge-m3` embeddings in ChromaDB.
- OOC rooms are moderated by the Laya classifier (trained locally from `ml/laya/`) or the loaded LLM; warnings and bans apply per chronicle.
- Optional cloud providers: an admin can add Anthropic or OpenAI API keys (stored encrypted, off by default).

### Gothic theme

- 97 original SVG glyphs and sigils, animated dice, fog, candle glow and blood effects on botches.
- An atmosphere setting per account: Full, Subtle or Off.
- A guided theme preview at `/showcase`.

### Security

- Rate limits and lockouts, token revocation with refresh rotation, a password policy, an audit log.
- gunicorn behind nginx with a strict Content-Security-Policy; only nginx is reachable from the network.
- See [SECURITY.md](SECURITY.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

### Admin

- Invite codes, all chronicles, users (bans, password resets), downtime requests, the moderation log.
- AI system: models per role, cloud keys, embeddings and re-embedding.

---

## Quick start

You need Linux with Docker and the Compose v2 plugin (`docker compose`), [LM Studio](https://lmstudio.ai/) with its `lms` command, and [Ollama](https://ollama.com/) on the host. An NVIDIA GPU is strongly recommended. The [Installation](https://github.com/Somnius/shadowrealms-ai/wiki/Installation) page in the wiki has every step in detail.

1. Clone the repository and create your config:

```bash
git clone https://github.com/Somnius/shadowrealms-ai.git
cd shadowrealms-ai
cp env.template .env
cp backend/invites.template.json backend/invites.json
python3 scripts/generate_secret_key.py
```

2. Edit `.env`: put your own keys in `FLASK_SECRET_KEY` and `JWT_SECRET_KEY`, and generate `POSTGRES_USER` and `POSTGRES_PASSWORD` ([how](docs/POSTGRESQL_ENV_SETUP.md)). Never keep the template values.
3. Edit `backend/invites.json`: replace the example codes with your own random ones and keep one admin code for yourself. Registration needs an invite code.
4. Download `llama-krikri-8b-instruct` and `text-embedding-bge-m3` in LM Studio, then load them. `gemma-4-e2b` is an optional smaller English chat model (`lms get gemma-4-e2b --gguf -y`).

```bash
lms server start
lms load llama-krikri-8b-instruct -y    # Storyteller, English and Greek
lms load text-embedding-bge-m3 -y       # memory and rule-book embeddings
ollama pull llama3.2:3b                 # utility model
```

5. Start the stack and build the frontend:

```bash
./docker-up.sh
./scripts/build-frontend.sh
```

6. Open http://localhost, register with your admin invite code (passwords need 12+ characters), create a chronicle, and type `/ai health` in its chat to check LM Studio, Ollama and ChromaDB.

For development, `docker compose --profile dev up -d frontend` starts the live-reload frontend (point nginx at it, see [docs/DOCKER_ENV_SETUP.md](docs/DOCKER_ENV_SETUP.md)), and `APP_SERVER=flask` with `FLASK_ENV=development` in `.env` runs the Flask dev server instead of gunicorn. Don't use the dev server on anything reachable from outside.

## Models and hardware

| Role | Default | Where to change it |
|---|---|---|
| Storyteller (English) | the model LM Studio has loaded | Admin, AI system, or `LM_STUDIO_MODEL` |
| Storyteller (Greek) | `llama-krikri-8b-instruct` (LM Studio) | Admin, AI system, or `STORYTELLER_EL_MODEL` |
| Utility | `llama3.2:3b` (Ollama) | Admin, AI system, or `UTILITY_PROVIDER` and `UTILITY_MODEL` |
| Classifier | Laya if its model is in `data/laya/model`, otherwise the loaded LM Studio model | Admin, AI system (also Typesafe Jev with a key) |
| Embeddings | `text-embedding-bge-m3` (LM Studio) | `EMBEDDING_MODEL` (the collections are re-embedded at the next start) |

- It's developed on Linux with a 16 GB NVIDIA GPU. Krikri needs about 5 GB of VRAM.
- If something else holds the GPU, load only Krikri in LM Studio: the English role follows the loaded model, so Krikri then answers in both languages.
- A Storyteller reply gets 45 seconds per model and 55 seconds in total before it falls back (`STORYTELLER_ATTEMPT_TIMEOUT`, `STORYTELLER_TIME_BUDGET`).
- More in the wiki's [AI Models](https://github.com/Somnius/shadowrealms-ai/wiki/AI-Models) page and [docs/AI_SYSTEMS.md](docs/AI_SYSTEMS.md).

## Documentation

- [docs/README.md](docs/README.md): index of everything in `docs/`
- Wiki: [Installation](https://github.com/Somnius/shadowrealms-ai/wiki/Installation), [Configuration](https://github.com/Somnius/shadowrealms-ai/wiki/Configuration), [Rules Editions](https://github.com/Somnius/shadowrealms-ai/wiki/Rules-Editions), [AI Models](https://github.com/Somnius/shadowrealms-ai/wiki/AI-Models), [Architecture](https://github.com/Somnius/shadowrealms-ai/wiki/Architecture), [Security](https://github.com/Somnius/shadowrealms-ai/wiki/Security), [Troubleshooting](https://github.com/Somnius/shadowrealms-ai/wiki/Troubleshooting)
- [docs/CHANGELOG.md](docs/CHANGELOG.md): every release
- [docs/ROADMAP_v0.10.md](docs/ROADMAP_v0.10.md): the plan from v0.9.2 to v0.10
- [docs/ROADMAP_v0.9.md](docs/ROADMAP_v0.9.md): the v0.9 plan

---

## Contributing

Contributions are welcome. Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) first, and use [GitHub Issues](https://github.com/Somnius/shadowrealms-ai/issues) for bugs and feature ideas.

## Security

Please don't open a public issue for a vulnerability. Report it privately from the Security tab of this repository; [SECURITY.md](SECURITY.md) has the details.

## License

MIT, see [LICENSE](LICENSE).

## Credits

- Made with ❤️ for tabletop RPG games by **Lefteris Iliadis** ([Somnius](https://github.com/Somnius), @SomniusX).
- Built with the help of [Cursor AI](https://cursor.sh).
- Greek Storyteller model: Llama-Krikri by ILSP. Embeddings: bge-m3 by BAAI.

## Disclaimer

Not affiliated with or endorsed by Paradox Interactive or White Wolf/Renegade; World of Darkness and Vampire: The Masquerade are their trademarks. All glyphs and sigils are original; no rulebook text is included — bring your own books.

---

## Demo video

[![ShadowRealms AI Demo](https://img.youtube.com/vi/9RGGb-F5Y2M/maxresdefault.jpg)](https://www.youtube.com/watch?v=9RGGb-F5Y2M)

**[▶️ Watch the demo on YouTube](https://www.youtube.com/watch?v=9RGGb-F5Y2M)**

> **Version 0.7.0 Preview:** This demo showcases the frontend interface in its current state. Please note that not all features are fully functional yet—this is a first look at the user interface and design direction of ShadowRealms AI.

The current interface is very different; see the screenshots at the top.

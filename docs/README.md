# ShadowRealms AI Documentation

Index of the documentation in this folder (current release: v0.10.0). The [project wiki](https://github.com/Somnius/shadowrealms-ai/wiki) has step-by-step pages for installation, configuration, AI models, rules editions, books, architecture and troubleshooting.

## Getting started

- [Main README](../README.md): what ShadowRealms AI is, screenshots, quick start
- [DOCKER_ENV_SETUP.md](DOCKER_ENV_SETUP.md): first run, services and ports, production build vs dev server, every environment variable
- [POSTGRESQL_ENV_SETUP.md](POSTGRESQL_ENV_SETUP.md): generating the database credentials

## Playing: rules, dice and characters

- [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md) and [rules/V5.md](rules/V5.md): the rules the app implements for each edition (data in `classic.json` and `v5.json`)
- [dice-old-wod.md](dice-old-wod.md): Classic (Revised) dice
- [dice-v5.md](dice-v5.md): V5 dice (Hunger, criticals, Rouse checks, Willpower rerolls)
- [character-creation-world-of-darkness.md](character-creation-world-of-darkness.md): Classic character creation for Vampire, Werewolf and Mage
- [CHARACTER_SHEET_BLOCKS.md](CHARACTER_SHEET_BLOCKS.md): how the character forge stores each sheet block, Classic and V5
- [CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md](CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md): joining and leaving chronicles, the playing character per chronicle
- [location-naming-world-of-darkness.md](location-naming-world-of-darkness.md): naming guide used for AI location suggestions
- [FEATURES.md](FEATURES.md): feature notes (what's new per release, admin tools, profile, dice theatre, chat actions, theme, invite codes)

## AI

- [AI_SYSTEMS.md](AI_SYSTEMS.md): providers and roles, Greek replies, embeddings, the classifier and OOC monitoring, memory
- [../ml/laya/README.md](../ml/laya/README.md): the Laya classifier (training and runtime)
- [laya/HOWTO.md](laya/HOWTO.md): labelling chat and evaluating Laya (admin tab, CLI); [laya/EVALUATION.md](laya/EVALUATION.md): results on real chat
- [../books/README.md](../books/README.md): syncing, parsing and importing rule books into RAG

## Security

- [../SECURITY.md](../SECURITY.md): security policy and how to report a vulnerability
- [SECURITY_MODEL.md](SECURITY_MODEL.md): authentication, sessions, rate limits, proxy trust, production server
- [SECURITY_AND_TESTING.md](SECURITY_AND_TESTING.md): CI, CodeQL, Dependabot, security tests, dependency hygiene

## Development

- [CONTRIBUTING.md](CONTRIBUTING.md): setup, project rules (EN+EL, schema), CI, commits and pull requests
- [../backend/README.md](../backend/README.md) and [../frontend/README.md](../frontend/README.md): code layout, routes, how to run
- [../frontend/src/design/README.md](../frontend/src/design/README.md): the design system (tokens, glyphs, components, motion)
- [../frontend/TESTING.md](../frontend/TESTING.md) and [../tests/README.md](../tests/README.md): test suites
- [DATABASE_TEST_DATA_CLEANUP.md](DATABASE_TEST_DATA_CLEANUP.md): removing integration-test rows from PostgreSQL
- [VERSION_BUMP_PROCESS.md](VERSION_BUMP_PROCESS.md): bumping the version and cutting a release

## Project history and plans

- [CHANGELOG.md](CHANGELOG.md): every release
- [ROADMAP_v0.10.md](ROADMAP_v0.10.md): the plan from v0.9.2 to v0.10, decisions and progress log
- [ROADMAP_v0.9.md](ROADMAP_v0.9.md): the v0.9 plan and its decisions
- [../SHADOWREALMS_AI_COMPLETE.md](../SHADOWREALMS_AI_COMPLETE.md): the long-form project history, release by release
- [archive/](archive/): historical reports and plans up to v0.8 (PostgreSQL migration, Phase 3B spec, old planning, quality audits, the v0.6 theme). Kept for reference; they don't describe the current app.

## Elsewhere

- [Wiki](https://github.com/Somnius/shadowrealms-ai/wiki): installation, configuration, AI models, rules editions, World of Darkness books, architecture, development and CI, security, troubleshooting
- [Issues](https://github.com/Somnius/shadowrealms-ai/issues): bug reports and feature requests
- [Demo video](../demo/README.md) (from v0.7.0)

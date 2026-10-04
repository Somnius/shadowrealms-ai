# Roadmap v0.10

Started 2026-10-04 ~09:15, target: everything done before 15:00 the same day. The 0.9 work is recorded in [ROADMAP_v0.9.md](ROADMAP_v0.9.md).

How each phase runs: build in its own git worktree → two independent reviews (the second on a different model) → fixes → CI green → merge to `main` → docs, wiki and project board updated → version bump when it's worth one.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 1 | Small loose ends | test data cleanup · `OLLAMA_MODEL` default · in-app README code blocks · `env.template` legacy variables · GitHub social preview (manual, see below) | 0.9.2 | built, in review |
| 2 | Security and maintenance | Dependabot alerts and PRs · CodeQL log-injection alerts · admin screens for account unlock and login audit · 30-minute access tokens · branch protection on `main` | 0.9.3 | in progress (30-min tokens + branch protection done) |
| 3 | Playing | dice pools computed from the character sheet · chat message actions and older history · Laya labelling tool and evaluation | 0.9.4 | in progress (dice pools) |
| 4 | Bigger projects | Create React App → Vite · major dependency upgrades (react-router 7, chromadb 1.x, Node LTS, …) · React lint warnings | 0.10.0 | todo |
| — | Later | rule-book import into RAG (Classic + V5, deduplicated) · showcase video | — | postponed |

## Decisions (2026-10-04)

- Test data: the reviewer accounts and test chronicles are deleted; `claude_test` and the demo chronicles "Athens by Night" and "Constantinople Nights" stay (screenshots, video).
- Chat: everyone can copy and reply; players delete their own messages (no editing); the chronicle's Storyteller/owner and admins can delete any message; players can't delete dice or AI messages.
- Laya: an admin labelling tool plus an evaluation report, run on the small amount of chat that exists now and re-runnable once real games produce more.
- Logins: access tokens drop to 30 minutes (the browser refreshes them automatically); `main` is protected against force-push and deletion.
- GitHub social preview: no API exists, so it's a manual step: Settings → General → Social preview → upload `assets/logos/shadowrealms-banner.png`.

## Log

- 09:15 — Phase 1: test data cleanup done (6 chronicles, 4 accounts deleted through the admin API).
- 09:20 — Branch protection on `main`: force-push and deletion blocked for everyone; normal pushes unchanged.
- 09:45 — Access tokens now last 30 minutes. Checked live first: with short tokens, an expired token got a 401, the app called `/api/auth/refresh` and retried, no logout. The live `OLLAMA_MODEL` pointed at a model that isn't installed (`command-r:35b`); now `llama3.2:3b`.
- 09:50 — Phase 1 built (OLLAMA default, in-app README renderer rewritten, unused env variables removed, docs index); first review done, second review (different model) running.

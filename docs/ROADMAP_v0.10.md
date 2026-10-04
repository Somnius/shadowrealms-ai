# Roadmap v0.10

Started 2026-10-04 ~09:00, target: everything done before 15:00 the same day. The 0.9 work is recorded in [ROADMAP_v0.9.md](ROADMAP_v0.9.md).

How each phase runs: build in its own git worktree → two independent reviews (the second on a different model) → fixes → CI green → merge to `main` → docs, wiki and project board updated → version bump when it's worth one.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 1 | Small loose ends | test data cleanup · `OLLAMA_MODEL` default · in-app README code blocks · `env.template` legacy variables · GitHub social preview (manual, see below) | 0.9.2 | **done** (released 0.9.2) |
| 2 | Security and maintenance | Dependabot alerts and PRs · CodeQL log-injection alerts · admin screens for account unlock and login audit · 30-minute access tokens · branch protection on `main` | 0.9.3 | **done** (released 0.9.3) |
| 3 | Playing | dice pools computed from the character sheet · chat message actions and older history · Laya labelling tool and evaluation | 0.9.4 | dice pools + chat actions merged and live · Laya tool in review |
| 4 | Bigger projects | Create React App → Vite · major dependency upgrades (react-router 7, chromadb 1.x, Node LTS, …) · React lint warnings | 0.10.0 | in progress (CRA → Vite started) |
| — | Later | rule-book import into RAG (Classic + V5, deduplicated) · showcase video | — | postponed |

## Decisions (2026-10-04)

- Test data: the reviewer accounts and test chronicles are deleted; `claude_test` and the demo chronicles "Athens by Night" and "Constantinople Nights" stay (screenshots, video).
- Chat: everyone can copy and reply; players delete their own messages (no editing); the chronicle's Storyteller/owner and admins can delete any message; players can't delete dice or AI messages.
- Laya: an admin labelling tool plus an evaluation report, run on the small amount of chat that exists now and re-runnable once real games produce more.
- Logins: access tokens drop to 30 minutes (the browser refreshes them automatically); `main` is protected against force-push and deletion.
- GitHub social preview: no API exists, so it's a manual step: Settings → General → Social preview → upload `assets/logos/shadowrealms-banner.png`.

## Log

- before 09:12 — Phase 1: test data cleanup done (6 chronicles, 4 accounts deleted through the admin API).
- before 09:12 — Branch protection on `main`: force-push and deletion blocked for everyone; normal pushes unchanged.
- 09:21 — Access tokens now last 30 minutes. Checked live first: with short tokens, an expired token got a 401, the app called `/api/auth/refresh` and retried, no logout. The live `OLLAMA_MODEL` pointed at a model that isn't installed (`command-r:35b`); now `llama3.2:3b`.
- 09:19 — Phase 1 built (OLLAMA default, in-app README renderer rewritten, unused env variables removed, docs index); first review done, second review (different model) running.
- 09:29 — Phase 2 built (dependency fixes, log-injection escaping: CodeQL alerts 47 → 0 locally, login audit paging and filters, admin "Logins & lockouts" tab, unlock takes one exact IP). First review done, nothing blocking; second review running.
- 09:36 — Phase 1 second review: no XSS, but hostile Markdown could hang the README viewer (backtick runs, unclosed links) or overflow the stack (deep nesting), and nested markup could end up inside an attribute. All fixed with tests, CI green, merged, **0.9.2 released and live**.
- 09:44 — Phase 2 second review: no regressions; the unlock fix was real (on the old code, unlocking `*` cleared every lockout). Fixed what it found: exception messages inside tracebacks are escaped now, the last f-string log calls use the helper, each Unlock button in the audit says who it unlocks, and fast paging can't show an older page. CI green, merged, **0.9.3 released and live** (checked: paging, `*` refused, bad limit → 400). Dependabot PR #31 closed (applied), #32 (react-router 7) waits for phase 4.
- 09:46 — Phase 3: chat message actions and older history built (delete rules per role, replies, `before_id` paging); second review running together with the dice pools. Laya labelling tool being built. Phase 4 started early in its own worktree: CRA → Vite.
- 10:04 — Dice pools and chat actions: second review found no authorization holes (checked against a real Postgres). Fixed what it found: V5 Humanity rolls used Humanity − Stains, but the corebook (p. 118) only counts Health and Willpower as tracker pools, so a Humanity roll uses the rating (our own rules doc was wrong too and is corrected); roll tags stay one line even with odd sheet text; replying to a message deleted a moment earlier gives a clear error instead of a 500; players get "not found" for hidden rolls instead of a 403 that gives them away. Merged and live (checked: older history, reply quote, delete). Known gap: a message someone else deletes inside an older page you loaded stays until reload.
- 10:04 — Laya labelling tool built: first evaluation on the 8 chat messages that exist (labels provisional, made by me): in/out of character 8/8, intent 6/8. Far too few messages to mean much; it's re-runnable from the admin tab or the CLI. Second review running.

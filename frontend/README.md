# ShadowRealms AI - Frontend

React single-page app (Vite, React Router). In production nginx serves the static build from `frontend/build/`; there is a live-reload dev server for development.

(`public/README.md` is a symlink to the repository's main README, which the app shows in its README dialog. This file is the frontend's own notes.)

## Build and run

```bash
./scripts/build-frontend.sh                 # production build into frontend/build/ (nginx serves it)
docker compose --profile dev up -d frontend # dev server on 127.0.0.1:3000, see docs/DOCKER_ENV_SETUP.md
./scripts/run-frontend-tests.sh             # Jest suite, see TESTING.md
```

Inside `frontend/` (node 22): `npm start` (Vite dev server on port 3000), `npm run build`, `npm test`, `npm run lint`.

The build (`vite.config.mjs`) keeps every script in a file, without the module preload polyfill, so nginx's Content-Security-Policy can forbid inline scripts. Hashed assets go to `build/static/`. JSX in `.js` files is fine; a small plugin in the Vite config compiles it. `REACT_APP_*` variables still work (`import.meta.env` or `process.env`).

After a dependency change, rebuild the dev image before building: `docker compose --profile dev build frontend`.

## Routes

| Path | Page | Access |
|------|------|--------|
| `/login` | Sign in and register (invite code) | public |
| `/showcase` | Guided theme preview | public |
| `/showcase/design` | Design system playground | public |
| `/` | Redirects to `/chronicles` | signed in |
| `/chronicles` | Chronicle hall: your chronicles and open ones to join | signed in |
| `/chronicles/new` | Create a chronicle (game line and rules edition) | signed in |
| `/chronicles/:id` | Chronicle settings: description, members, enrollment, locations | signed in |
| `/c/:id` | Redirects to a room of the chronicle | signed in |
| `/c/:id/:locationId` | Play view: rooms, chat, dice, members | signed in |
| `/profile`, `/profile/:section` | Profile: `account`, `characters`, `downtime` | signed in |
| `/profile/characters/new` | Character forge (Classic or V5, per the chronicle) | signed in |
| `/admin/*` | Admin panel: home, invites, chronicles, users, downtime, moderation, AI | admins |

Routes are defined in `src/app/App.jsx`.

## Layout

| Path | What it is |
|------|-----------|
| `src/app/` | App shell: routes, guards, auth and session (`AuthContext.jsx`, `http.js`), user menu, chronicle rail |
| `src/features/` | One folder per area: `auth`, `hall`, `chronicle`, `play`, `chat`, `dice`, `profile` |
| `src/design/` | Design system: tokens, components, glyphs, motion, atmosphere ([README](src/design/README.md)) |
| `src/pages/` | Admin panel (`AdminPage.js`, `admin/`) and the theme preview (`showcase/`) |
| `src/components/` | Older shared components still in use: character creation wizards and sheet views, dice faces and overlay, README dialog, footer |
| `src/characterSheet/`, `src/rules/` | Character creation rules for Classic and V5; `rules/*.json` are copies of `docs/rules/*.json` |
| `src/dice/` | Dice result display helpers |
| `src/i18n/` | Translations (`locales/en`, `locales/el`) and the `t()` helper |
| `src/utils/` | Older API helpers, sanitising, time formatting |
| `scripts/i18n-extract.js` | Syncs `locales/en` with the English defaults in `t()` calls and lists missing Greek keys (`node scripts/i18n-extract.js [--write]`) |

## Conventions

- All UI text goes through `t('ns:key', 'English default')` and needs a Greek translation; the locale tests fail otherwise.
- Talk to the API through `src/app/http.js` (it handles token refresh, logout on a dead session, and rate-limit messages).
- Reuse the design system components instead of styling one-off elements.

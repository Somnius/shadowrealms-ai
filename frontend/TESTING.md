# Frontend Testing

The frontend tests use Jest and React Testing Library. There are 418 tests in 40 files, and all of them run in CI.

## Running the tests

From the repository root, in a one-off container of the dev frontend service (the same command CI runs):

```bash
./scripts/run-frontend-tests.sh                   # whole suite
./scripts/run-frontend-tests.sh src/features/chat # only paths matching a pattern
./scripts/run-frontend-tests.sh --coverage        # coverage report in frontend/coverage/
```

Extra arguments go to Jest. `JEST_WORKERS` (default 4) caps the parallel workers.

Inside `frontend/`: `npm test` (add `-- --watch` to watch), `npm run test:ci` (with coverage).

CI (`.github/workflows/ci.yml`, job "Frontend tests + build") runs `npm ci`, then `npx jest --ci`, `npm run lint` and `npm run build`.

## Configuration

- All Jest settings are in `jest.config.js`: jsdom, Babel (`@babel/preset-env`, `@babel/preset-react`) for the code and the d3 packages, CSS and file stubs, `resetMocks`. Vite isn't involved in the tests.
- `jest/polyfills.js` adds a `fetch` stub (jsdom has none) so tests can mock it.
- `src/setupTests.js` runs before every test file (jest-dom matchers, and `matchMedia` / `crypto` stubs that jsdom lacks).

## What is tested

| Area | Files | Covers |
|------|-------|--------|
| App shell and session | `src/app/__tests__/` (`guards`, `http`, `session`) | Route guards, the JSON client, token refresh on 401, logout, 429/503 handling |
| Chat | `src/features/chat/__tests__/` | Message grouping, markdown rendering (no HTML), the composer and "Speaking as", the send flow, slash commands, live updates, room message loading |
| Dice | `src/dice/*.test.js`, `src/features/dice/__tests__/`, `src/components/dice/__tests__/` | Classic and V5 result display, roll history rows, server-posted dice integrity, the roll overlay |
| Character sheets | `src/characterSheet/*.test.js`, `src/characterSheet/v5/validation.test.js`, `src/rules/rulesEdition.test.js` | Classic creation budgets and freebies, merits and flaws, V5 creation rules, `v5.json` matching `docs/rules/v5.json`, the rules edition |
| Translations | `src/i18n/__tests__/` | Every English key exists in Greek and the other way round (same plurals and placeholders), every `t('ns:key')` in the code exists, language switching |
| Design system | `src/design/__tests__/` | Buttons, modals, tabs and forms, dot tracks, glyphs, dice, motion and toasts, the atmosphere layer |
| Theme preview | `src/pages/showcase/__tests__/` | The `/showcase` page, its dice demo, its translations |
| Components | `src/components/__tests__/`, `src/pages/__tests__/` | README dialog, glyph replacements, creation wizard translations, admin page tabs |
| Utilities and flows | `src/utils/__tests__/security.test.js`, `src/__tests__/integration/userFlow.test.js` | Sanitising and validation helpers; the main user flows through the app shell with `fetch` mocked per route |

## Writing tests

- Put a `*.test.js(x)` file next to the code, or in a `__tests__/` folder beside it.
- Test behaviour through the rendered output (Testing Library queries), not implementation details.
- UI text must exist in both locales; the translation tests fail otherwise.
- Keep tests independent of the backend: mock `fetch` or the API helpers.

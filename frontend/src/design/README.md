# ShadowRealms design system (`src/design`)

Tokens, glyphs, components, motion and atmosphere for the whole app (built in v0.9). The app
shell wraps everything in `<DesignProvider>` (`src/app/App.jsx`).

```jsx
import { DesignProvider, ToastProvider, Button, Glyph, Modal } from './design';

<DesignProvider line="vampire" lang={i18n.language}>
  <ToastProvider>
    <App />
  </ToastProvider>
</DesignProvider>
```

- Importing `./design` loads `tokens.css`. Custom properties go on `:root` and are all named `--sr-*`, so on their own they change nothing. Every element style is scoped under `.sr-app`, so anything rendered outside it keeps its own look.
- `DesignProvider` renders `<div class="sr-app" data-motion data-line lang>` and a Motion `MotionConfig`.
- Modals, drawers and toasts render through `Portal` into their own `.sr-app.sr-portal` node on `<body>`, so they get the tokens too.

## Fonts

All fonts are SIL OFL 1.1. They are loaded from Google Fonts by `public/index.html` (preconnect plus one stylesheet link for Cinzel, Alegreya, EB Garamond, Inter and JetBrains Mono). nginx's Content-Security-Policy allows `fonts.googleapis.com` and `fonts.gstatic.com` for that.

| Token | Font | Greek |
|---|---|---|
| `--sr-font-display` | Cinzel; under `:lang(el)` → Alegreya | Cinzel has none, hence the swap. Not Alegreya SC: its small caps keep the tonos, which Greek capitals must not carry |
| `--sr-font-body` | EB Garamond (prose, chat, textarea) | yes |
| `--sr-font-ui` | Inter (buttons, labels, inputs) | yes |
| `--sr-font-mono` | JetBrains Mono (dice, keys) | yes |

Greek notes:
- `text-transform: uppercase` (`.sr-caps`) only drops the tonos when the element's language is Greek. Set `lang="el"` on `<html>`, or pass `lang` to `DesignProvider`.
- Display tracking is capped at `.06em`.
- `.sr-smallcaps` turns into normal text under `:lang(el)`.
- Labels are allowed to wrap; nothing has a fixed width.

## Tokens

| Group | Tokens |
|---|---|
| Night surfaces | `--sr-night-950/900/850/800/750/700/600/500` (page `#0f0f1e`, panels `#16213e`, borders `#2a2a4e`) |
| Bone text | `--sr-bone-100` primary 12–14:1, `-300` secondary ≥ 7.4:1, `-500` muted ≥ 4.5:1 on every surface |
| Blood | `-300 #fda4af`, `-400 #ff6b81` (rose text, ≥ 5.5:1), `-500 #e94560` (brand, borders, focus ring, large text), `-600 #c2334d` (fill under white text, 5.42:1), `-700 #8b0000`, `-800`, `-900` |
| Arcane / gold / ember | `--sr-arcane-300/400/500/700/950`, `--sr-gold-300/400/500`, `--sr-ember-500`, `--sr-amber-600` |
| Status | `--sr-ok-400`, `--sr-warn-400`, `--sr-danger-400`, `--sr-info-400` |
| Semantic | `--sr-bg`, `--sr-surface(-sunken/-hover)`, `--sr-border(-strong)`, `--sr-border-input` (#707096, ≥ 3.18:1, WCAG 1.4.11), `--sr-text(-2/-muted)`, `--sr-accent(-text/-fill/-fill-hover)`, `--sr-on-accent`, `--sr-focus`, `--sr-glyph-accent` |
| Game line | `data-line="werewolf"` (amber) and `"mage"` (arcane) override the accent group |
| Type | `--sr-text-xs…3xl` = 12 / 13 / 14 / 16 / 17 (chat) / 20 / 24 / 30 / 38 px; leading `tight/ui/body`; `--sr-tracking-display` |
| Space | `--sr-space-1…10` = 4 8 12 16 20 24 32 40 48 64 |
| Radius | `--sr-radius-sm 4`, `md 8`, `lg 12`, `full` |
| Elevation | `--sr-shadow-1/2/3`, `--sr-glow-blood/arcane/ember/gold` |
| Z-index | rail 10, drawer 40, popover 50, modal 60, toast 70, dice 80 |
| Motion | `--sr-dur-instant 80`, `fast 150`, `base 240`, `slow 400`, `ritual 1200` ms; `--sr-ease-out`, `-in-out`, `-drip` |
| Touch | `--sr-tap: 44px` (applied on `pointer: coarse`) |

All contrast figures were computed with the WCAG formula against `#0f0f1e`, `#0f1729`, `#16213e` and `#1a2547`. Text must be white (not bone) on accent fills: bone on `#c2334d` is only 4.11:1.

## Motion and reduced motion

- **Atmosphere** (the user menu's setting, phase 4): `'full' | 'subtle' | 'off'`, stored in `localStorage.sr_atmosphere` and written to `data-atmosphere` on `.sr-app` (and on portals). `full` = everything; `subtle` = ambient loops (fog drift, candle glow, grain, glyph loops not marked `.sr-glyph--essential`) hold still, short transitions and one-shot effects still play; `off` = reduced motion (`data-motion=reduced`). The OS `prefers-reduced-motion` forces `off`. `useAtmosphere()` → `{ level, choice, setLevel, systemReduced }`. An older `sr_motion=reduced` reads as `off`.
- Preference: `'system' | 'reduced' | 'full'`. The OS `prefers-reduced-motion` always wins. The manual toggle (`<MotionToggle/>`, or `useMotionPreference().setPreference`) can only add a reduction on top of it, and the choice is stored in `localStorage.sr_motion` on a best-effort basis.
- CSS: `.sr-app[data-motion=reduced]` and `@media (prefers-reduced-motion)` cut animations and transitions to 0.01 ms. Glyph loops are set to `animation: none`. JS: `MotionConfig reducedMotion="always"`, and the components also skip their framer transitions.
- Ambient effects (`FogLayer`, `CandleGlow`) pause through `data-paused` when the tab is hidden (`visibilitychange`) or the element is off-screen (`IntersectionObserver`). Only `transform` and `opacity` are animated. Never put fog behind chat text.
- Motion (`motion/react`, formerly framer-motion) is used through `LazyMotion` + `m` + `domAnimation`, so the full `motion` bundle isn't pulled in.

## Glyphs (97, original, hand-authored)

`<Glyph name="candle" size={24} title="…" animate draw />`

- Each glyph sits on a 24 px grid with a 1.75 stroke, round caps and `currentColor`. Accent fills use `--sr-glyph-accent`.
- A glyph is decorative by default (`aria-hidden`). Passing `title` makes it `role="img"` with that accessible name.
- Animated presets: `AnimatedCandle` (flicker), `BlinkingEye`, `AiSigil` (rune ring turns, eye blinks), `DrippingBlood`, and `SigilDraw` (stroke draw-on through `pathLength=1` + `stroke-dashoffset`, works for any glyph).
- `DieFace`: a d10 with its value. Variants: normal / hunger (blood body plus a fang notch), and states success / fail / crit / one. It gets an accessible name such as "Hunger die: 10, critical".
- `sigilFor('clan', 'Banu Haqim')` returns `'clan-banu-haqim'`.

| Group | Names |
|---|---|
| dice | d10, d10-crit, d10-hunger, d10-botch, dice (two d10s) |
| horror | blood-drop, fangs, eye, eye-shut, skull, candle, raven, bat, chalice, vitae-sigil, dagger, cross, thorned-rose, coffin, key, lock-chain, chain, scroll, book, mask, hood, crown, crown-thorns, web, hourglass, quill, ai-sigil, logo-mark |
| moon | moon-new, moon-crescent, moon-half, moon-gibbous, moon-full |
| room | room-ooc, room-elysium, room-haven, room-street |
| ui | menu, close, send, settings, user, users, logout, globe, bell, search, chevron-down/up/left/right, check, plus, reroll, minus, trash, warning, info, ornament |
| line | line-vampire, line-werewolf, line-mage, line-wraith, line-changeling |
| clan | clan-banu-haqim, -brujah, -gangrel, -hecata, -lasombra, -malkavian, -ministry, -nosferatu, -toreador, -tremere, -tzimisce, -ventrue, -ravnos, -salubri, -caitiff, -thin-blood |
| discipline | disc-animalism, -auspex, -blood-sorcery, -celerity, -dominate, -fortitude, -obfuscate, -oblivion, -potence, -presence, -protean, -thin-blood-alchemy |

**Originality rule.** Clan and discipline sigils are abstract, and none of them redraws an official White Wolf / Paradox logo. There is no rose (Toreador is a frame and a brushstroke), no dragon (Tzimisce is a ribcage), no rune (Tremere is a retort), no eye for Salubri (an open palm), no crown for Ventrue (a signet ring), and no circle-A for Brujah (a fractured ring). A human reviewer should still put each one side by side with the official marks; that check hasn't been done yet (it's on the roadmap).

## Components

| Component | Notes |
|---|---|
| `Button` | Variants `primary` / `secondary` / `ghost` / `danger` / `arcane` / `icon`; sizes `sm 32`, `md 40`, `lg 48` (44 on touch); `icon` / `iconEnd` take a glyph name. `loading` sets `aria-busy` + `aria-disabled`, blocks click and submit, and keeps focus. |
| `IconButton` | `label` is required: it's used as the `aria-label` and as the tooltip. |
| `Card` / `Panel` | `Card ornate` adds original corner filigree; `glow`. `Panel` is a `<section aria-labelledby>` with a header and `actions`. |
| `Modal` | `role=dialog aria-modal`, labelled by its title and described by its description. Focus moves inside, Tab/Shift+Tab are trapped, Esc closes, focus returns to the opener, body scroll is locked, the backdrop click can be turned off. Sizes `sm`, `md`, `lg`, and `sheet` (a bottom sheet under 768 px). Stacked dialogs: only the top one reacts. |
| `Drawer` | Left / right / bottom, with the same dialog behaviour. Width `min(85vw, 360px)`. |
| `Tabs` | WAI-ARIA tabs with roving tabindex and arrow keys / Home / End. Disabled tabs are skipped. |
| `Tooltip` | Opens after a 400 ms hover delay, or straight away on focus. Esc hides it. `aria-describedby` is set unless `describe={false}`. Hidden on touch devices. |
| `ToastProvider` / `useToast()` | `toast({ title, body, tone, duration })`. Errors use `role=alert`, others `role=status`. Timers pause on hover and focus. Shown at the top on phones. |
| `Badge` | Tones neutral / blood / arcane / gold / ok / warn / danger; `count` (shows 99+ above 99); `edition="V5"` for the engraved edition badge. |
| `Avatar` | Shows the image. With no image, or when it fails to load, it shows initials on an original sigil. `presence` uses a moon-phase dot. |
| `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Switch` | Each has a label, hint and error wired through `aria-describedby` / `aria-invalid`. Inputs use 16 px text so iOS doesn't zoom. Select is the native element, styled. |
| `DotTrack` | `role=slider`: arrows / Home / End / digits; clicking the top dot clears it. `locked` sets a floor. `readOnly` makes it `role=img` ("Strength: 3 of 5"). `shape="square"`, `tone`. `valueText` is for i18n. |
| `Divider` | Ornament glyph, or `label` text. |
| `Spinner` | `drop` / `candle` / `ring`, with `role=status` and a label. |
| `EmptyState`, `Kbd` | |

## Atmosphere

- `FogLayer` and `CandleGlow`: CSS only. They use no image assets, are aria-hidden, and pause or go static as described under motion.
- `BloodDrip`: a one-shot drip for a botch or a bestial failure. `playKey` replays it and `onDone` fires when it ends. Under reduced motion it shows the final drips with no movement.
- `SigilReveal`: the original ShadowRealms sigil. The thorned ring is built with `d3-shape` (`lineRadial`), each stroke is drawn in with Motion `pathLength`, then the drop fills. It plays once it's in view.
- `DiceRollViz`: a d10 pool visualisation. Takes either the API `roll_result` (`result={…}`, V5 or classic) or raw dice (`edition`, `normal`, `hunger`, `dice`, `difficulty`, `rerolls`, `willpower`). `d3-scale` handles the layout (`scaleBand`) and the success meter (`scaleLinear`), `d3-shape` draws the crit-pair arcs, React renders the SVG, and Motion staggers the tumble. It's a `<figure>` whose caption states the result in words and lists every die. Server flags win over local maths. `diceAnalysis.js` mirrors `backend/services/v5_dice.py resolve_v5` and `docs/dice-old-wod.md`.

## Integration layer (phase 4, `atmosphere/Ambience.jsx`)

| Piece | Where it's used | Static fallback |
|---|---|---|
| `Vignette`, `Grain` | login set piece | grain holds still (subtle / off) |
| `CandleHalo` | Storyteller avatar while the AI writes | steady glow |
| `CrackOverlay`, `RollFx`, `rollMood()` | dice overlay + fresh dice cards: blood drips + crack (botch, bestial failure), gold-to-blood sweep (messy critical), gold flare (critical / exceptional) | end state drawn, no movement; history cards keep only a few dried drips |
| `ChronicleSigil` | hall cards and the "open chronicles" list: the line's glyph in an edition ring (V5 thorns, classic engraved double ring), drawn on once in view; on hover / focus of `.sr-sigil-host` the ring turns and the line motif plays | complete ring, no motifs |
| `RouteTransition` | shell outlet: 180 ms fade + 6 px rise per page type (never per room) | none (same element, so switching the atmosphere never remounts the page) |
| `EmptyState ambient`, `TopBar ambient` | faint fog in empty states and the play header (never behind chat text) | still fog |

## Playground

`DesignPlayground.jsx` is a living style guide covering all glyphs, components, the motion toggle, game-line switching, EN/EL text and dice outcomes. It is mounted at **`/showcase/design`**. The guided theme preview at **`/showcase`** (`src/pages/showcase/`) walks through the same pieces for visitors. Both routes are public.

## Tests

`src/design/__tests__/` covers glyph rendering and naming, Button, Modal and Drawer focus and Esc, DotTrack keyboard, Tabs, the form controls, motion preference, toasts and dice analysis. `testing/setupUser.js` returns a user-event 14 instance (React Testing Library 16 wraps its events in `act` itself).

## Third-party code

| Package | Licence | Use |
|---|---|---|
| `d3-shape` 3.2 (+ `d3-path`) | ISC, © Mike Bostock | sigil ring, dice crit arcs |
| `d3-scale` 4.0 (+ `d3-array`, `d3-format`, `d3-interpolate`, `d3-color`, `d3-time`, `d3-time-format`, `internmap`) | ISC, © Mike Bostock | dice layout and meter |
| `motion` 14 (formerly `framer-motion`) | MIT | overlays, reveals |
| Cinzel, Alegreya, EB Garamond, Inter, JetBrains Mono | SIL OFL 1.1 | fonts, loaded from Google Fonts |

All glyph and sigil artwork in this folder is original and falls under the repository's licence. No icon set was copied.

The d3 v7 packages are ESM-only, so `package.json` has `jest.transformIgnorePatterns` to let Jest transform `d3-*` and `internmap`.

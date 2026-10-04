#!/usr/bin/env node
// ShadowRealms AI trailer: caption overlays, intro title and outro card.
//
// Renders HTML in headless Chromium over the DevTools protocol (no npm deps: Node's
// built-in WebSocket) with a transparent background, at 1920x1080:
//   data/trailer/cards/{lang}/cap_NN.png      one transparent PNG per caption (edit.py fades it)
//   data/trailer/cards/{lang}/intro.mov       8 s alpha animation (sigil draws, title), PNG-in-MOV
//   data/trailer/cards/{lang}/intro_rec.mov, outro_rec.mov  variants laid over the login page recording
//     (clips/{lang}/sigil_clean.mp4): no sigil of ours, the app's wordmark is the title
//   data/trailer/cards/{lang}/outro.mov       8 s alpha animation (sigil, Enter the night, lines)
//   data/trailer/cards/{lang}/{title,outro}.png  stills of the finished cards, for review
// Text comes from tools/trailer/timeline.json. Greek never uses Cinzel (CUES.md font rule).
// Outputs are cached by a hash of their HTML; --force re-renders.
//
// Usage: node tools/trailer/cards.mjs [--lang en,el] [--only captions,intro,outro] [--force] [--recorded]

import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
const DATA = path.join(ROOT, 'data/trailer');
const FONTS = path.join(DATA, 'fonts');
const TL = JSON.parse(fs.readFileSync(path.join(HERE, 'timeline.json'), 'utf8'));
const W = TL.width, H = TL.height, FPS = TL.fps;

const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : dflt;
};
const LANGS = opt('lang', 'en,el').split(',');
const ONLY = opt('only', 'captions,intro,outro').split(',');
const FORCE = args.includes('--force');
const REC_ALWAYS = args.includes('--recorded');

// ---------------------------------------------------------------- sigil (from the repo asset)
const sigilSvg = fs.readFileSync(path.join(ROOT, 'assets/logos/shadowrealms-sigil.svg'), 'utf8');
const sigilD = [...sigilSvg.matchAll(/<path d="([^"]+)"/g)].map((m) => m[1]);
if (sigilD.length !== 6) throw new Error(`expected 6 paths in the sigil SVG, got ${sigilD.length}`);
const [THORNS, RING, RUNES, TRI, MOON, DROP] = sigilD;

// ---------------------------------------------------------------- shared CSS
const fontUrl = (f) => pathToFileURL(path.join(FONTS, f)).href;
const BASE_CSS = `
@font-face { font-family: 'Cinzel'; src: url('${fontUrl('Cinzel.ttf')}') format('truetype'); font-weight: 400 900; }
@font-face { font-family: 'Alegreya'; src: url('${fontUrl('Alegreya.ttf')}') format('truetype'); font-weight: 400 900; }
@font-face { font-family: 'Alegreya'; font-style: italic; src: url('${fontUrl('Alegreya-Italic.ttf')}') format('truetype'); font-weight: 400 900; }
@font-face { font-family: 'EB Garamond'; src: url('${fontUrl('EBGaramond.ttf')}') format('truetype'); font-weight: 400 800; }
@font-face { font-family: 'EB Garamond'; font-style: italic; src: url('${fontUrl('EBGaramond-Italic.ttf')}') format('truetype'); font-weight: 400 800; }
:root {
  --night-950: #07070f; --night-900: #0f0f1e;
  --bone-50: #f5f2ea; --bone-100: #e0e0e0; --bone-300: #b5b5c3;
  --blood-400: #ff6b81; --blood-500: #e94560; --blood-600: #c2334d; --blood-700: #8b0000;
}
html, body { margin: 0; padding: 0; width: ${W}px; height: ${H}px; background: transparent; overflow: hidden; }
body { position: relative; -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
       font-kerning: normal; font-variant-ligatures: common-ligatures; }
.display-en { font-family: 'Cinzel', serif; }
.display-el { font-family: 'Alegreya', serif; }          /* Greek titles: never Cinzel */
.body { font-family: 'EB Garamond', serif; }
.glow { text-shadow: 0 2px 3px rgba(0,0,0,.95), 0 0 2px rgba(0,0,0,.8), 0 0 22px rgba(233,69,96,.38), 0 0 60px rgba(139,0,0,.35); }
.sigil path { fill: none; stroke: #e94560; stroke-linecap: round; stroke-linejoin: round; }
.sigil .thorns { stroke-width: 1.6; } .sigil .ring { stroke-width: 1; }
.sigil .runes { stroke-width: 1.4; } .sigil .tri { stroke-width: 1.8; }
.sigil .moon { stroke: #b5b5c3; stroke-width: 1.2; }
.sigil .drop { fill: #c2334d; stroke: #ff6b81; stroke-width: .8; transform-box: fill-box; transform-origin: 50% 60%; }
`;

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// Greek text is set in its own faces; Latin brand words inside Greek lines stay in the same face.
const displayClass = (lang) => (lang === 'el' ? 'display-el' : 'display-en');

const sigilMarkup = (size, id = 'sig') => `
<svg class="sigil" id="${id}" viewBox="0 0 100 100" width="${size}" height="${size}" style="overflow:visible">
  <g transform="translate(50 50)">
    <path class="thorns s" d="${THORNS}"/><path class="ring s" d="${RING}" style="opacity:.7"/>
    <path class="runes s" d="${RUNES}" style="opacity:.8"/><path class="tri s" d="${TRI}"/>
    <path class="moon s" d="${MOON}"/><path class="drop" d="${DROP}"/>
  </g>
</svg>`;

// Same choreography as frontend SigilReveal (stroke i starts at i*step*0.8, draws for
// step*1.6, eased; then the drop scales in), stretched to the given window.
const SIGIL_JS = `
const ease = (x) => { x = Math.min(1, Math.max(0, x)); // cubic-bezier(.65,0,.35,1) ~ easeInOutCubic
  return x < .5 ? 4*x*x*x : 1 - Math.pow(-2*x + 2, 3) / 2; };
const easeOut = (x) => { x = Math.min(1, Math.max(0, x)); return 1 - Math.pow(1 - x, 3); };
function sigilAt(svg, t, t0, t1) {
  const strokes = svg.querySelectorAll('path.s');
  const total = t1 - t0, dur = total - .5, step = dur / strokes.length;
  strokes.forEach((p, i) => {
    const L = p.__len || (p.__len = p.getTotalLength() + 1);
    const k = ease((t - t0 - i * step * .8) / (step * 1.6));
    p.style.strokeDasharray = L + ' ' + L;
    p.style.strokeDashoffset = String(L * (1 - k));
    p.style.visibility = k <= 0 ? 'hidden' : 'visible';
  });
  const drop = svg.querySelector('path.drop');
  const d = easeOut((t - t0 - dur) / .5);
  drop.style.opacity = d; drop.style.transform = 'scale(' + (.4 + .6 * d) + ')';
  return d;
}
const clamp01 = (x) => Math.min(1, Math.max(0, x));
`;

// ---------------------------------------------------------------- card HTML
function captionHtml(cap, lang) {
  const text = cap[lang];
  const cls = displayClass(lang);
  const size = lang === 'el' ? 56 : 52;
  const color = cap.accent ? 'var(--blood-500)' : 'var(--bone-50)';
  const top = cap.pos === 'top';   // chat shots: the newest messages live at the bottom
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><style>${BASE_CSS}
.band { position:absolute; left:0; right:0; ${top ? 'top' : 'bottom'}:0; height:400px;
  background: linear-gradient(to ${top ? 'top' : 'bottom'}, rgba(7,7,15,0) 0%, rgba(7,7,15,.55) 40%, rgba(7,7,15,.84) 75%, rgba(7,7,15,.90) 100%); }
.cap { position:absolute; left:${Math.round(W * 0.08)}px; right:${Math.round(W * 0.08)}px; ${top ? 'top' : 'bottom'}:${Math.round(H * (top ? 0.085 : 0.105))}px;
  display:flex; flex-direction:column; align-items:center; gap:22px; text-align:center; }
.orn { display:flex; align-items:center; gap:14px; }
.orn i { display:block; width:150px; height:2px; }
.orn i.l { background: linear-gradient(to right, rgba(233,69,96,0), rgba(233,69,96,.95)); }
.orn i.r { background: linear-gradient(to left, rgba(233,69,96,0), rgba(233,69,96,.95)); }
.orn b { display:block; width:9px; height:9px; transform: rotate(45deg); background: var(--blood-500);
  box-shadow: 0 0 10px rgba(233,69,96,.9); }
.txt { position:relative; }
.txt::before { content:''; position:absolute; z-index:-1; left:-90px; right:-90px; top:-34px; bottom:-34px;
  background: radial-gradient(closest-side, rgba(7,7,15,.78), rgba(7,7,15,.55) 60%, rgba(7,7,15,0)); }
.cap { isolation:isolate; }
.txt { font-size:${size}px; line-height:1.22; color:${color}; letter-spacing:${lang === 'el' ? '.012em' : '.05em'};
  font-weight:${lang === 'el' ? 500 : 600}; text-wrap: balance; max-width:${Math.round(W * 0.84)}px; }
</style></head><body>
<div class="band"></div>
<div class="cap">${top ? '' : '<div class="orn"><i class="l"></i><b></b><i class="r"></i></div>'}
<div class="txt ${cls} glow">${esc(text)}</div>${top ? '<div class="orn"><i class="l"></i><b></b><i class="r"></i></div>' : ''}</div>
</body></html>`;
}

function introHtml(lang, mode) {
  // 'own': our sigil draws + big title. 'recorded': over the login page recording, whose own
  // sigil and wordmark are the title, so only the subtitle (and a rule) is added under them.
  const I = TL.intro;
  const sub = I.subtitle[lang];
  const withSigil = mode === 'own';
  const subTop = withSigil ? 815 : I.recorded_subtitle_top;
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><style>${BASE_CSS}
.stage { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; }
#sigwrap { position:absolute; left:50%; top:${withSigil ? 395 : 380}px; transform: translate(-50%,-50%); }
.title { position:absolute; left:0; right:0; top:${withSigil ? 655 : 470}px; text-align:center;
  font-family:'Cinzel', serif; font-weight:700; font-size:118px; color:var(--bone-50); white-space:nowrap; }
.sub { position:absolute; left:0; right:0; top:${subTop}px; text-align:center;
  font-family:'EB Garamond', serif; font-style:italic; font-size:44px; color:var(--bone-300); letter-spacing:.02em; }
.rule { position:absolute; left:50%; top:${subTop - 15}px; height:1px; width:520px; transform: translateX(-50%) scaleX(0);
  background: linear-gradient(to right, rgba(233,69,96,0), rgba(233,69,96,.9), rgba(233,69,96,0)); }
</style></head><body>
${withSigil ? `<div id="sigwrap">${sigilMarkup(380)}</div>` : ''}
${withSigil ? `<div class="title glow" id="title">${esc(I.title)}</div>` : ''}
<div class="rule" id="rule"></div>
<div class="sub glow" id="sub" lang="${lang}">${esc(sub)}</div>
<script>${SIGIL_JS}
const svg = document.getElementById('sig');
window.render = (t) => {
  if (svg) {
    const d = sigilAt(svg, t, ${I.sigil_draw[0]}, ${I.sigil_draw[1]});
    // glow: builds while drawing, a flare when the drop lands and on the bell at 6.0
    const flare = Math.exp(-Math.pow((t - ${I.sigil_draw[1]}) / .35, 2)) + .7 * Math.exp(-Math.pow((t - 6.0) / .45, 2));
    const g = 4 + 8 * clamp01((t - ${I.sigil_draw[0]}) / 3) + 18 * flare + 2 * Math.sin(t * 2.2);
    svg.style.filter = 'drop-shadow(0 0 ' + (g * .35).toFixed(2) + 'px rgba(255,107,129,.85)) drop-shadow(0 0 ' + g.toFixed(2) + 'px rgba(233,69,96,.55))';
  }
  const ti = clamp01((t - ${I.title_in}) / 1.6), te = easeOut(ti);
  const title = document.getElementById('title');
  if (title) {
    title.style.opacity = te;
    title.style.letterSpacing = (0.34 - 0.22 * te).toFixed(4) + 'em';
    title.style.filter = 'blur(' + (6 * (1 - te)).toFixed(2) + 'px)';
  }
  const si = easeOut((t - ${I.subtitle_in}) / 1.2);
  const sub = document.getElementById('sub');
  sub.style.opacity = si; sub.style.transform = 'translateY(' + (14 * (1 - si)).toFixed(2) + 'px)';
  const ruleT = ${withSigil ? '${I.title_in} + .3' : '${I.subtitle_in} - .4'};
  document.getElementById('rule').style.transform = 'translateX(-50%) scaleX(' + easeOut((t - ruleT) / 1.4).toFixed(4) + ')';
};
</script></body></html>`;
}

function outroHtml(lang, mode = 'own') {
  const withSigil = mode === 'own';
  const dy = withSigil ? 0 : TL.outro.recorded_top - 440;   // the recording's sigil + wordmark sit above
  const O = TL.outro;
  const head = O.headline[lang];
  const headStyle = lang === 'el'
    ? "font-family:'Alegreya', serif; font-weight:500; font-size:104px; letter-spacing:.01em;"
    : "font-family:'Cinzel', serif; font-weight:700; font-size:100px; letter-spacing:.08em;";
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><style>${BASE_CSS}
#sigwrap { position:absolute; left:50%; top:280px; transform: translate(-50%,-50%); }
.head { position:absolute; left:0; right:0; top:${440 + dy}px; text-align:center; color:var(--bone-50); white-space:nowrap; ${headStyle} }
.line { position:absolute; left:0; right:0; top:${592 + dy}px; text-align:center; font-family:'EB Garamond', serif; font-style:italic;
  font-size:44px; color:var(--bone-100); }
.rule { position:absolute; left:50%; top:${690 + dy}px; width:560px; height:1px; transform: translateX(-50%) scaleX(0);
  background: linear-gradient(to right, rgba(233,69,96,0), rgba(233,69,96,.9), rgba(233,69,96,0)); }
.tags { position:absolute; left:0; right:0; top:${728 + dy}px; text-align:center; font-family:'Cinzel', serif; font-weight:600;
  font-size:31px; letter-spacing:.22em; color:var(--bone-300); }
.url { position:absolute; left:0; right:0; top:${800 + dy}px; text-align:center; font-family:'EB Garamond', serif; font-weight:500;
  font-size:42px; letter-spacing:.03em; color:var(--blood-400); }
</style></head><body>
${withSigil ? `<div id="sigwrap">${sigilMarkup(250)}</div>` : ''}
<div class="head glow" id="head" lang="${lang}">${esc(head)}</div>
<div class="line glow" id="line" lang="${lang}">${esc(O.line[lang])}</div>
<div class="rule" id="rule"></div>
<div class="tags glow" id="tags" lang="en">${esc(O.tags)}</div>
<div class="url glow" id="url" lang="en">${esc(O.url)}</div>
<script>${SIGIL_JS}
const svg = document.getElementById('sig');
const fadeUp = (id, t0, dur, dy) => { const k = easeOut((window.__t - t0) / dur); const el = document.getElementById(id);
  el.style.opacity = k; el.style.transform = 'translateY(' + (dy * (1 - k)).toFixed(2) + 'px)'; return k; };
window.render = (t) => {
  window.__t = t;
  if (svg) {
  sigilAt(svg, t, 0.05, 1.5);
  const flare = Math.exp(-Math.pow((t - 1.0) / .4, 2));          // the last bell at 113.0
  const g = 6 + 3 * Math.sin(t * 1.6) + 16 * flare;
  svg.style.filter = 'drop-shadow(0 0 ' + (g * .35).toFixed(2) + 'px rgba(255,107,129,.85)) drop-shadow(0 0 ' + g.toFixed(2) + 'px rgba(233,69,96,.55))';
  }
  const k = fadeUp('head', ${O.headline_in}, 1.4, 0);
  const head = document.getElementById('head');
  head.style.filter = 'blur(' + (5 * (1 - k)).toFixed(2) + 'px)';
  ${lang === 'el' ? '' : "head.style.letterSpacing = (0.16 - 0.08 * k).toFixed(4) + 'em';"}
  fadeUp('line', ${O.line_in}, 1.1, 12);
  document.getElementById('rule').style.transform = 'translateX(-50%) scaleX(' + easeOut((t - ${O.tags_in} + .3) / 1.2).toFixed(4) + ')';
  fadeUp('tags', ${O.tags_in}, 1.0, 10);
  fadeUp('url', ${O.url_in}, 1.0, 10);
};
</script></body></html>`;
}

// ---------------------------------------------------------------- tiny CDP client
async function launchBrowser() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'sr-cards-'));
  const proc = spawn('nice', ['-n', '10', 'chromium', '--headless=new', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
    '--force-device-scale-factor=1', `--window-size=${W},${H}`, '--font-render-hinting=none',
    '--disable-lcd-text', '--mute-audio', '--allow-file-access-from-files', 'about:blank'],
  { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let buf = '';
    const t = setTimeout(() => reject(new Error('chromium did not start')), 20000);
    proc.stderr.on('data', (d) => {
      buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(t); resolve(m[1]); }
    });
    proc.on('exit', (c) => reject(new Error(`chromium exited ${c}: ${buf.slice(-500)}`)));
  });
  const ws = new WebSocket(wsUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0; const pending = new Map(); const listeners = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id); pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    } else if (msg.method) listeners.forEach((l) => l(msg));
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const mid = ++id; pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const s = (m, p) => send(m, p, sessionId);
  await s('Page.enable');
  await s('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await s('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  const page = {
    async load(file) {
      const loaded = new Promise((r) => { const l = (m) => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(l), 1); r(); } }; listeners.push(l); });
      await s('Page.navigate', { url: pathToFileURL(file).href });
      await loaded;
      // Load every declared face, then wait for layout with them; fail loudly if one is missing.
      const res = await s('Runtime.evaluate', { awaitPromise: true, returnByValue: true, expression: `(async () => {
        await Promise.all([...document.fonts].map((f) => f.load().catch(() => null)));
        await document.fonts.ready;
        await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
        return [...document.fonts].map((f) => f.family + ' ' + f.style + ':' + f.status);
      })()` });
      const bad = res.result.value.filter((x) => !x.endsWith(':loaded'));
      if (bad.length) throw new Error(`fonts not loaded: ${bad.join(', ')}`);
    },
    async eval(expr) { return s('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); },
    async shot() {
      const { data } = await s('Page.captureScreenshot', { format: 'png', fromSurface: true, optimizeForSpeed: true });
      return Buffer.from(data, 'base64');
    },
  };
  const close = async () => {
    const exited = new Promise((r) => (proc.exitCode !== null ? r() : proc.once('exit', r)));
    try { await send('Browser.close'); } catch { /* gone */ }
    ws.close();
    await Promise.race([exited, new Promise((r) => setTimeout(r, 3000))]);
    proc.kill();
    try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* best effort */ }
  };
  return { page, close };
}

// ---------------------------------------------------------------- render helpers
const htmlDir = path.join(DATA, 'cards/_html');
fs.mkdirSync(htmlDir, { recursive: true });
const hashOf = (s) => createHash('sha256').update(s).digest('hex').slice(0, 16);
function upToDate(out, html) {
  if (FORCE) return false;
  try { return fs.existsSync(out) && fs.readFileSync(out + '.hash', 'utf8') === hashOf(html); } catch { return false; }
}
const stamp = (out, html) => fs.writeFileSync(out + '.hash', hashOf(html));

async function still(page, name, html, out, t) {
  if (upToDate(out, html + (t ?? ''))) { console.log(`  = ${path.relative(ROOT, out)} (cached)`); return; }
  const f = path.join(htmlDir, name + '.html'); fs.writeFileSync(f, html);
  await page.load(f);
  if (t !== undefined) await page.eval(`render(${t})`);
  fs.writeFileSync(out, await page.shot());
  stamp(out, html + (t ?? ''));
  console.log(`  + ${path.relative(ROOT, out)}`);
}

async function animation(page, name, html, out, seconds) {
  if (upToDate(out, html)) { console.log(`  = ${path.relative(ROOT, out)} (cached)`); return; }
  const f = path.join(htmlDir, name + '.html'); fs.writeFileSync(f, html);
  await page.load(f);
  const tmp = out + '.part.mov';
  const ff = spawn('nice', ['-n', '10', 'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '4',
    '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-c:v', 'png', '-pix_fmt', 'rgba', '-f', 'mov', tmp], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((r, j) => ff.on('exit', (c) => (c === 0 ? r() : j(new Error(`ffmpeg exited ${c}`)))));
  const n = Math.round(seconds * FPS); const t0 = Date.now();
  for (let i = 0; i < n; i += 1) {
    await page.eval(`render(${(i / FPS).toFixed(6)})`);
    const png = await page.shot();
    if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); await done;
  fs.renameSync(tmp, out); stamp(out, html);
  console.log(`  + ${path.relative(ROOT, out)} (${n} frames, ${((Date.now() - t0) / 1000).toFixed(1)} s)`);
}

// ---------------------------------------------------------------- main
const { page, close } = await launchBrowser();
try {
  for (const lang of LANGS) {
    const outDir = path.join(DATA, 'cards', lang);
    fs.mkdirSync(outDir, { recursive: true });
    console.log(`[cards] ${lang}`);
    if (ONLY.includes('captions')) {
      for (const cap of TL.captions) {
        await still(page, `cap_${cap.id}_${lang}`, captionHtml(cap, lang), path.join(outDir, `cap_${cap.id}.png`));
      }
    }
    // With the login page recording (clips/{lang}/sigil_clean.mp4) the cards go on top of it.
    const rec = REC_ALWAYS || fs.existsSync(path.join(DATA, 'clips', lang, 'sigil_clean.mp4'));
    const v = rec ? '_rec' : '';
    if (ONLY.includes('intro')) {
      const ih = introHtml(lang, rec ? 'recorded' : 'own');
      await still(page, `intro${v}_${lang}`, ih, path.join(outDir, `title${v}.png`), 7.9);
      await animation(page, `intro${v}_${lang}`, ih, path.join(outDir, `intro${v}.mov`), 8.0);
    }
    if (ONLY.includes('outro')) {
      const oh = outroHtml(lang, rec ? 'recorded' : 'own');
      await still(page, `outro${v}_${lang}`, oh, path.join(outDir, `outro${v}.png`), 7.9);
      await animation(page, `outro${v}_${lang}`, oh, path.join(outDir, `outro${v}.mov`), 8.0);
    }
  }
} finally {
  await close();
}

// Record the trailer's raw clips from the demo stack (http://127.0.0.1:8180) in headless Chromium.
//   node tools/trailer/record.mjs en|el [shot ...]      shots: sigil showhero 02 03 04 05 06 07 08 09
// Needs: demo stack up (demo-up.sh), accounts (register_accounts.mjs), seed (setup_demo.mjs <lang>).
// Output: data/trailer/clips/<lang>/<shot>.mp4, shots.json (durations + key moments), stills/.
// Capture: Page.startScreencast JPEG frames (compositor timestamps) -> ffmpeg concat -> CFR 60 fps x264 crf 14.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { launchChromium, CDP, sleep } from './lib/cdp.mjs';
import { Page, Recorder, newContextPage, activate, reseed } from './lib/driver.mjs';
import { api, must, login, accounts, T, BASE } from './lib/api.mjs';

const LANG = process.argv[2] === 'el' ? 'el' : 'en';
const ONLY = process.argv.slice(3);
const L = (en, el) => (LANG === 'el' ? el : en);
const OUT = T + `clips/${LANG}/`;
const FRAMES = T + `frames/${LANG}/`;
fs.mkdirSync(OUT + 'stills', { recursive: true });
const state = JSON.parse(fs.readFileSync(T + `demo-state.${LANG}.json`, 'utf8'));
const acc = accounts();
const shotsFile = OUT + 'shots.json';
const shots = fs.existsSync(shotsFile) ? JSON.parse(fs.readFileSync(shotsFile, 'utf8')) : {};
const want = (s) => !ONLY.length || ONLY.includes(s);
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

// ---------- browser ----------
const br = await launchChromium({ userDataDir: T + `chromium-profile/rec-${LANG}`, port: 9400 + (LANG === 'el' ? 1 : 0), lang: LANG === 'el' ? 'el-GR' : 'en-US' });
const bc = await CDP.connect(br.browserWs);
process.on('exit', () => { try { br.proc.kill(); } catch {} });

const pages = {};
async function page(name) {
  if (pages[name]) return pages[name];
  const p = await newContextPage(bc, name);
  await p.init();
  const ua = (await p.eval('navigator.userAgent')).replace('HeadlessChrome', 'Chrome');
  await p.send('Emulation.setUserAgentOverride', { userAgent: ua, acceptLanguage: LANG === 'el' ? 'el-GR,el' : 'en-US,en' });
  await p.send('Emulation.setFocusEmulationEnabled', { enabled: true });
  // Safety: the recording browser may only talk to the demo origin (never the live site on :80)
  await p.send('Network.enable');
  await p.send('Network.setBlockedURLs', { urls: ['http://127.0.0.1/*', 'http://localhost/*', 'http://127.0.0.1:80/*', 'http://localhost:80/*', '*srv-box*', 'http://10.0.0.3*'] });
  // No spell-check squiggles under typed text
  await p.send('Page.addScriptToEvaluateOnNewDocument', { source: `document.addEventListener('focusin', (e) => { if (e.target && 'spellcheck' in e.target) e.target.spellcheck = false; }, true);` });
  pages[name] = p;
  return p;
}
async function loginUI(p, user, { cps = 9, record = null } = {}) {
  await p.type('form.sr-auth__form input[autocomplete=username]', user, { cps });
  await sleep(250);
  await p.type('form.sr-auth__form input[type=password]', acc[user].password, { cps: Math.max(cps * 1.6, 14) });
  await sleep(300);
  record?.mark('signin_click_at');
  await p.click('form.sr-auth__form button[type=submit]');
}
async function ensureLoggedIn(user) {
  const p = await page(user);
  const href = await p.eval('location.href');
  if (href.startsWith(BASE) && !href.includes('/login') && (await p.eval(`!!localStorage.getItem('token')`))) return p;
  await p.goto(`${BASE}/login?lang=${LANG}`, { waitMs: 1200 });
  await loginUI(p, user, { cps: 60 });
  await p.waitFor('.sr-rail__item', { timeout: 15000 });
  await sleep(800);
  return p;
}

// ---------- helpers ----------
const tok = {};
async function token(u) { return (tok[u] ||= await login(u)); }
async function roomMessages(cid, lid) { const d = await must(api(`/campaigns/${cid}/locations/${lid}`, { token: await token('nyx') })); return Array.isArray(d) ? d : d.messages || []; }
async function deleteAfter(cid, lid, afterId) {
  for (const m of await roomMessages(cid, lid)) if (m.id > afterId) await api(`/messages/${m.id}`, { method: 'DELETE', token: await token('nyx') });
}
async function lastId(cid, lid) { const m = await roomMessages(cid, lid); return m.length ? Math.max(...m.map((x) => x.id)) : 0; }

/** Wait until the newest Storyteller line is in the room (no fixed sleeps around the AI). */
async function waitStoryteller(p, prevCount, timeout = 120000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const n = await p.eval(`document.querySelectorAll('.sr-msg-group--ai .sr-msg, .sr-msg-group--assistant .sr-msg').length`);
    const pending = await p.exists('.sr-chat__typing-text');
    if (n > prevCount && !pending) return true;
    await sleep(150);
  }
  throw new Error('Storyteller reply timeout');
}
const aiCount = (p) => p.eval(`document.querySelectorAll('.sr-msg-group--ai .sr-msg, .sr-msg-group--assistant .sr-msg').length`);

function stills(file, name, marks, duration) {
  const ts = new Set([0.6, duration * 0.3, duration * 0.55, duration * 0.8, Math.max(0, duration - 0.6), ...Object.values(marks).map((t) => Math.min(duration - 0.1, t + 0.6))]);
  [...ts].sort((a, b) => a - b).forEach((t, i) => {
    spawnSync('nice', ['-n', '10', 'ffmpeg', '-y', '-loglevel', 'error', '-ss', t.toFixed(2), '-i', file, '-frames:v', '1', '-q:v', '3', `${OUT}stills/${name}_${String(i).padStart(2, '0')}_${t.toFixed(1)}s.jpg`]);
  });
}
function save(name, rec, extra = {}) {
  const file = `${OUT}${name}.mp4`;
  const r = rec.render(file);
  for (const f of fs.readdirSync(OUT + 'stills')) if (f.startsWith(name + '_')) fs.rmSync(OUT + 'stills/' + f);
  stills(file, name, r.marks, r.duration);
  shots[name] = { path: `data/trailer/clips/${LANG}/${name}.mp4`, duration: r.duration, fps_capture_measured: r.fps_measured, ...r.marks, ...extra, recorded_at: new Date().toISOString() };
  fs.writeFileSync(shotsFile, JSON.stringify(shots, null, 2));
  fs.rmSync(rec.dir, { recursive: true, force: true });
  log(name, JSON.stringify(shots[name]));
}

// ======================= shots =======================

// Login page sigil reveal, untouched (15 s) and a "clean" take with the form hidden (recording-only CSS)
async function shotSigil() {
  for (const clean of [false, true]) {
    const p = await page('anon');
    await p.goto('about:blank', { waitMs: 100 });
    await p.eval(`document.documentElement.style.background='#07060b'`);
    const rec = new Recorder(p, FRAMES + 'sigil');
    if (clean) {
      await p.send('Page.addScriptToEvaluateOnNewDocument', { source: `document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent='.sr-auth__tagline,.sr-auth__card,.sr-auth__links,.sr-footer,footer{visibility:hidden!important}';document.head.appendChild(s);});` }).then((r) => (p._cleanScript = r.identifier));
    }
    await rec.start(p);
    rec.mark('navigate_at');
    await p.send('Page.navigate', { url: `${BASE}/login?lang=${LANG}` });
    await sleep(15500);
    await rec.stop();
    if (clean && p._cleanScript) await p.send('Page.removeScriptToEvaluateOnNewDocument', { identifier: p._cleanScript });
    save(clean ? 'sigil_clean' : 'sigil', rec, { note: clean ? 'login page with the form, tagline, links and footer hidden by recording-only CSS (sigil + wordmark + fog only)' : 'login page as is: page load -> SigilReveal draws (1.4 s) -> idle fog/candle' });
  }
}

// /showcase hero: sigil replay + fog, 10 s
async function shotShowHero() {
  const p = await page('anon');
  await p.goto(`${BASE}/showcase?lang=${LANG}`, { waitMs: 2500 });
  await p.eval('window.scrollTo(0,0)');
  const rec = new Recorder(p, FRAMES + 'showhero');
  await rec.start(p);
  await sleep(600);
  rec.mark('sigil_replay_at');
  await p.eval(`document.querySelector('button[aria-label*="sigil" i], .sc-hero button.sr-btn--icon')?.click()`);
  await sleep(10000);
  await rec.stop();
  save('showcase_hero', rec, { note: 'showcase hero: Replay-the-sigil clicked at sigil_replay_at (no ring), fog + candle glow' });
}

// 02 login: type username + password, sign in, the hall opens
async function shot02() {
  const p = await page('nyx');
  await p.goto(`${BASE}/login?lang=${LANG}`, { waitMs: 2600 });
  reseed(202);
  const rec = new Recorder(p, FRAMES + '02');
  await rec.start(p);
  await sleep(1300);
  rec.mark('typing_start_at');
  await loginUI(p, 'nyx', { cps: 8, record: rec });
  await p.waitFor('.sr-rail__item', { timeout: 15000 });
  rec.mark('hall_at');
  await sleep(3500);
  await rec.stop();
  save('shot02', rec);
}

// 03 new chronicle: Classic vs V5, game lines, create (a fresh copy, deleted after shot 04)
let freshCampaign = null;
async function showOptions(p, sel, ms) {
  const n = await p.eval(`document.querySelector(${JSON.stringify(sel)}).options.length`);
  if (n < 2) { await p.ring(await p.rect(sel), ms); await p.unring(); return; }
  await p.eval(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.size = e.options.length; e.style.height = 'auto'; e.style.overflow = 'hidden'; })()`);
  await sleep(30);
  await p.ring(await p.rect(sel), ms);
  await p.unring();
  await p.eval(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.removeAttribute('size'); e.style.height = ''; e.style.overflow=''; })()`);
}
async function cleanupFresh() {
  const nyx = await token('nyx');
  const list = await must(api('/campaigns/', { token: nyx }));
  for (const c of list) if (c.id !== state.v5 && c.id !== state.cl) await api(`/campaigns/${c.id}`, { method: 'DELETE', token: nyx });
}
async function shot03() {
  await cleanupFresh();
  const p = await ensureLoggedIn('nyx');
  await p.goto(`${BASE}/chronicles`, { waitMs: 2000 });
  reseed(303);
  const rec = new Recorder(p, FRAMES + '03');
  await rec.start(p);
  await sleep(900);
  await p.click('header a[href="/chronicles/new"], .sr-topbar a[href="/chronicles/new"], a.sr-btn[href="/chronicles/new"]');
  await p.waitFor('form.sr-form input[name=name]');
  rec.mark('form_at');
  await sleep(500);
  await p.type('form.sr-form input[name=name]', state.names.v5, { cps: 13 });
  await sleep(200);
  await p.type('form.sr-form textarea[name=description]', L('Thessaloniki by night. The Prince is missing and the harbour smells of blood.', 'Θεσσαλονίκη τη νύχτα. Ο Prince έχει χαθεί και το λιμάνι μυρίζει αίμα.'), { cps: 30 });
  await sleep(400);
  const sel = 'form.sr-form select';
  await p.click('form.sr-form input[value=classic]');
  rec.mark('classic_at');
  await sleep(300);
  await showOptions(p, sel, 1700);
  await sleep(250);
  await p.click('form.sr-form input[value=v5]');
  rec.mark('v5_at');
  await sleep(300);
  await showOptions(p, sel, 1300);
  await sleep(600);
  rec.mark('create_click_at');
  await p.click('form.sr-form button[type=submit]', { ringMs: 450 });
  for (let i = 0; i < 100 && !/\/chronicles\/\d+/.test(await p.eval('location.pathname')); i++) await sleep(100);
  rec.mark('created_at');
  await sleep(3000);
  await rec.stop();
  freshCampaign = Number((await p.eval('location.pathname')).split('/').pop());
  fs.writeFileSync(T + `fresh-campaign.${LANG}.json`, JSON.stringify({ id: freshCampaign }));
  save('shot03', rec, { note: 'creates a throwaway copy of the V5 chronicle (deleted after shot 04); the seeded one is used for play' });
}

// 04 forge: ianthe builds Ianthe Kallergi in the fresh chronicle, then the finished sheet
async function dot(p, label, n, opts) {
  const js = `(() => { const rows=[...document.querySelectorAll('#v5-section-attributes span, #v5-section-skills span')].filter(s=>s.textContent.trim()===${JSON.stringify(label)}); const row=rows[0]?.parentElement; return row ? row.querySelectorAll('button')[${n - 1}] : null; })()`;
  await p.click({ js }, { ringMs: 160, after: 90, ...opts });
}
async function shot04() {
  if (!freshCampaign) freshCampaign = JSON.parse(fs.readFileSync(T + `fresh-campaign.${LANG}.json`, 'utf8')).id;
  const nyx = await token('nyx');
  await api(`/campaigns/${freshCampaign}/members`, { method: 'POST', token: nyx, body: { username: 'ianthe' } });
  const p = await ensureLoggedIn('ianthe');
  await p.goto(`${BASE}/profile/characters/new?campaign=${freshCampaign}`, { waitMs: 2500 });
  await p.waitFor('#v5-field-character_name');
  // chronicle preselected?
  await p.select('#v5-field-chronicle', String(freshCampaign), { ring: false });
  reseed(404);
  const rec = new Recorder(p, FRAMES + '04');
  await rec.start(p);
  await sleep(800);
  const fast = { cps: 16 };
  await p.type('#v5-field-character_name', state.names.ianthe, fast);
  await p.type('#v5-field-concept', L('Gallery owner who never sleeps', 'Γκαλερίστα που δεν κοιμάται ποτέ'), { cps: 24 });
  await p.type('#v5-field-ambition', L('Own the city’s taste', 'Να ορίζει το γούστο της πόλης'), { cps: 24 });
  await p.select('#v5-field-clan', 'Toreador');
  rec.mark('clan_at');
  await sleep(500);
  // attributes: Cha 4; Dex, Man, Wit 3; Sta, Com, Int, Res 2; Str 1
  rec.mark('attributes_at');
  for (const [a, n] of [['Charisma', 4], ['Dexterity', 3], ['Manipulation', 3], ['Wits', 3], ['Stamina', 2], ['Composure', 2], ['Intelligence', 2], ['Resolve', 2]]) await dot(p, a, n);
  await sleep(400);
  rec.mark('skills_at');
  const skills = [['Persuasion', 3], ['Etiquette', 3], ['Insight', 3], ['Stealth', 2], ['Subterfuge', 2], ['Awareness', 2], ['Finance', 2], ['Streetwise', 2], ['Athletics', 1], ['Drive', 1], ['Larceny', 1], ['Intimidation', 1], ['Investigation', 1], ['Occult', 1], ['Politics', 1]];
  for (const [s, n] of skills) await dot(p, s, n, { ringMs: 120, after: 60 });
  await p.select('#v5-section-skills select:not(#v5-field-distribution)', 'etiquette');
  await p.type('#v5-section-skills input:not([type])', L('Art collectors', 'Συλλέκτες τέχνης'), { cps: 24 });
  await sleep(300);
  rec.mark('disciplines_at');
  await p.select({ js: `document.querySelectorAll('#v5-section-disciplines select')[0]` }, 'Presence');
  await p.select({ js: `document.querySelectorAll('#v5-section-disciplines select')[1]` }, 'Auspex');
  await sleep(300);
  rec.mark('predator_at');
  await p.select('#v5-field-predator', 'Siren');
  await sleep(300);
  await p.click('input[name=v5-predator-specialty]');
  await p.select('#v5-field-predator-discipline', 'Presence');
  await sleep(300);
  rec.mark('advantages_at');
  const adv = [['Resources', 3], ['Haven', 2], ['Contacts', 2], [L('Prey Exclusion (artists)', 'Prey Exclusion (artists)'), -1]];
  for (let i = 0; i < adv.length; i++) {
    if (i > 0) await p.click({ js: `[...document.querySelectorAll('#v5-section-advantages button')].find(b => b.textContent.trim().startsWith('+'))` }, { ringMs: 150, after: 150 });
    await p.type({ js: `document.querySelectorAll('#v5-section-advantages input:not([type=number])')[${i * 2}]` }, adv[i][0], { cps: 26 });
    await p.type({ js: `document.querySelectorAll('#v5-section-advantages input[type=number]')[${i}]` }, String(adv[i][1]), { cps: 10, clear: true });
  }
  await sleep(300);
  rec.mark('humanity_at');
  await p.type({ js: `document.querySelectorAll('#v5-section-humanity input')[0]` }, L('Never destroy a work of art', 'Ποτέ μην καταστρέψεις έργο τέχνης'), { cps: 26 });
  await p.type({ js: `document.querySelectorAll('#v5-section-humanity input')[1]` }, L('Daphne, her gallery assistant', 'Η Δάφνη, η βοηθός της στη γκαλερί'), { cps: 26 });
  await sleep(500);
  rec.mark('create_click_at');
  await p.click({ js: `[...document.querySelectorAll('main button')].filter(b => b.style.fontWeight === 'bold').pop()` }, { ringMs: 450 });
  for (let i = 0; i < 100 && !/^\/c\/\d+/.test(await p.eval('location.pathname')); i++) await sleep(100);
  const err = await p.eval(`[...document.querySelectorAll('[role=alert], .sr-toast')].map(e=>e.innerText).join(' | ')`);
  if (!/^\/c\//.test(await p.eval('location.pathname'))) throw new Error('forge did not finish: ' + err);
  rec.mark('created_at');
  await sleep(1800);
  await p.click({ re: '^(Character sheet|Φύλλο χαρακτήρα)$', sel: 'button' }, { ringMs: 400 });
  rec.mark('sheet_open_at');
  await sleep(2500);
  // scroll inside the sheet modal to Hunger / Willpower if it scrolls
  await p.eval(`(() => { const d=document.querySelector('[role=dialog]'); if(!d) return; const sc=[d,...d.querySelectorAll('*')].find(e=>e.scrollHeight>e.clientHeight+40 && ['auto','scroll'].includes(getComputedStyle(e).overflowY)); if(sc) sc.dataset.trailerScroll='1'; })()`);
  if (await p.exists('[data-trailer-scroll]')) { await p.scrollBy(500, { ms: 1400, container: '[data-trailer-scroll]' }); await sleep(1500); await p.scrollBy(500, { ms: 1400, container: '[data-trailer-scroll]' }); }
  await sleep(2500);
  await rec.stop();
  save('shot04', rec, { note: 'full forge at real speed; the edit speeds it up' });
  await api(`/campaigns/${freshCampaign}`, { method: 'DELETE', token: nyx });
}

// 05 play: ianthe writes, the Storyteller answers with a roll chip, stavros replies with a quote
const LADA_LINE = L('I slip into the alley behind the warehouse and keep to the shadows, trying to reach the back door before the buyer’s guards notice me.',
  'Γλιστράω στο στενό πίσω από την αποθήκη και μένω στις σκιές, προσπαθώντας να φτάσω στην πίσω πόρτα πριν με δουν οι φρουροί του αγοραστή.');
const STAV_REPLY = L('Careful, Kallergi. That courier works for me. If he sees you, the price doubles.',
  'Προσοχή, Καλλέργη. Αυτός ο κούριερ δουλεύει για μένα. Αν σε δει, η τιμή διπλασιάζεται.');
async function shot05() {
  const { v5, v5Rooms, chars } = state;
  const nyx = await token('nyx');
  // The Storyteller (nyx) sets Ianthe's Hunger to 4 on her sheet, as an ST does between scenes
  const ch = await must(api(`/characters/${chars.ianthe}`, { token: nyx }));
  const c = ch.character || ch; const wm = typeof c.wod_meta === 'string' ? JSON.parse(c.wod_meta) : c.wod_meta;
  if (wm.hunger !== 4) await must(api(`/characters/${chars.ianthe}`, { method: 'PUT', token: nyx, body: { wod_meta: { ...wm, hunger: 4 } } }));
  const ia = await ensureLoggedIn('ianthe');
  const st = await ensureLoggedIn('stavros');
  await st.goto(`${BASE}/c/${v5}/${v5Rooms.ladadika}`, { waitMs: 2500 });
  await ia.goto(`${BASE}/c/${v5}/${v5Rooms.ladadika}`, { waitMs: 3000 });
  await activate(bc, ia);
  reseed(505);
  const rec = new Recorder(ia, FRAMES + '05');
  await rec.start(ia);
  await sleep(1200);
  rec.mark('typing_start_at');
  await ia.type('textarea.sr-composer__input', LADA_LINE, { cps: 26 });
  await sleep(400);
  rec.mark('send_at');
  const before = await aiCount(ia);
  await ia.key('Enter');
  await sleep(500);
  rec.cutStart(1.6); // keep 1.6 s of "the Storyteller is weaving…"
  const t0 = Date.now();
  await waitStoryteller(ia, before);
  rec.cutEnd();
  const aiWait = (Date.now() - t0) / 1000;
  rec.mark('reply_at');
  await sleep(600);
  const hasChip = await ia.exists('.sr-msg:last-of-type .sr-rollreq__chip, .sr-rollreq__chip');
  await sleep(3200);
  // second player
  await activate(bc, st);
  await st.waitText(L('Stealth', 'Stealth'), { timeout: 20000 }).catch(() => {});
  await sleep(500);
  await rec.start(st);
  rec.mark('switch_to_stavros_at');
  await sleep(900);
  const lastAi = `[...document.querySelectorAll('.sr-msg-group--ai .sr-msg, .sr-msg-group--assistant .sr-msg')].pop()`;
  await st.hover({ js: lastAi });
  await sleep(500);
  const replyBtn = { js: `(${lastAi}).querySelectorAll('.sr-msg-actions__bar button')[1]` };
  if (!(await st.eval(`(() => { const b = ${replyBtn.js}; return b && b.getBoundingClientRect().width > 0 && getComputedStyle(b).visibility !== 'hidden'; })()`))) {
    await st.click({ js: `(${lastAi}).querySelector('.sr-msg-actions__more')` }, { ringMs: 250 });
  }
  rec.mark('reply_click_at');
  await st.click(replyBtn, { ringMs: 350 });
  await sleep(500);
  await st.type(null, STAV_REPLY, { cps: 24 });
  await sleep(400);
  rec.mark('quote_sent_at');
  await st.key('Enter');
  await sleep(3000);
  await rec.stop();
  save('shot05', rec, { ai_wait_cut_s: +aiWait.toFixed(1), roll_chip_present: hasChip });
}

// 06 dice: V5 roll from the chip (Hunger 4) until a messy critical or bestial failure; then Classic botch
function classify(r) {
  if (!r) return 'none';
  if ((r.modifiers?.rules_edition || '') === 'v5') {
    const h = r.modifiers.hunger_dice || [], n = r.modifiers.normal_dice || [];
    const tens = [...h, ...n].filter((d) => d === 10).length;
    const win = r.successes >= (r.difficulty || 0);
    if (win && tens >= 2 && h.includes(10)) return 'Messy critical';
    if (!win && h.includes(1)) return 'Bestial failure';
    return win ? 'win' : 'fail';
  }
  return r.is_botch ? 'Botch' : (r.successes > 0 ? 'success' : 'failure');
}
async function rollTake(p, recName, { openDialog, prepare, outcomes, maxTakes = 40, cid, lid }) {
  for (let take = 1; take <= maxTakes; take++) {
    const base = await lastId(cid, lid);
    const rs0 = (await api(`/campaigns/${cid}/rolls?location_id=${lid}&limit=1`, { token: await token('nyx') })).data || [];
    const baseRoll = rs0[0]?.id || 0;
    await p.goto(`${BASE}/c/${cid}/${lid}`, { waitMs: 2800 });
    reseed(600 + take);
    const rec = new Recorder(p, FRAMES + recName);
    await rec.start(p);
    await sleep(2000);
    await openDialog(p, rec);
    await p.waitFor('[role=dialog]');
    rec.mark('dialog_at');
    await sleep(2200);
    if (prepare) await prepare(p, rec);
    rec.mark('roll_click_at');
    await p.click({ js: `[...document.querySelectorAll('[role=dialog] button')].pop()` }, { ringMs: 400 });
    // the moment the dice overlay settles on the result (that is the music hit)
    let settled = false;
    for (let i = 0; i < 400 && !settled; i++) { settled = await p.exists('.sr-diceov.is-settled'); if (!settled) await sleep(25); }
    rec.mark('result_at');
    // the server's roll record decides the outcome (same rule as the UI: dice/v5DiceDisplay.js)
    let roll = null;
    for (let i = 0; i < 100 && !roll; i++) {
      const rs = (await api(`/campaigns/${cid}/rolls?location_id=${lid}&limit=1`, { token: await token('nyx') })).data || [];
      if (rs[0] && rs[0].id > baseRoll) roll = rs[0]; else await sleep(100);
    }
    const outcome = classify(roll);
    const hit = outcomes.includes(outcome) ? outcome : null;
    await sleep(hit ? 5500 : 300);
    await rec.stop();
    log(recName, 'take', take, hit ? `HIT ${hit}` : 'miss', outcome, JSON.stringify(roll && roll.results));
    if (hit) return { rec, take, outcome: hit, base };
    await deleteAfter(cid, lid, base);
  }
  throw new Error('no hit after max takes');
}
async function shot06() {
  const { v5, v5Rooms, cl, clRooms } = state;
  const ia = await ensureLoggedIn('ianthe');
  await activate(bc, ia);
  const v = await rollTake(ia, '06v5', {
    cid: v5, lid: v5Rooms.ladadika, outcomes: ['Messy critical', 'Bestial failure'],
    openDialog: async (p) => { await p.click({ js: `[...document.querySelectorAll('.sr-rollreq__chip')].filter(c => /\\b4 Hunger/i.test(c.innerText)).pop()` }, { ringMs: 450, block: 'center' }); },
  });
  // The V5 roll moment: dice tumble ~1.5-2 s after the click; result_at is when the outcome text is in the room
  const vr = v.rec;
  // Classic: Brother Anselm, Courage roll (3 dice, difficulty 8) with the dice button
  const st = await ensureLoggedIn('stavros');
  await activate(bc, st);
  const c = await rollTake(st, '06cl', {
    cid: cl, lid: clRooms.crypt, outcomes: ['Botch'],
    openDialog: async (p) => { await p.click({ js: `[...document.querySelectorAll('button.sr-btn.sr-btn--icon')].find(b => b.getBoundingClientRect().top > 980)` }, { ringMs: 400 }); },
    prepare: async (p) => {
      await p.type({ js: `document.querySelector('[role=dialog] input')` }, '3', { cps: 6, clear: true });
      await p.select({ js: `document.querySelector('[role=dialog] select')` }, '8');
      await p.type({ js: `document.querySelector('[role=dialog] textarea')` }, L('Courage: the skulls begin to whisper', 'Courage: τα κρανία αρχίζουν να ψιθυρίζουν'), { cps: 30 });
      await sleep(300);
    },
  });
  // render the parts and a combined clip (hard cut)
  save('shot06_v5', vr, { outcome: v.outcome, takes: v.take });
  save('shot06_classic', c.rec, { outcome: c.outcome, takes: c.take });
  const a = shots.shot06_v5, b = shots.shot06_classic;
  const list = T + `frames/${LANG}/concat06.txt`;
  fs.mkdirSync(path.dirname(list), { recursive: true });
  fs.writeFileSync(list, `file '${path.resolve(OUT + 'shot06_v5.mp4')}'\nfile '${path.resolve(OUT + 'shot06_classic.mp4')}'\n`);
  spawnSync('nice', ['-n', '10', 'ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', OUT + 'shot06.mp4']);
  shots.shot06 = { path: `data/trailer/clips/${LANG}/shot06.mp4`, duration: +(a.duration + b.duration).toFixed(3), v5_outcome: a.outcome, classic_outcome: b.outcome,
    v5_roll_click_at: a.roll_click_at, v5_result_at: a.result_at, classic_start_at: a.duration, classic_roll_click_at: +(a.duration + b.roll_click_at).toFixed(3), classic_result_at: +(a.duration + b.result_at).toFixed(3),
    note: 'shot06_v5 + shot06_classic joined (hard cut at classic_start_at). result_at = the moment the outcome text is in the room; the dice overlay tumbles between roll_click_at and result_at.' };
  fs.writeFileSync(shotsFile, JSON.stringify(shots, null, 2));
  stills(OUT + 'shot06.mp4', 'shot06', {}, shots.shot06.duration);
}

// 07 two languages: EN render shows a Greek exchange; EL render shows an English one
async function shot07() {
  const { v5, v5Rooms } = state;
  const ia = await ensureLoggedIn('ianthe');
  await ia.goto(`${BASE}/c/${v5}/${v5Rooms.elysium}`, { waitMs: 3000 });
  await activate(bc, ia);
  reseed(707);
  const line = L('Ρωτάω τον Λόρδο Δημητρίου, χαμηλόφωνα: ποιος είδε τελευταίος τον Prince, και πού;',
    'I ask the Harpies, quietly: who saw the Prince last, and where?');
  const rec = new Recorder(ia, FRAMES + '07');
  await rec.start(ia);
  await sleep(1000);
  rec.mark('typing_start_at');
  await ia.type('textarea.sr-composer__input', line, { cps: 24 });
  await sleep(300);
  rec.mark('send_at');
  const before = await aiCount(ia);
  await ia.key('Enter');
  await sleep(500);
  rec.cutStart(1.2);
  const t0 = Date.now();
  await waitStoryteller(ia, before);
  rec.cutEnd();
  rec.mark('reply_at');
  await sleep(5000);
  await rec.stop();
  const lastText = await ia.eval(`[...document.querySelectorAll('.sr-msg')].pop().innerText`);
  save('shot07', rec, { ai_wait_cut_s: +((Date.now() - t0) / 1000).toFixed(1), reply_excerpt: lastText.slice(0, 200) });
}

// 08 moderation: stavros posts an in-character line in the OOC room, Laya flags it; admin pages
async function shot08() {
  const { v5, v5Rooms } = state;
  // A real failed sign-in from the browser (mistyped password), so the audit shows more than sign-ins
  const fail = await page('anon');
  await fail.goto(`${BASE}/login?lang=${LANG}`, { waitMs: 1500 });
  await fail.type('form.sr-auth__form input[autocomplete=username]', 'stavros', { cps: 60, ring: false });
  await fail.type('form.sr-auth__form input[type=password]', 'not-my-password-1', { cps: 80, ring: false });
  await fail.click('form.sr-auth__form button[type=submit]', { ring: false });
  await sleep(1500);
  const st = await ensureLoggedIn('stavros');
  await st.goto(`${BASE}/c/${v5}/${v5Rooms.ooc}`, { waitMs: 3000 });
  const nyx = await ensureLoggedIn('nyx');
  await nyx.goto(`${BASE}/admin`, { waitMs: 2000 });
  await activate(bc, st);
  reseed(808);
  const rec = new Recorder(st, FRAMES + '08');
  await rec.start(st);
  await sleep(1000);
  rec.mark('typing_start_at');
  await st.type('textarea.sr-composer__input', L('*Stavros bares his fangs at the courier and hisses, then melts back into the dark of the cistern.*', '*Ο Σταύρος δείχνει τα δόντια του στον κούριερ και σφυρίζει, μετά χάνεται ξανά στο σκοτάδι της στέρνας.*'), { cps: 30 });
  await sleep(300);
  rec.mark('send_at');
  await st.key('Enter');
  for (let i = 0; i < 100 && !(await st.eval(`/warning|προειδοποίηση|Προειδοποίηση/i.test(document.body.innerText)`)); i++) await sleep(100);
  rec.mark('laya_warning_at');
  await sleep(3500);
  await activate(bc, nyx);
  await rec.start(nyx);
  rec.mark('admin_at');
  await sleep(500);
  await nyx.click('button[id$="-tab-security"]', { ringMs: 350 });
  rec.mark('security_at');
  await sleep(2600);
  await nyx.click('button[id$="-tab-ai"]', { ringMs: 350 });
  rec.mark('ai_roles_at');
  await sleep(1200);
  const roles = { js: `[...document.querySelectorAll('h2,h3,h4')].find(h => /per role|ανά ρόλο|ρόλο/i.test(h.textContent))` };
  if (await nyx.exists(roles)) { await nyx.scrollTo(roles, { ms: 1200, offset: 90, container: await nyx.eval(`(() => { const m=document.querySelector('main'); return m && m.scrollHeight > m.clientHeight + 20 ? 'main' : null; })()`) }); rec.mark('ai_roles_models_at'); }
  await sleep(2400);
  await rec.stop();
  save('shot08', rec);
}

// 09 showcase: glyphs, clan sigils, fog/candle, atmosphere Full / Subtle / Off
async function shot09() {
  const p = await page('anon');
  await p.goto(`${BASE}/showcase?lang=${LANG}`, { waitMs: 2500 });
  await p.eval(`(() => { const f=document.querySelector('.sc-top input[value=full], input[value=full]'); f && f.click(); window.scrollTo(0,0); })()`);
  await sleep(800);
  reseed(909);
  const rec = new Recorder(p, FRAMES + '09');
  await rec.start(p);
  await sleep(2200);
  rec.mark('glyphs_at');
  await p.scrollTo('#sc-glyphs', { ms: 1400, offset: 40 });
  await sleep(800);
  await p.hover('button.sc-glyph:nth-of-type(6)').catch(() => {});
  await sleep(1300);
  const clanHead = { js: `[...document.querySelectorAll('#sc-glyphs h3, #sc-glyphs h4, #sc-glyphs [class*=group] > *')].find(e => /Clan sigils|Σύμβολα φατριών|clan/i.test(e.textContent) && e.textContent.length < 40)` };
  rec.mark('clans_at');
  if (await p.exists(clanHead)) await p.scrollTo(clanHead, { ms: 1400, offset: 140 });
  await sleep(600);
  await p.hover({ js: `[...document.querySelectorAll('button.sc-glyph')].find(b => /Toreador/.test(b.getAttribute('aria-label') || b.textContent))` }).catch(() => {});
  await sleep(1500);
  rec.mark('back_to_hero_at');
  await p.scrollBy(-(await p.eval('document.scrollingElement.scrollTop')), { ms: 1600 });
  await sleep(1200);
  for (const [mode, ms] of [['subtle', 1700], ['off', 1700], ['full', 2200]]) {
    rec.mark(`atmosphere_${mode}_at`);
    await p.click({ js: `[...document.querySelectorAll('input[value=${mode}]')].map(i => i.closest('label') || i).find(e => e.getBoundingClientRect().top < 80)` }, { ringMs: 300 });
    await sleep(ms);
  }
  await rec.stop();
  save('shot09', rec);
}

const order = [['sigil', shotSigil], ['showhero', shotShowHero], ['02', shot02], ['03', shot03], ['04', shot04], ['05', shot05], ['06', shot06], ['07', shot07], ['08', shot08], ['09', shot09]];
try {
  for (const [k, fn] of order) {
    if (!want(k)) continue;
    log('=== shot', k);
    await fn();
  }
} catch (e) {
  console.error('FAILED', e.stack || e);
  for (const [n, p] of Object.entries(pages)) await p.screenshot(T + `debug-${LANG}-${n}.png`).catch(() => {});
  process.exitCode = 1;
} finally {
  bc.close(); br.proc.kill();
}

// Record the raw clips of trailer v2 (150 s, CUES_v2.md / timeline_v2.json) from the demo stack
// (http://127.0.0.1:8180) in headless Chromium.
//   TRAILER_DATA=data/trailer-v2 node tools/trailer/record_v2.mjs en|el [shot ...]
//   shots: 04 05 07 08 10 13 14        (05 also writes shot06: Guided and the forge are one take;
//          13 also makes shot13_pdf from the downloaded PDF; `pdfclip` remakes only that)
// Needs: the demo stack seeded for the language (reset_demo.sh), LM Studio with the Storyteller models.
// Output: <TRAILER_DATA>/clips/<lang>/<shot>.mp4, shots.json (durations + the marks timeline_v2.json
// names in its "_marks"), stills/, takes.log (every dice take). Real results only: Storyteller
// lines come from the model, dice from the server; a roll is retaken until the wanted outcome lands.
// Machine limits: run it under `taskset -c 0-15 nice -n 10`; one recording at a time.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { launchChromium, CDP, sleep } from './lib/cdp.mjs';
import { Recorder, newContextPage, activate, reseed } from './lib/driver.mjs';
import { api, must, login, accounts, T, ROOT, BASE } from './lib/api.mjs';

if (!/trailer-v2\/$/.test(T)) throw new Error(`record_v2.mjs writes trailer v2 clips: run it with TRAILER_DATA=data/trailer-v2 (now ${T})`);
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
const takesLog = (line) => fs.appendFileSync(T + `takes.${LANG}.log`, `${new Date().toISOString()} ${line}\n`);

// ---------- browser (own headless Chromium on 9410/9411; never the personal browser) ----------
const br = await launchChromium({ userDataDir: T + `chromium-profile/rec-${LANG}`, port: 9410 + (LANG === 'el' ? 1 : 0), lang: LANG === 'el' ? 'el-GR' : 'en-US' });
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
  await p.send('Network.setBlockedURLs', { urls: ['http://127.0.0.1/*', 'http://localhost/*', 'http://127.0.0.1:80/*', 'http://localhost:80/*', ...(process.env.TRAILER_BLOCK_URLS || '').split(',').filter(Boolean)] });
  // No spell-check squiggles under typed text
  await p.send('Page.addScriptToEvaluateOnNewDocument', { source: `document.addEventListener('focusin', (e) => { if (e.target && 'spellcheck' in e.target) e.target.spellcheck = false; }, true);` });
  pages[name] = p;
  return p;
}
async function ensureLoggedIn(user) {
  const p = await page(user);
  const href = await p.eval('location.href');
  if (href.startsWith(BASE) && !href.includes('/login') && (await p.eval(`!!localStorage.getItem('token')`))) return p;
  await p.goto(`${BASE}/login?lang=${LANG}`, { waitMs: 1200 });
  await p.type('form.sr-auth__form input[autocomplete=username]', user, { cps: 60, ring: false });
  await p.type('form.sr-auth__form input[type=password]', acc[user].password, { cps: 90, ring: false });
  await p.click('form.sr-auth__form button[type=submit]', { ring: false });
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
const AI_MSGS = `document.querySelectorAll('.sr-msg-group--ai .sr-msg, .sr-msg-group--assistant .sr-msg')`;
const aiCount = (p) => p.eval(`${AI_MSGS}.length`);
/** Wait until a new Storyteller line is in the room and the "weaving" indicator is gone. */
async function waitStoryteller(p, prevCount, timeout = 120000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const n = await aiCount(p);
    const pending = await p.exists('.sr-chat__typing-text');
    if (n > prevCount && !pending) return true;
    await sleep(120);
  }
  throw new Error('Storyteller reply timeout');
}
/** Show a <select>'s options as an open list for `ms` (headless Chromium paints no native popup). */
async function showOptions(p, target, ms, { rows = 9 } = {}) {
  const js = typeof target === 'string' ? `document.querySelector(${JSON.stringify(target)})` : target.js;
  const n = await p.eval(`(${js}).options.length`);
  await p.eval(`(() => { const e = ${js}; e.dataset.trailerH = e.style.height; e.size = Math.min(${rows}, e.options.length); e.style.height = 'auto'; e.style.position = 'relative'; e.style.zIndex = '30'; })()`);
  await sleep(30);
  await p.ring(await p.rect({ js }), ms);
  await p.unring();
  await p.eval(`(() => { const e = ${js}; e.removeAttribute('size'); e.style.height = e.dataset.trailerH || ''; e.style.position = ''; e.style.zIndex = ''; })()`);
  return n;
}
/** The page's scrolling element for the app layout (main.sr-page scrolls, not the document). */
const MAIN = 'main.sr-page';
async function scrollMainTo(p, target, { ms = 900, offset = 140 } = {}) {
  const container = (await p.exists(MAIN)) && (await p.eval(`(() => { const m = document.querySelector('${MAIN}'); return m.scrollHeight > m.clientHeight + 20; })()`)) ? MAIN : null;
  const r = await p.rect(target);
  if (!r) throw new Error('scroll target not found: ' + JSON.stringify(target));
  await p.scrollBy(r.y - offset, { ms, container });
  await sleep(60);
}
function stills(file, name, marks, duration) {
  const ts = new Set([0.6, duration * 0.3, duration * 0.55, duration * 0.8, Math.max(0, duration - 0.6), ...Object.values(marks).map((t) => Math.min(duration - 0.1, t + 0.6))]);
  [...ts].sort((a, b) => a - b).forEach((t, i) => {
    spawnSync('nice', ['-n', '10', 'ffmpeg', '-y', '-loglevel', 'error', '-ss', t.toFixed(2), '-i', file, '-frames:v', '1', '-q:v', '3', `${OUT}stills/${name}_${String(i).padStart(2, '0')}_${t.toFixed(1)}s.jpg`]);
  });
}
const rel = (f) => path.relative(ROOT, path.resolve(f));
function save(name, rec, extra = {}, also = []) {
  const file = `${OUT}${name}.mp4`;
  const r = rec.render(file);
  for (const n of [name, ...also]) {
    for (const f of fs.readdirSync(OUT + 'stills')) if (f.startsWith(n + '_')) fs.rmSync(OUT + 'stills/' + f);
  }
  stills(file, name, r.marks, r.duration);
  const entry = { path: rel(file), duration: r.duration, fps_capture_measured: r.fps_measured, ...r.marks, ...extra, recorded_at: new Date().toISOString() };
  shots[name] = entry;
  for (const n of also) { fs.copyFileSync(file, `${OUT}${n}.mp4`); shots[n] = { ...entry, path: rel(`${OUT}${n}.mp4`), same_take_as: name }; }
  fs.writeFileSync(shotsFile, JSON.stringify(shots, null, 2));
  fs.rmSync(rec.dir, { recursive: true, force: true });
  log(name, JSON.stringify(shots[name]));
}

// ======================= shots =======================

// 04 creation rules: nyx on the V5 chronicle's settings, the "Character creation rules" card
const HOUSE_RULE = L('Every character needs a reason to stay in Thessaloniki.', 'Κάθε χαρακτήρας χρειάζεται έναν λόγο να μένει στη Θεσσαλονίκη.');
const RULES_LIST = (i) => `[...document.querySelectorAll('fieldset.sr-creation-rules__list')][${i}]`; // 0 books, 1 clans, 2 predators, 3 ages
const ruleBox = (list, name) => ({ js: `[...${RULES_LIST(list)}.querySelectorAll('label')].find(l => l.textContent.replace(/\\s+/g,' ').trim().startsWith(${JSON.stringify(name)}))` });
async function shot04() {
  const { v5 } = state;
  const nyx = await token('nyx');
  await must(api(`/campaigns/${v5}`, { method: 'PUT', token: nyx, body: { creation_settings: {} } }));
  const p = await ensureLoggedIn('nyx');
  await p.goto(`${BASE}/chronicles/${v5}`, { waitMs: 2500 });
  await p.waitFor({ js: RULES_LIST(1) });
  reseed(404);
  const rec = new Recorder(p, FRAMES + '04');
  await rec.start(p);
  await sleep(1000);
  const title = { js: `(() => { let e = document.querySelector('fieldset.sr-creation-rules__list'); while (e && !e.querySelector('h2,h3')) e = e.parentElement; return e && e.querySelector('h2,h3'); })()` };
  await scrollMainTo(p, title, { ms: 1500, offset: 72 });
  rec.mark('rules_card_at');
  await sleep(700);
  await p.click(ruleBox(1, 'Thin-blood'), { ringMs: 380, after: 300 });
  await p.click(ruleBox(1, 'Caitiff'), { ringMs: 380, after: 300 });
  rec.mark('hecata_tick_at');
  await p.ring(await p.rect(ruleBox(1, 'Hecata')), 1200);
  await p.unring();
  await sleep(350);
  rec.mark('age_at');
  const ages = await p.eval(`[...${RULES_LIST(3)}.querySelectorAll('label')].map(l => l.textContent.trim())`);
  await p.click({ js: `[...${RULES_LIST(3)}.querySelectorAll('label')][0]` }, { ringMs: 380, after: 300 }); // childe / fledgling
  await p.click({ js: `[...${RULES_LIST(3)}.querySelectorAll('label')][2]` }, { ringMs: 380, after: 300 }); // ancilla
  await p.ring(await p.rect({ js: `[...${RULES_LIST(3)}.querySelectorAll('label')][1]` }), 700); // neonate stays
  await p.unring();
  await sleep(250);
  const area = { js: `[...document.querySelectorAll('textarea')].find(t => t.closest('form') && t.closest('form').querySelector('fieldset.sr-creation-rules__list'))` };
  await scrollMainTo(p, area, { ms: 1000, offset: 420 });
  await sleep(250);
  rec.mark('house_rule_at');
  await p.type(area, HOUSE_RULE, { cps: 20 });
  await sleep(500);
  const saveBtn = { js: `(${area.js}).closest('form').querySelector('button[type=submit]')` };
  rec.mark('save_click_at');
  await p.click(saveBtn, { ringMs: 450 });
  await sleep(2200);
  await rec.stop();
  const cs = (await must(api(`/campaigns/${v5}`, { token: nyx }))).campaign?.creation_settings || (await must(api(`/campaigns/${v5}`, { token: nyx }))).creation_settings;
  log('creation settings now', JSON.stringify(cs));
  if (!cs || !(cs.allowed_clans || []).includes('Hecata') || !String(cs.house_rules || '').includes(HOUSE_RULE.slice(0, 20))) throw new Error('creation rules not saved: ' + JSON.stringify(cs));
  save('shot04', rec, { ages_listed: ages, creation_settings: cs });
}

// 05 + 06 Guided mode -> the forge -> the finished sheet (one take: the guide's prefill lives in the page)
const GUIDED = { confrontation: 'charm', night_job: 'night_shift', feeding: 'dying', fear: 'the_dead', mortal_ties: 'mine', secrets: 'dig', ambition: 'knowledge', body_mind: 'instinct' };
const KAL = {
  name: L('Kalliroi Daskalaki', 'Καλλιρρόη Δασκαλάκη'),
  concept: L('Undertaker who keeps the family business and talks to the dead', 'Νεκροθάφτρια που κρατά την οικογενειακή επιχείρηση και μιλά με τους νεκρούς'),
  ambition: L('Keep the family parlour open for another century', 'Να κρατήσει το γραφείο τελετών ανοιχτό άλλον έναν αιώνα'),
  desire: L('Learn who left a body on her doorstep', 'Να μάθει ποιος άφησε ένα πτώμα στο κατώφλι της'),
  // the guide rates Academics and Science, which bring a free specialty each, plus one of her choice
  specialties: [['academics', L('Funeral rites', 'Νεκρώσιμες τελετές')], ['science', L('Embalming', 'Ταρίχευση')], ['occult', L('Ghosts', 'Φαντάσματα')]],
  conviction: L('Never deny the dead their rites', 'Ποτέ μην αρνηθείς στους νεκρούς τις τελετές τους'),
  touchstone: L('Myrto, her niece at the front desk', 'Η Μυρτώ, η ανιψιά της στο γραφείο'),
};
const sel = (aria) => ({ js: `[...document.querySelectorAll('select')].find(s => s.getAttribute('aria-label') === ${JSON.stringify(aria)})` });
// the two Discipline picks (at 2 dots, at 1 dot): the selects that list Disciplines, not powers
const discSelect = (i) => ({ js: `[...document.querySelectorAll('#v5-section-disciplines select')].filter(s => !s.id && [...s.options].some(o => ['Oblivion', 'Fortitude', 'Auspex'].includes(o.value)))[${i}]` });
async function deleteKalliroiChars() {
  const k = await token('kalliroi');
  const list = await must(api('/characters/', { token: k }));
  for (const c of (Array.isArray(list) ? list : list.characters || [])) await api(`/characters/${c.id}`, { method: 'DELETE', token: await token('nyx') });
}
async function shot05() {
  const { v5 } = state;
  await deleteKalliroiChars();
  const p = await ensureLoggedIn('kalliroi');
  await p.goto(`${BASE}/profile/characters/new?campaign=${v5}`, { waitMs: 2500 });
  const guidedBtn = { js: `document.querySelector('[aria-labelledby="v5-mode-guided-title"]')` };
  await p.waitFor(guidedBtn);
  await sleep(1500); // catalog + question set in
  reseed(505);
  const rec = new Recorder(p, FRAMES + '05');
  await rec.start(p);
  await sleep(1300);
  rec.mark('guided_click_at');
  await p.click(guidedBtn, { ringMs: 500, after: 200 });
  await p.waitFor('#guided-question');
  rec.mark('q1_at');
  const nextBtn = { js: `[...document.querySelector('section[aria-labelledby="guided-question"]').querySelectorAll('button')].pop()` };
  const qid = () => p.eval(`document.querySelector('[role=radiogroup] input')?.name?.replace('guided-','')`);
  let q = await qid();
  await sleep(1000);
  await p.click(`#guided-${q}-${GUIDED[q]}`, { ringMs: 380, after: 450 });
  await p.click(nextBtn, { ringMs: 260, after: 120 });
  const waitQ = async (prev) => { for (let i = 0; i < 80; i++) { const n = await qid(); if (n && n !== prev) return n; await sleep(25); } throw new Error('next question did not come'); };
  q = await waitQ(q);
  rec.mark('q2_at');
  const total = await p.eval(`+document.querySelector('[role=progressbar]').getAttribute('aria-valuemax')`);
  for (let i = 2; i < total; i++) {
    await sleep(420);
    await p.click(`#guided-${q}-${GUIDED[q]}`, { ringMs: 220, after: 160 });
    await p.click(nextBtn, { ringMs: 160, after: 60 });
    q = await waitQ(q);
  }
  rec.mark('q_last_at');
  await sleep(1000);
  await p.click(`#guided-${q}-${GUIDED[q]}`, { ringMs: 380, after: 500 });
  await p.click(nextBtn, { ringMs: 380, after: 80 });
  await p.waitFor('#guided-result-title');
  rec.mark('suggestion_at');
  const result = await p.eval(`[...document.querySelectorAll('section[aria-labelledby="guided-result-title"] [lang=en]')].map(e => e.textContent.trim())`);
  log('guided suggests', result);
  await sleep(700);
  const cards = `[...document.querySelectorAll('section[aria-labelledby="guided-result-title"] > div')]`;
  await p.ring(await p.rect({ js: `${cards}[0]` }), 1100);
  await p.ring(await p.rect({ js: `${cards}[1]` }), 900);
  await p.unring();
  await sleep(300);
  rec.mark('open_forge_at');
  await p.click({ js: `[...document.querySelectorAll('section[aria-labelledby="guided-result-title"] button')].pop()` }, { ringMs: 450, after: 100 });
  await p.waitFor('#v5-field-character_name');
  rec.mark('forge_at');
  await sleep(1400);
  // Concept
  await p.type('#v5-field-character_name', KAL.name, { cps: 18 });
  await p.type('#v5-field-concept', KAL.concept, { cps: 34 });
  await p.type('#v5-field-ambition', KAL.ambition, { cps: 34 });
  await p.type('#v5-field-desire', KAL.desire, { cps: 34 });
  await sleep(300);
  // Clan (filled in by the guide): its catalog card
  await scrollMainTo(p, '#v5-section-clan', { ms: 900, offset: 150 });
  rec.mark('clan_at');
  await sleep(300);
  const clanNote = { js: `document.querySelector('#v5-section-clan .sr-catalog-note').parentElement` };
  await p.ring(await p.rect(clanNote), 2000);
  await p.unring();
  await sleep(200);
  // Attributes and Skills (filled in by the guide) + the two free specialties
  await scrollMainTo(p, '#v5-section-attributes', { ms: 900, offset: 150 });
  rec.mark('attributes_at');
  await sleep(900);
  await scrollMainTo(p, '#v5-section-skills', { ms: 900, offset: 150 });
  rec.mark('skills_at');
  await sleep(600);
  const addSpec = { js: `[...document.querySelectorAll('#v5-section-skills button')].find(b => b.textContent.trim().startsWith('+'))` };
  for (let i = 0; i < KAL.specialties.length; i++) {
    if (!(await p.exists(addSpec))) break;
    await p.click(addSpec, { ringMs: 220, after: 150 });
    await p.select({ js: `[...document.querySelectorAll('#v5-section-skills select:not(#v5-field-distribution)')][${i}]` }, KAL.specialties[i][0], { ringMs: 260 });
    await p.type({ js: `[...document.querySelectorAll('#v5-section-skills input')].filter(e => !e.type || e.type === 'text')[${i}]` }, KAL.specialties[i][1], { cps: 30 });
  }
  await sleep(300);
  // Disciplines: Oblivion 2 (two powers), Fortitude 1, a Level 1 ceremony, the predator preview
  await scrollMainTo(p, '#v5-section-disciplines', { ms: 900, offset: 150 });
  rec.mark('disciplines_at');
  await sleep(350);
  await p.select(discSelect(0), 'Oblivion', { ringMs: 420 });
  await sleep(250);
  const powerSel = (disc, n) => ({ js: `[...document.querySelectorAll('#v5-section-disciplines select')].find(s => s.getAttribute('aria-label') === ${JSON.stringify(`${disc} power ${n}`)} || (s.getAttribute('aria-label') || '').startsWith(${JSON.stringify(disc)}) && (s.getAttribute('aria-label') || '').endsWith(' ${n}'))` });
  rec.mark('power_list_at');
  await showOptions(p, powerSel('Oblivion', 1), 1300, { rows: 5 });
  await p.select(powerSel('Oblivion', 1), 'Ashes to Ashes', { ringMs: 200 });
  rec.mark('power_at');
  await p.ring(await p.rect({ js: `(${powerSel('Oblivion', 1).js}).parentElement` }), 1300);
  await p.unring();
  await p.select(powerSel('Oblivion', 2), 'The Binding Fetter', { ringMs: 300 });
  await sleep(250);
  await p.select(discSelect(1), 'Fortitude', { ringMs: 380 });
  await sleep(200);
  await p.select(powerSel('Fortitude', 1), 'Resilience', { ringMs: 300 });
  await sleep(250);
  await scrollMainTo(p, '#v5-field-starting-ceremony', { ms: 700, offset: 360 });
  rec.mark('ceremony_at');
  await showOptions(p, '#v5-field-starting-ceremony', 1000, { rows: 5 });
  await p.select('#v5-field-starting-ceremony', 'Summon Spirit', { ringMs: 200 });
  await p.ring(await p.rect({ js: `document.querySelector('#v5-field-starting-ceremony').parentElement` }), 1300);
  await p.unring();
  await sleep(200);
  rec.mark('predator_preview_at');
  await p.ring(await p.rect({ js: `document.getElementById('v5-field-predator-preview').closest('[role=region]')` }), 1600);
  await p.unring();
  // Predator type (Grim Reaper from the guide): specialty, Discipline dot, its Advantage
  await scrollMainTo(p, '#v5-section-predator', { ms: 900, offset: 150 });
  rec.mark('predator_at');
  await sleep(300);
  await p.click({ js: `document.querySelectorAll('input[name=v5-predator-specialty]')[0]` }, { ringMs: 260, after: 200 });
  await p.select('#v5-field-predator-discipline', 'Auspex', { ringMs: 300 });
  await sleep(200);
  const predAdv = { js: `[...document.querySelectorAll('#v5-section-predator input[type=radio]')].find(i => i.name !== 'v5-predator-specialty' && /Allies/.test(i.parentElement.textContent))` };
  if (await p.exists(predAdv)) await p.click(predAdv, { ringMs: 260, after: 200 });
  // the predator's Auspex dot asks for its power (back in the Disciplines step)
  if (await p.exists(powerSel('Auspex', 1))) {
    await scrollMainTo(p, powerSel('Auspex', 1), { ms: 700, offset: 400 });
    await p.select(powerSel('Auspex', 1), 'Sense the Unseen', { ringMs: 300 });
    await sleep(200);
  }
  // Advantages from the catalog dropdowns: Backgrounds and two Flaws of her own
  await scrollMainTo(p, '#v5-section-advantages', { ms: 900, offset: 150 });
  rec.mark('advantages_at');
  await sleep(300);
  const addIn = (kind) => ({ js: `document.querySelector('[data-adv-section=${kind}]') && [...document.querySelector('[data-adv-section=${kind}]').querySelectorAll('button')].pop()` });
  const rowSel = (kind, i) => ({ js: `[...document.querySelector('[data-adv-section=${kind}]').querySelectorAll('select')].filter(s => !/dots|τελείες|●/i.test(s.getAttribute('aria-label') || '') && s.options[0] && s.options[0].value === '')[${i}]` });
  const dotSel = (kind, i) => ({ js: `[...document.querySelector('[data-adv-section=${kind}]').querySelectorAll('select')].filter(s => s.options.length && [...s.options].every(o => /^[●–]+$/.test(o.text.trim())))[${i}]` });
  const bgs = [['background:resources', 3], ['background:haven', 2], ['background:contacts', 2]];
  for (let i = 0; i < bgs.length; i++) {
    await p.click(addIn('background'), { ringMs: 200, after: 150 });
    await p.select(rowSel('background', i), bgs[i][0], { ringMs: 260 });
    if (await p.exists(dotSel('background', i))) await p.select(dotSel('background', i), String(bgs[i][1]), { ringMs: 200 });
    await sleep(150);
  }
  rec.mark('flaws_at');
  for (const [i, id] of [['0', 'flaw:haunted'], ['1', 'flaw:creepy']]) {
    await p.click(addIn('flaw'), { ringMs: 200, after: 150 });
    await p.select(rowSel('flaw', +i), id, { ringMs: 260 });
    if (await p.exists(dotSel('flaw', +i))) await p.select(dotSel('flaw', +i), '1', { ringMs: 200 });
    await sleep(150);
  }
  const count = await p.eval(`document.getElementById('v5-advantages-count')?.textContent`);
  log('advantages', count);
  // Convictions
  await scrollMainTo(p, '#v5-section-humanity', { ms: 900, offset: 150 });
  rec.mark('convictions_at');
  await sleep(250);
  await p.type({ js: `document.querySelectorAll('#v5-section-humanity input:not([type=checkbox])')[0]` }, KAL.conviction, { cps: 34 });
  await p.type({ js: `document.querySelectorAll('#v5-section-humanity input:not([type=checkbox])')[1]` }, KAL.touchstone, { cps: 34 });
  await sleep(300);
  await scrollMainTo(p, '#v5-section-age', { ms: 800, offset: 150 });
  rec.mark('age_step_at');
  await sleep(900);
  const createBtn = { js: `[...document.querySelectorAll('main button')].filter(b => b.style.fontWeight === 'bold').pop()` };
  await scrollMainTo(p, createBtn, { ms: 800, offset: 700 });
  await sleep(300);
  rec.mark('create_click_at');
  await p.click(createBtn, { ringMs: 450 });
  for (let i = 0; i < 120 && !/^\/c\/\d+/.test(await p.eval('location.pathname')); i++) await sleep(100);
  if (!/^\/c\//.test(await p.eval('location.pathname'))) {
    const err = await p.eval(`[...document.querySelectorAll('[role=alert], .sr-toast, [role=status]')].map(e=>e.innerText).join(' | ')`);
    const inline = await p.eval(`[...document.querySelectorAll('main p')].filter(e => getComputedStyle(e).color === 'rgb(248, 113, 113)' || /danger/.test(e.style.color)).map(e => e.innerText).join(' | ')`);
    await p.screenshot(T + `debug-${LANG}-forge.png`);
    await rec.stop();
    throw new Error('forge did not finish: ' + err + ' / ' + inline);
  }
  rec.mark('created_at');
  await p.waitFor('.sr-member-card__actions button', { timeout: 15000 });
  await sleep(1600);
  await p.click({ js: `document.querySelector('.sr-member-card__actions button')` }, { ringMs: 400 });
  rec.mark('sheet_open_at');
  await sleep(2600);
  await p.eval(`(() => { const d=document.querySelector('[role=dialog]'); if(!d) return; const sc=[d,...d.querySelectorAll('*')].find(e=>e.scrollHeight>e.clientHeight+40 && ['auto','scroll'].includes(getComputedStyle(e).overflowY)); if(sc) sc.dataset.trailerScroll='1'; })()`);
  if (await p.exists('[data-trailer-scroll]')) { await p.scrollBy(450, { ms: 1400, container: '[data-trailer-scroll]' }); await sleep(1400); await p.scrollBy(450, { ms: 1400, container: '[data-trailer-scroll]' }); }
  await sleep(2000);
  await rec.stop();
  const k = await token('kalliroi');
  const list = await must(api('/characters/', { token: k }));
  const ch = (Array.isArray(list) ? list : list.characters || []).find((c) => c.name === KAL.name);
  state.chars.kalliroi = ch?.id;
  fs.writeFileSync(T + `demo-state.${LANG}.json`, JSON.stringify(state, null, 2));
  save('shot05', rec, { guided_result: result, character_id: ch?.id, note: 'Guided -> forge -> sheet in one take; shot06 is the same file' }, ['shot06']);
}

// 07 play: ianthe writes, the Storyteller answers with a roll chip, stavros replies with a quote
const LADA_LINE = L('I slip into the alley behind the warehouse and keep to the shadows, trying to reach the back door before the buyer’s guards notice me.',
  'Γλιστράω στο στενό πίσω από την αποθήκη και μένω στις σκιές, προσπαθώντας να φτάσω στην πίσω πόρτα πριν με δουν οι φρουροί του αγοραστή.');
const STAV_REPLY = L('Careful, Kallergi. That courier works for me. If he sees you, the price doubles.',
  'Προσοχή, Καλλέργη. Αυτός ο κούριερ δουλεύει για μένα. Αν σε δει, η τιμή διπλασιάζεται.');
async function setHunger(charId, n) {
  const nyx = await token('nyx');
  const ch = await must(api(`/characters/${charId}`, { token: nyx }));
  const c = ch.character || ch; const wm = typeof c.wod_meta === 'string' ? JSON.parse(c.wod_meta) : c.wod_meta;
  if (wm.hunger !== n) await must(api(`/characters/${charId}`, { method: 'PUT', token: nyx, body: { wod_meta: { ...wm, hunger: n } } }));
}
async function shot07() {
  const { v5, v5Rooms, chars } = state;
  // The Storyteller (nyx) sets Ianthe's Hunger to 4 on her sheet, as an ST does between scenes
  await setHunger(chars.ianthe, 4);
  const ia = await ensureLoggedIn('ianthe');
  const st = await ensureLoggedIn('stavros');
  const base = await lastId(v5, v5Rooms.ladadika);
  for (let take = 1; take <= 6; take++) {
    await st.goto(`${BASE}/c/${v5}/${v5Rooms.ladadika}`, { waitMs: 2500 });
    await ia.goto(`${BASE}/c/${v5}/${v5Rooms.ladadika}`, { waitMs: 3000 });
    await activate(bc, ia);
    reseed(707);
    const rec = new Recorder(ia, FRAMES + '07');
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
    await sleep(500);
    const lastAi = `[...${AI_MSGS}].pop()`;
    const reply = await ia.eval(`(${lastAi}).innerText`);
    const chip = await ia.eval(`(() => { const c = [...document.querySelectorAll('.sr-rollreq__chip')].pop(); return c ? c.innerText : null; })()`);
    const chipOk = !!chip && /hunger/i.test(chip);
    takesLog(`shot07 take ${take}: chip=${JSON.stringify(chip)} wait=${aiWait.toFixed(1)}s reply=${JSON.stringify(reply.slice(0, 300))}`);
    log('shot07 take', take, 'chip', chip, 'reply', reply.slice(0, 160).replace(/\n/g, ' '));
    if (!chipOk) { await rec.stop(); await deleteAfter(v5, v5Rooms.ladadika, base); continue; }
    await sleep(3200);
    // second player
    await activate(bc, st);
    await st.waitFor('.sr-rollreq__chip', { timeout: 20000 }).catch(() => {});
    await sleep(500);
    await rec.start(st);
    rec.mark('switch_to_stavros_at');
    await sleep(900);
    await st.hover({ js: lastAi });
    await sleep(500);
    const replyBtn = { js: `(${lastAi}).closest('.sr-msg, .sr-card-row').querySelectorAll('.sr-msg-actions__bar button')[1] || (${lastAi}).parentElement.querySelectorAll('.sr-msg-actions__bar button')[1]` };
    if (!(await st.eval(`(() => { const b = ${replyBtn.js}; return !!b && b.getBoundingClientRect().width > 0 && getComputedStyle(b).visibility !== 'hidden'; })()`))) {
      await st.click({ js: `(${lastAi}).parentElement.querySelector('.sr-msg-actions__more') || (${lastAi}).querySelector('.sr-msg-actions__more')` }, { ringMs: 250 });
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
    save('shot07', rec, { ai_wait_cut_s: +aiWait.toFixed(1), roll_chip_present: true, roll_chip: chip, reply_excerpt: reply.slice(0, 400), takes: take });
    return;
  }
  throw new Error('no roll chip after 6 takes');
}

// 08 + 09: V5 roll from the chip (Hunger 4) until a BESTIAL FAILURE; then /ai explain on its card
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
async function rollTake(p, recName, { openDialog, prepare, outcomes, fallbackAfter = Infinity, fallbackOutcomes = [], maxTakes = 60, cid, lid, holdHit = 5500, after = null }) {
  for (let take = 1; take <= maxTakes; take++) {
    const ok = take > fallbackAfter ? [...outcomes, ...fallbackOutcomes] : outcomes;
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
    for (let i = 0; i < 400 && !settled; i++) { settled = await p.exists('.sr-diceov.is-settled'); if (!settled) await sleep(15); }
    rec.mark('result_at');
    // the server's roll record decides the outcome (same rule as the UI: dice/v5DiceDisplay.js)
    let roll = null;
    for (let i = 0; i < 100 && !roll; i++) {
      const rs = (await api(`/campaigns/${cid}/rolls?location_id=${lid}&limit=1`, { token: await token('nyx') })).data || [];
      if (rs[0] && rs[0].id > baseRoll) roll = rs[0]; else await sleep(100);
    }
    const outcome = classify(roll);
    const hit = ok.includes(outcome) ? outcome : null;
    const line = `${recName} take ${take}: ${hit ? 'HIT ' + hit : 'miss'} (${outcome}) dice=${JSON.stringify(roll && roll.results)} hunger=${JSON.stringify(roll?.modifiers?.hunger_dice)} normal=${JSON.stringify(roll?.modifiers?.normal_dice)} successes=${roll?.successes} difficulty=${roll?.difficulty}`;
    takesLog(line);
    log(line);
    if (hit && after) {
      const extra = await after(p, rec, { roll, take });
      await rec.stop();
      return { rec, take, outcome: hit, base, roll, ...extra };
    }
    await sleep(hit ? holdHit : 300);
    await rec.stop();
    if (hit) return { rec, take, outcome: hit, base, roll };
    await deleteAfter(cid, lid, base);
  }
  throw new Error('no hit after max takes');
}
const EXPLAIN = L('/ai explain', '/ai εξήγησε');
async function explainAfter(p, rec) {
  // the overlay hides 2.2 s after it settles; then the card in the room is hovered and replied to
  for (let i = 0; i < 80 && (await p.exists('.sr-diceov')); i++) await sleep(50);
  rec.mark('overlay_gone_at');
  const card = `[...document.querySelectorAll('.sr-card-row')].filter(r => r.querySelector('.sr-dicecard')).pop()`;
  await p.hover({ js: `(${card}).querySelector('.sr-dicecard')` });
  await sleep(350);
  const replyBtn = { js: `(${card}).querySelectorAll('.sr-msg-actions__bar button')[1]` };
  if (!(await p.eval(`(() => { const b = ${replyBtn.js}; return !!b && b.getBoundingClientRect().width > 0 && getComputedStyle(b).visibility !== 'hidden'; })()`))) {
    await p.click({ js: `(${card}).querySelector('.sr-msg-actions__more')` }, { ringMs: 200 });
  }
  rec.mark('explain_reply_click_at');
  await p.click(replyBtn, { ringMs: 300, after: 250 });
  rec.mark('explain_typing_at');
  await p.type(null, EXPLAIN, { cps: 16 });
  await sleep(250);
  // /ai output is posted as a collapsed "Storyteller diagnostics" card (messageModel.js: slash_assistant)
  const DIAG = `document.querySelectorAll('.sr-diag')`;
  const before = await p.eval(`${DIAG}.length`);
  rec.mark('explain_sent_at');
  await p.key('Enter');
  await sleep(250);
  rec.cutStart(0.35);
  const t0 = Date.now();
  for (let i = 0; i < 1200 && (await p.eval(`${DIAG}.length`)) <= before; i++) await sleep(50);
  rec.cutEnd();
  const wait = (Date.now() - t0) / 1000;
  if ((await p.eval(`${DIAG}.length`)) <= before) throw new Error('no explain card after 60 s');
  rec.mark('explain_at');
  const diag = `[...${DIAG}].pop()`;
  await sleep(700);
  rec.mark('explain_open_at');
  await p.click({ js: `(${diag}).querySelector('summary')` }, { ringMs: 450, after: 300 });
  const text = await p.eval(`(${diag}).innerText`);
  // bring the Result lines into view, slowly
  const resLine = { js: `[...(${diag}).querySelectorAll('p, li')].find(e => /^(Result|Αποτέλεσμα)\\s*:/.test(e.innerText.trim())) || (${diag})` };
  await p.eval(`(() => { const m = [...document.querySelectorAll('*')].find(e => e.scrollHeight > e.clientHeight + 40 && ['auto','scroll'].includes(getComputedStyle(e).overflowY) && e.querySelector('.sr-diag')); if (m) m.dataset.trailerChat = '1'; })()`);
  await sleep(500);
  const r = await p.rect(resLine);
  if (r && (await p.exists('[data-trailer-chat]')) && r.y > 330) await p.scrollBy(r.y - 330, { ms: 1100, container: '[data-trailer-chat]' });
  rec.mark('explain_result_at');
  await sleep(5000);
  // a Storyteller follow-up line (LLM, optional) may arrive; give it a moment, not forever
  const t1 = Date.now();
  const n0 = await aiCount(p);
  for (let i = 0; i < 100 && (await aiCount(p)) <= n0; i++) await sleep(100);
  const follow = (await aiCount(p)) > n0 ? await p.eval(`[...${AI_MSGS}].pop().innerText`) : null;
  await sleep(follow ? 2500 : 200);
  return { explain_wait_cut_s: +wait.toFixed(1), explain_text: text.slice(0, 1500), explain_followup: follow ? follow.slice(0, 600) : null, followup_wait_s: +((Date.now() - t1) / 1000).toFixed(1) };
}
async function shot08() {
  const { v5, v5Rooms, chars } = state;
  await setHunger(chars.ianthe, 4);
  const ia = await ensureLoggedIn('ianthe');
  await activate(bc, ia);
  const v = await rollTake(ia, '08v5', {
    cid: v5, lid: v5Rooms.ladadika, outcomes: ['Bestial failure'], fallbackAfter: Number(process.env.BESTIAL_TAKES || 30), fallbackOutcomes: ['Messy critical'],
    openDialog: async (p) => { await p.click({ js: `[...document.querySelectorAll('.sr-rollreq__chip')].filter(c => /\\b4 Hunger/i.test(c.innerText)).pop()` }, { ringMs: 450, block: 'center' }); },
    after: (p, rec) => explainAfter(p, rec),
  });
  const { rec, take, outcome, roll, base: _base, ...extra } = v;
  save('shot08_v5', rec, { outcome, takes: take, roll_results: roll?.results, hunger_dice: roll?.modifiers?.hunger_dice, normal_dice: roll?.modifiers?.normal_dice, successes: roll?.successes, difficulty: roll?.difficulty, ...extra });
}

// 10 Classic botch: Brother Anselm, Courage 3 dice at difficulty 8, the dice button
async function shot10() {
  const { cl, clRooms } = state;
  const st = await ensureLoggedIn('stavros');
  await activate(bc, st);
  const c = await rollTake(st, '10cl', {
    cid: cl, lid: clRooms.crypt, outcomes: ['Botch'],
    openDialog: async (p) => { await p.click({ js: `[...document.querySelectorAll('button.sr-btn.sr-btn--icon')].find(b => b.getBoundingClientRect().top > 980)` }, { ringMs: 400 }); },
    prepare: async (p) => {
      await p.type({ js: `document.querySelector('[role=dialog] input')` }, '3', { cps: 6, clear: true });
      await p.select({ js: `document.querySelector('[role=dialog] select')` }, '8');
      await p.type({ js: `document.querySelector('[role=dialog] textarea')` }, L('Courage: the skulls begin to whisper', 'Courage: τα κρανία αρχίζουν να ψιθυρίζουν'), { cps: 30 });
      await sleep(300);
    },
  });
  save('shot10_classic', c.rec, { outcome: c.outcome, takes: c.take, roll_results: c.roll?.results, successes: c.roll?.successes, difficulty: c.roll?.difficulty });
}

// 13 PDF export: kalliroi's play panel, "Export PDF"; the real downloaded file -> shot13_pdf (pdftoppm + zoompan)
async function shot13() {
  const { v5, v5Rooms } = state;
  const p = await ensureLoggedIn('kalliroi');
  const dl = T + `pdf/${LANG}/`;
  fs.rmSync(dl, { recursive: true, force: true }); fs.mkdirSync(dl, { recursive: true });
  await bc.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: path.resolve(dl), browserContextId: p.contextId, eventsEnabled: true });
  let done = null; const off = bc.on('Browser.downloadProgress', (e) => { if (e.state === 'completed') done = e; });
  await p.goto(`${BASE}/c/${v5}/${v5Rooms.elysium}`, { waitMs: 3000 });
  const exportBtn = { js: `[...document.querySelectorAll('.sr-member-card__actions button')].find(b => /PDF/.test(b.textContent))` };
  await p.waitFor(exportBtn, { timeout: 15000 });
  reseed(1313);
  const rec = new Recorder(p, FRAMES + '13');
  await rec.start(p);
  await sleep(1500);
  rec.mark('export_click_at');
  await p.click(exportBtn, { ringMs: 600 });
  for (let i = 0; i < 300 && !done; i++) await sleep(50);
  rec.mark('downloaded_at');
  await sleep(1500);
  await rec.stop();
  off();
  const files = fs.readdirSync(dl).filter((f) => f.endsWith('.pdf'));
  if (!files.length) throw new Error('no PDF downloaded');
  const pdf = dl + files[0];
  save('shot13', rec, { pdf: rel(pdf), pdf_bytes: fs.statSync(pdf).size });
  makePdfClip(pdf);
}
/**
 * The exported PDF as a clip (no recording): page 1 as a sheet on the dark table, pushed in to its
 * top (name, clan, attributes), then page 3 ("Reference": the clan, powers and ceremony with book and
 * page), drifting down. pdftoppm at 300 dpi so the zoom stays sharp; one still -> zoompan per page.
 */
function makePdfClip(pdf) {
  const dir = T + `pdf/${LANG}/pages/`;
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const r = spawnSync('nice', ['-n', '10', 'pdftoppm', '-r', '300', '-png', pdf, dir + 'p'], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error('pdftoppm failed');
  const pages = fs.readdirSync(dir).filter((f) => f.endsWith('.png')).sort();
  const info = spawnSync('pdfinfo', [pdf]).stdout.toString();
  log('pdf pages', pages.length, info.split('\n').filter((l) => /Pages|Page size/.test(l)).join('; '));
  const p1 = dir + pages[0], p3 = dir + (pages[2] || pages[pages.length - 1]);
  const out = `${OUT}shot13_pdf.mp4`;
  const fps = 60, D1 = 3.2, D3 = 3.0, N1 = Math.round(D1 * fps), N3 = Math.round(D3 * fps);
  // a 3840x2160 table with the page (height 2040) in the middle; zoompan reads (x, y) as the top-left of the window
  const table = (i) => `[${i}:v]scale=-2:2040:flags=lanczos,pad=3840:2160:(ow-iw)/2:60:color=0x0b0b14,format=yuv444p`;
  const ease = (n) => `(on/${n})*(on/${n})*(3-2*(on/${n}))`;
  // page 1: zoom 1.0 -> 2.1 onto the header and attributes (page-relative point 0.5, 0.2)
  const z1 = `1+1.1*${ease(N1)}`, cx1 = `1920`, cy1 = `(1080+(60+2040*0.21-1080)*${ease(N1)})`;
  // page 3: zoom 2.5 -> 2.62, the "Reference" page from the clan (0.27 of the page) drifting to the powers (0.40)
  const z3 = `2.5+0.12*(on/${N3})`, cx3 = `1920`, cy3 = `(60+2040*(0.27+0.13*${ease(N3)}))`;
  const zp = (z, cx, cy, n) => `zoompan=z='${z}':x='${cx}-iw/zoom/2':y='${cy}-ih/zoom/2':d=${n}:s=1920x1080:fps=${fps}`;
  const vf = `${table(0)},${zp(z1, cx1, cy1, N1)},format=yuv420p,setsar=1[a];${table(1)},${zp(z3, cx3, cy3, N3)},format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]`;
  const enc = spawnSync('nice', ['-n', '10', 'ffmpeg', '-y', '-loglevel', 'error', '-i', p1, '-i', p3,
    '-filter_complex', vf, '-map', '[v]', '-r', String(fps), '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-threads', '8', '-movflags', '+faststart', out], { stdio: 'inherit' });
  if (enc.status !== 0) throw new Error('pdf clip encode failed');
  shots.shot13_pdf = { path: rel(out), duration: D1 + D3, page1_at: 0.0, page3_at: D1, pages: pages.length, source_pdf: rel(pdf), note: 'made from the exported PDF (pdftoppm 300 dpi, zoompan), no recording', recorded_at: new Date().toISOString() };
  fs.writeFileSync(shotsFile, JSON.stringify(shots, null, 2));
  stills(out, 'shot13_pdf', { page1_at: 0, page3_at: D1 }, D1 + D3);
}
async function pdfClipOnly() {
  if (!shots.shot13?.pdf) throw new Error('no shot13 PDF yet: record shot 13 first');
  makePdfClip(path.join(ROOT, shots.shot13.pdf));
}

// 14 showcase: the atmosphere switch to Full first (lands on the 128.0 theme downbeat), glyphs, clan
// sigils with the Hecata hover, back to the hero for Subtle and Off, the Editions section
async function shot14() {
  const p = await page('anon');
  await p.goto(`${BASE}/showcase?lang=${LANG}`, { waitMs: 2500 });
  const atmo = (mode) => ({ js: `document.querySelector('input[name=sc-atmo][value=${mode}]').closest('label') || document.querySelector('input[name=sc-atmo][value=${mode}]')` });
  await p.eval(`(() => { const o = document.querySelector('input[name=sc-atmo][value=off]'); (o.closest('label') || o).click(); window.scrollTo(0, 0); })()`);
  await sleep(2500);
  reseed(1414);
  const rec = new Recorder(p, FRAMES + '14');
  await rec.start(p);
  await sleep(1200);
  rec.mark('atmosphere_full_at');
  await p.click(atmo('full'), { ringMs: 260, after: 0 });
  await sleep(3400);
  rec.mark('glyphs_at');
  await p.scrollTo('#sc-glyphs', { ms: 1300, offset: 40 });
  await sleep(700);
  await p.hover({ js: `[...document.querySelectorAll('button.sc-glyph')][5]` }).catch(() => {});
  await sleep(1200);
  const clanHead = { js: `[...document.querySelectorAll('#sc-glyphs h3')].find(e => /Clan sigils|clan|φατρ/i.test(e.textContent))` };
  rec.mark('clans_at');
  await p.scrollTo(clanHead, { ms: 1300, offset: 160 });
  await sleep(500);
  rec.mark('hecata_hover_at');
  await p.hover({ js: `[...document.querySelectorAll('button.sc-glyph')].find(b => /Hecata/.test(b.getAttribute('aria-label') || b.textContent))` }).catch(() => {});
  await sleep(1800);
  rec.mark('back_to_hero_at');
  await p.scrollBy(-(await p.eval('document.scrollingElement.scrollTop')), { ms: 1500 });
  await sleep(900);
  for (const [mode, ms] of [['subtle', 2000], ['off', 1900]]) {
    rec.mark(`atmosphere_${mode}_at`);
    await p.click(atmo(mode), { ringMs: 300 });
    await sleep(ms);
  }
  await p.click(atmo('full'), { ring: false, after: 0 });
  rec.mark('editions_scroll_at');
  await p.scrollTo('#sc-editions', { ms: 1200, offset: 30 });
  rec.mark('editions_at');
  await sleep(3000);
  await rec.stop();
  save('shot14', rec);
}

const order = [['04', shot04], ['05', shot05], ['07', shot07], ['08', shot08], ['10', shot10], ['13', shot13], ['14', shot14], ['pdfclip', pdfClipOnly]];
try {
  for (const [k, fn] of order) {
    if (!want(k)) continue;
    log('=== shot', k, LANG);
    await fn();
  }
} catch (e) {
  console.error('FAILED', e.stack || e);
  for (const [n, p] of Object.entries(pages)) await p.screenshot(T + `debug-${LANG}-${n}.png`).catch(() => {});
  process.exitCode = 1;
} finally {
  bc.close(); br.proc.kill();
}

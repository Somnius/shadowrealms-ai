// High-level page driver for the trailer recordings: human-ish typing, highlighted clicks,
// smooth scrolling, waiting for text/selectors, and a frame recorder on Page.startScreencast.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { CDP, sleep } from './cdp.mjs';

export { sleep };

// Deterministic pseudo-random (typing rhythm is the same every take)
let seed = 1234567;
export function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
export function reseed(s) { seed = s; }

const RING_CSS = `
#__trailer_ring{position:fixed;pointer-events:none;z-index:2147483647;border-radius:10px;
 box-shadow:0 0 0 2px rgba(224,72,72,.85),0 0 18px 4px rgba(200,40,40,.45);opacity:0;
 transition:opacity .18s ease, left .25s ease, top .25s ease, width .25s ease, height .25s ease;}
`;

export class Page {
  constructor(cdp, { sessionId, name } = {}) { this.c = cdp; this.sid = sessionId; this.name = name || 'page'; }
  send(m, p) { return this.c.send(m, p, this.sid); }

  async init(url) {
    for (const d of ['Page.enable', 'Runtime.enable', 'DOM.enable']) await this.send(d);
    await this.send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await this.send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => {
      const add = () => { if (document.getElementById('__trailer_css')) return; const s = document.createElement('style'); s.id='__trailer_css'; s.textContent=${JSON.stringify(RING_CSS)}; document.documentElement.appendChild(s);
        const r=document.createElement('div'); r.id='__trailer_ring'; document.documentElement.appendChild(r); };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
    })();` });
    if (url) await this.goto(url);
  }

  async eval(expr, { awaitPromise = true } = {}) {
    const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise });
    if (r.exceptionDetails) throw new Error('eval: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  }

  async goto(url, { waitMs = 600 } = {}) {
    const loaded = new Promise((res) => { const off = this.c.on('Page.loadEventFired', (p, s) => { if (!this.sid || s === this.sid) { off(); res(); } }); });
    await this.send('Page.navigate', { url });
    await Promise.race([loaded, sleep(15000)]);
    await sleep(waitMs);
    await this.eval(`(() => { if (!document.getElementById('__trailer_ring')) { const s=document.createElement('style'); s.id='__trailer_css'; s.textContent=${JSON.stringify(RING_CSS)}; document.documentElement.appendChild(s); const r=document.createElement('div'); r.id='__trailer_ring'; document.documentElement.appendChild(r);} })()`);
  }

  /** Client-side navigation through react-router (no reload). */
  async route(pathname, waitMs = 500) {
    await this.eval(`(() => { window.history.pushState({}, '', ${JSON.stringify(pathname)}); window.dispatchEvent(new PopStateEvent('popstate')); })()`);
    await sleep(waitMs);
  }

  // ---------- element finding ----------
  /** JS expression returning an element: css selector, or {text, sel} (visible element whose text matches). */
  static finder(target) {
    if (typeof target === 'string') return `document.querySelector(${JSON.stringify(target)})`;
    if (target.js) return `(${target.js})`;
    const { sel = 'button, a, [role=button], [role=tab], [role=option], [role=menuitem], [role=radio], label, summary', text = '', re = null, exact = false, nth = 0, within } = target;
    const root = within ? `(document.querySelector(${JSON.stringify(within)})||document)` : 'document';
    const test = re ? `new RegExp(${JSON.stringify(re)}).test(t)` : (exact ? `t===${JSON.stringify(text)}` : `t.includes(${JSON.stringify(text)})`);
    return `(() => { const norm = (s) => (s||'').replace(/\\s+/g,' ').trim();
      const els = [...${root}.querySelectorAll(${JSON.stringify(sel)})].filter((e) => { const r=e.getBoundingClientRect(); const cs=getComputedStyle(e); return r.width>0 && r.height>0 && cs.visibility!=='hidden' && cs.display!=='none'; });
      const m = els.filter((e) => { const t = norm(e.innerText || e.value || e.getAttribute('aria-label') || e.title || e.placeholder); return ${test}; });
      return m[${nth < 0 ? 'm.length' + nth : nth}] || null; })()`;
  }

  async exists(target) { return this.eval(`!!(${Page.finder(target)})`); }

  async waitFor(target, { timeout = 20000, poll = 100 } = {}) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      if (await this.exists(target).catch(() => false)) return true;
      await sleep(poll);
    }
    throw new Error(`[${this.name}] timeout waiting for ${JSON.stringify(target)}`);
  }

  async waitText(text, { timeout = 20000 } = {}) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      if (await this.eval(`document.body && document.body.innerText.includes(${JSON.stringify(text)})`)) return true;
      await sleep(150);
    }
    throw new Error(`[${this.name}] timeout waiting for text ${text}`);
  }

  async rect(target) {
    return this.eval(`(() => { const e = ${Page.finder(target)}; if (!e) return null; const r = e.getBoundingClientRect(); return {x:r.left,y:r.top,w:r.width,h:r.height}; })()`);
  }

  /** Smoothly bring an element into view (if needed) and wait for the scroll to settle. */
  async reveal(target, { block = 'center', margin = 80 } = {}) {
    const r = await this.rect(target);
    if (!r) throw new Error(`[${this.name}] not found: ${JSON.stringify(target)}`);
    if (r.y >= margin && r.y + r.h <= 1080 - margin) return r;
    await this.eval(`(${Page.finder(target)}).scrollIntoView({behavior:'smooth', block:${JSON.stringify(block)}})`);
    let last = null;
    for (let i = 0; i < 60; i++) { await sleep(60); const n = await this.rect(target); if (last && Math.abs(n.y - last.y) < 0.5) break; last = n; }
    return this.rect(target);
  }

  async ring(r, ms = 350) {
    if (!r) return;
    const pad = 6;
    await this.eval(`(() => { const g=document.getElementById('__trailer_ring'); if(!g) return; Object.assign(g.style,{left:${r.x - pad}+'px',top:${r.y - pad}+'px',width:${r.w + 2 * pad}+'px',height:${r.h + 2 * pad}+'px',opacity:'1'}); })()`);
    await sleep(ms);
  }
  async unring() { await this.eval(`(() => { const g=document.getElementById('__trailer_ring'); if(g) g.style.opacity='0'; })()`); }

  async mouse(type, x, y, extra = {}) {
    await this.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mousePressed' ? 1 : 0, clickCount: 1, ...extra });
  }

  /** Highlight then click the element's center with real mouse events. */
  async click(target, { ring = true, ringMs = 380, after = 250, block } = {}) {
    const r = await this.reveal(target, { block });
    const x = r.x + r.w / 2, y = r.y + r.h / 2;
    if (ring) await this.ring(r, ringMs);
    await this.mouse('mouseMoved', x, y);
    await sleep(40);
    await this.mouse('mousePressed', x, y);
    await sleep(70);
    await this.mouse('mouseReleased', x, y);
    if (ring) setTimeout(() => this.unring().catch(() => {}), 220);
    await sleep(after);
  }

  async hover(target) { const r = await this.reveal(target); await this.mouse('mouseMoved', r.x + r.w / 2, r.y + r.h / 2); }

  /** Focus an input (click) and type like a person. */
  async type(target, text, { cps = 14, jitter = 0.5, clear = false, ring = true } = {}) {
    if (target) await this.click(target, { ring, after: 120 });
    if (clear) await this.eval(`(() => { const e=document.activeElement; if(!e) return; const p = e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(p,'value').set.call(e,''); e.dispatchEvent(new Event('input',{bubbles:true})); })()`);
    const base = 1000 / cps;
    for (const ch of text) {
      if (ch === '\n') await this.key('Enter', { shift: true });
      else await this.send('Input.insertText', { text: ch });
      let d = base * (1 - jitter / 2 + rnd() * jitter);
      if (ch === ' ' && rnd() < 0.15) d += base * 1.5;
      if (/[.,!?;:·]/.test(ch)) d += base * 2;
      await sleep(d);
    }
  }

  async key(key, { shift = false } = {}) {
    const map = { Enter: { code: 'Enter', vk: 13, text: '\r' }, Tab: { code: 'Tab', vk: 9 }, Escape: { code: 'Escape', vk: 27 }, Backspace: { code: 'Backspace', vk: 8 } };
    const k = map[key];
    const mods = shift ? 8 : 0;
    await this.send('Input.dispatchKeyEvent', { type: k.text ? 'keyDown' : 'rawKeyDown', key, code: k.code, windowsVirtualKeyCode: k.vk, nativeVirtualKeyCode: k.vk, text: k.text, unmodifiedText: k.text, modifiers: mods });
    await this.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code: k.code, windowsVirtualKeyCode: k.vk, nativeVirtualKeyCode: k.vk, modifiers: mods });
  }

  /** Set a <select> (React-controlled) to the option whose value or text matches. */
  async select(target, want, { ring = true, ringMs = 450 } = {}) {
    const r = await this.reveal(target);
    if (ring) await this.ring(r, ringMs);
    const ok = await this.eval(`(() => { const e = ${Page.finder(target)}; const w=${JSON.stringify(want)};
      const o = [...e.options].find((o) => o.value === String(w)) || [...e.options].find((o) => o.text.trim() === String(w)) || [...e.options].find((o) => o.text.includes(String(w)));
      if (!o) return false; e.focus();
      Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(e, o.value);
      e.dispatchEvent(new Event('change',{bubbles:true})); return true; })()`);
    if (!ok) throw new Error(`[${this.name}] option ${want} not in ${JSON.stringify(target)}`);
    await sleep(200);
    if (ring) await this.unring();
  }

  /** Smooth scroll the page (or a scroll container) by dy px over ms. */
  async scrollBy(dy, { ms = 900, container = null } = {}) {
    await this.eval(`new Promise((res) => { const el = ${container ? `document.querySelector(${JSON.stringify(container)})` : 'document.scrollingElement'};
      const y0 = el.scrollTop, t0 = performance.now(), d=${dy}, dur=${ms};
      const ease = (t) => t<.5 ? 4*t*t*t : 1-Math.pow(-2*t+2,3)/2;
      const step = (now) => { const t = Math.min(1,(now-t0)/dur); el.scrollTop = y0 + d*ease(t); if (t<1) requestAnimationFrame(step); else res(); };
      requestAnimationFrame(step); })`);
  }
  async scrollTo(target, { ms = 900, container = null, offset = 120 } = {}) {
    const r = await this.rect(target);
    await this.scrollBy(r.y - offset, { ms, container });
  }

  async screenshot(file) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' });
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
  }

  /** Visible clickable texts, for exploring. */
  async listClickables() {
    return this.eval(`[...document.querySelectorAll('button, a, [role=button], [role=tab], input, select, textarea')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0}).map(e=>{const r=e.getBoundingClientRect(); return e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(e.className&&typeof e.className==='string'?'.'+e.className.split(' ').filter(Boolean).slice(0,2).join('.'):'')+' ['+((e.innerText||e.value||e.getAttribute('aria-label')||e.placeholder||'').replace(/\\s+/g,' ').trim().slice(0,60))+'] @'+Math.round(r.x)+','+Math.round(r.y)+' '+Math.round(r.width)+'x'+Math.round(r.height)})`);
  }
}

/**
 * Frame recorder on Page.startScreencast: JPEG frames with compositor timestamps go to a folder.
 * Segments (start/stop or switching page = a hard cut), cut ranges (e.g. waiting for the AI, keep
 * `keep` s of it) and named marks; render() builds a constant-60 fps H.264 clip from the real
 * frame timing (ffmpeg concat with per-frame durations, then fps=60).
 */
export class Recorder {
  constructor(page, dir, { quality = 92 } = {}) {
    this.p = page; this.dir = dir; this.q = quality; this.segs = []; this.marks = {}; this.running = false; this.n = 0;
    fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  }
  get seg() { return this.segs.at(-1); }
  async start(page = this.p) {
    if (this.running) await this.stop();
    this.p = page;
    const seg = { page: page.name, frames: [], cuts: [], startWall: Date.now() };
    this.segs.push(seg);
    this.off = page.c.on('Page.screencastFrame', (p, sid) => {
      if (sid !== page.sid) return;
      page.send('Page.screencastFrameAck', { sessionId: p.sessionId }).catch(() => {});
      if (!this.running || this.seg !== seg) return;
      const f = path.join(this.dir, `f${String(++this.n).padStart(6, '0')}.jpg`);
      fs.writeFileSync(f, Buffer.from(p.data, 'base64'));
      seg.frames.push({ f, ts: p.metadata.timestamp, wall: Date.now() });
    });
    this.running = true;
    await page.send('Page.startScreencast', { format: 'jpeg', quality: this.q, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
    await this.nudge();
    for (let i = 0; i < 50 && !seg.frames.length; i++) await sleep(20);
  }
  /** Force a repaint so a static page still sends a frame. */
  async nudge() { await this.p.eval(`(() => { const b = document.body; if (!b) return; b.style.outline = b.style.outline ? '' : '0px solid transparent'; })()`).catch(() => {}); }
  async stop() {
    if (!this.running) return;
    await this.nudge(); await sleep(50);
    this.seg.endWall = Date.now();
    this.running = false;
    await this.p.send('Page.stopScreencast').catch(() => {});
    this.off?.();
  }
  _ts(seg, wall) {
    const fr = seg.frames; if (!fr.length) return 0;
    let best = fr[0]; for (const f of fr) { if (f.wall <= wall) best = f; else break; }
    return best.ts + (wall - best.wall) / 1000;
  }
  mark(name) { this.marks[name] = { seg: this.segs.length - 1, wall: Date.now() }; }
  cutStart(keep = 0.8) { this.seg.cuts.push({ fromWall: Date.now(), keep }); }
  cutEnd() { const c = this.seg.cuts.at(-1); c.toWall = Date.now(); }

  render(out) {
    const items = []; let offset = 0; const segOffsets = []; const vtFns = [];
    const dtsAll = [];
    for (const [si, seg] of this.segs.entries()) {
      if (!seg.frames.length) { segOffsets.push(offset); vtFns.push(() => 0); continue; }
      const t0 = seg.frames[0].ts;
      const cuts = seg.cuts.filter((c) => c.toWall).map((c) => { const a = this._ts(seg, c.fromWall) + c.keep; const b = this._ts(seg, c.toWall); return b > a ? { a, b } : null; }).filter(Boolean);
      const vt = (ts) => { let r = ts - t0; for (const c of cuts) { if (ts >= c.b) r -= c.b - c.a; else if (ts > c.a) r -= ts - c.a; } return r; };
      const kept = seg.frames.filter((f) => !cuts.some((c) => f.ts > c.a && f.ts < c.b));
      const endTs = seg.endWall ? this._ts(seg, seg.endWall) : kept.at(-1).ts + 0.1;
      for (let i = 0; i < kept.length; i++) {
        const nxt = i + 1 < kept.length ? vt(kept[i + 1].ts) : vt(endTs);
        items.push({ f: kept[i].f, dur: Math.max(0, nxt - vt(kept[i].ts)) });
        if (i > 0) dtsAll.push(kept[i].ts - kept[i - 1].ts);
      }
      segOffsets.push(offset); vtFns.push(vt);
      offset += vt(endTs);
    }
    const marks = Object.fromEntries(Object.entries(this.marks).map(([k, m]) => {
      const seg = this.segs[m.seg]; return [k, +(segOffsets[m.seg] + Math.max(0, vtFns[m.seg](this._ts(seg, m.wall)))).toFixed(3)];
    }));
    const listFile = path.join(this.dir, 'list.txt');
    fs.writeFileSync(listFile, items.map((k) => `file '${k.f}'\nduration ${k.dur.toFixed(6)}`).join('\n') + `\nfile '${items.at(-1).f}'\n`);
    const active = dtsAll.filter((d) => d > 0 && d < 0.05);
    const fps = active.length ? active.length / active.reduce((s, d) => s + d, 0) : 0;
    const r = spawnSync('nice', ['-n', '10', 'ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-vf', 'fps=60,format=yuv420p', '-fps_mode', 'cfr', '-r', '60',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-profile:v', 'high', '-threads', '8', '-an', '-movflags', '+faststart', out], { stdio: 'inherit' });
    if (r.status !== 0) throw new Error('ffmpeg failed for ' + out);
    const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out]).stdout.toString().trim();
    return { duration: +(+probe).toFixed(3), marks, fps_measured: +fps.toFixed(1), frames: items.length };
  }
}

/** Open a page in a fresh browser context (own localStorage/cookies). */
export async function newContextPage(browserCdp, name) {
  const { browserContextId } = await browserCdp.send('Target.createBrowserContext', { disposeOnDetach: false });
  const { targetId } = await browserCdp.send('Target.createTarget', { url: 'about:blank', browserContextId, width: 1920, height: 1080 });
  const { sessionId } = await browserCdp.send('Target.attachToTarget', { targetId, flatten: true });
  const p = new Page(browserCdp, { sessionId, name });
  p.targetId = targetId; p.contextId = browserContextId;
  return p;
}
export async function activate(browserCdp, page) { await browserCdp.send('Target.activateTarget', { targetId: page.targetId }); await page.send('Page.bringToFront').catch(() => {}); }

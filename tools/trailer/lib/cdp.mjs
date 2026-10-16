// Minimal Chrome DevTools Protocol client + Chromium launcher (no npm deps; Node >= 22 WebSocket).
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import path from 'node:path';
import fs from 'node:fs';

export { sleep };

export class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.handlers = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : Buffer.from(ev.data).toString());
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject, method } = this.pending.get(msg.id); this.pending.delete(msg.id);
        if (msg.error) reject(new Error(`${method}: ${msg.error.message}`)); else resolve(msg.result);
      } else if (msg.method) {
        for (const h of this.handlers.get(msg.method) || []) h(msg.params, msg.sessionId);
      }
    });
  }
  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((res, rej) => { ws.addEventListener('open', res, { once: true }); ws.addEventListener('error', rej, { once: true }); });
    return new CDP(ws);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.id;
    const msg = { id, method, params }; if (sessionId) msg.sessionId = sessionId;
    this.ws.send(JSON.stringify(msg));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject, method }));
  }
  on(method, fn) { if (!this.handlers.has(method)) this.handlers.set(method, []); this.handlers.get(method).push(fn); return () => this.off(method, fn); }
  off(method, fn) { const a = this.handlers.get(method) || []; const i = a.indexOf(fn); if (i >= 0) a.splice(i, 1); }
  close() { try { this.ws.close(); } catch {} }
}

/** Launch headless Chromium at 1920x1080, DSF 1. Returns {proc, port, browserWs}. */
export async function launchChromium({ userDataDir, port = 9336, extraArgs = [], headless = true, lang = 'en-US' }) {
  // 9333 is a personal browser's debugging port on this machine: never start (or attach) there
  if (port === 9333) throw new Error('port 9333 is reserved for the personal browser; pick another');
  fs.mkdirSync(userDataDir, { recursive: true });
  const args = [
    `--remote-debugging-port=${port}`, `--user-data-dir=${userDataDir}`,
    ...(headless ? ['--headless=new'] : []),
    '--window-size=1920,1080', '--force-device-scale-factor=1', '--hide-scrollbars',
    '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-sync',
    '--disable-features=Translate,MediaRouter,OptimizationHints', '--disable-background-timer-throttling',
    '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows',
    '--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=vulkan', '--enable-features=Vulkan',
    `--lang=${lang}`, '--font-render-hinting=none',
    ...extraArgs, 'about:blank',
  ];
  const proc = spawn('nice', ['-n', '10', '/usr/bin/chromium', ...args], { stdio: ['ignore', 'ignore', 'pipe'] });
  let errLog = ''; proc.stderr.on('data', (d) => { errLog += d; if (errLog.length > 20000) errLog = errLog.slice(-10000); });
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) { const v = await r.json(); return { proc, port, browserWs: v.webSocketDebuggerUrl, errLog: () => errLog }; }
    } catch {}
    await sleep(100);
  }
  proc.kill(); throw new Error('chromium did not start: ' + errLog.slice(-2000));
}

/** Connect to the first page target (or create one). */
export async function connectPage(port) {
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  let page = list.find((t) => t.type === 'page');
  if (!page) page = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const c = await CDP.connect(page.webSocketDebuggerUrl);
  await c.send('Page.enable'); await c.send('Runtime.enable'); await c.send('DOM.enable');
  await c.send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  return c;
}

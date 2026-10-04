// Register the demo accounts (nyx admin, ianthe + stavros players) with random passwords.
// Passwords go to data/trailer/demo-accounts.json (mode 600). Usage: node register_accounts.mjs
import fs from 'node:fs';
import crypto from 'node:crypto';
import { api, must, T, saveAccounts } from './lib/api.mjs';
const codes = JSON.parse(fs.readFileSync(T + '.invite-codes.json', 'utf8'));
let acc = {};
try { acc = JSON.parse(fs.readFileSync(T + 'demo-accounts.json', 'utf8')); } catch {}
const pw = () => crypto.randomBytes(18).toString('base64url') + 'a9!';
for (const name of ['nyx', 'ianthe', 'stavros']) {
  if (acc[name]?.registered) continue;
  const password = acc[name]?.password || pw();
  acc[name] = { password, email: `${name}@demo.invalid` };
  saveAccounts(acc);
  const r = await api('/auth/register', { method: 'POST', body: { username: name, email: acc[name].email, password, invite_code: codes[name] } });
  if (!r.ok) throw new Error(`register ${name}: ${r.status} ${JSON.stringify(r.data)}`);
  acc[name].registered = true; acc[name].id = r.data.user?.id; acc[name].role = r.data.user?.role;
  saveAccounts(acc);
  console.log('registered', name, acc[name].role);
}

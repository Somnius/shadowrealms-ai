// Seed the trailer's demo stack through the app's API (no SQL):
//   chronicles + rooms, memberships, characters, earlier chat (Storyteller lines from the real model).
// Usage: node tools/trailer/setup_demo.mjs en|el      (accounts first: register_accounts.mjs)
// Writes data/trailer/demo-state.<lang>.json (ids for the recording script).
import fs from 'node:fs';
import { api, must, login, accounts, T } from './lib/api.mjs';

const LANG = process.argv[2] === 'el' ? 'el' : 'en';
const L = (en, el) => (LANG === 'el' ? el : en);

const tok = {};
for (const u of ['nyx', 'ianthe', 'stavros']) tok[u] = await login(u);
const ids = Object.fromEntries(Object.entries(accounts()).map(([k, v]) => [k, v.id]));

for (const u of ['nyx', 'ianthe', 'stavros']) {
  await must(api('/users/me/language', { method: 'PUT', token: tok[u], body: { ui_language: LANG } }));
}
// Site admin lets both players hold a locked character in more than one chronicle
for (const u of ['ianthe', 'stavros']) {
  await must(api(`/admin/users/${ids[u]}`, { method: 'PUT', token: tok.nyx, body: { allow_multi_campaign_play: true } }));
}

// ---------- chronicles ----------
const V5_NAME = L('Thessaloniki Requiem', 'Requiem της Θεσσαλονίκης');
const CL_NAME = L('Mistra in Ashes', 'Μυστράς στις στάχτες');
const V5_DESC = L(
  'Thessaloniki, tonight. The Camarilla holds the Rotunda as Elysium; the Anarchs drink in the old warehouses of Ladadika; the Nosferatu keep the Byzantine cisterns under the upper town. A Prince is missing and the harbour smells of fresh blood.',
  'Θεσσαλονίκη, απόψε. Η Camarilla κρατά τη Ροτόντα ως Elysium· οι Anarchs πίνουν στις παλιές αποθήκες στα Λαδάδικα· οι Nosferatu φυλάνε τις βυζαντινές στέρνες κάτω από την Άνω Πόλη. Ο Prince έχει χαθεί και το λιμάνι μυρίζει φρέσκο αίμα.'
);
const CL_DESC = L(
  'Mistra, 1460. The Despotate falls to the Ottomans; in the burning palace and beneath the Pantanassa monastery the Kindred of the Morea make their last bargains.',
  'Μυστράς, 1460. Το Δεσποτάτο πέφτει στους Οθωμανούς· στο φλεγόμενο παλάτι και κάτω από τη μονή της Παντάνασσας τα Kindred του Μοριά κλείνουν τις τελευταίες τους συμφωνίες.'
);

async function findOrCreateCampaign(name, description, edition) {
  const list = await must(api('/campaigns/', { token: tok.nyx }));
  const arr = Array.isArray(list) ? list : list.campaigns || [];
  const hit = arr.find((c) => c.name === name);
  if (hit) return hit.id;
  const d = await must(api('/campaigns/', { method: 'POST', token: tok.nyx, body: { name, description, game_system: 'vampire', rules_edition: edition } }));
  return d.campaign_id;
}
const v5 = await findOrCreateCampaign(V5_NAME, V5_DESC, 'v5');
const cl = await findOrCreateCampaign(CL_NAME, CL_DESC, 'classic');

async function rooms(cid, wanted) {
  const have = await must(api(`/campaigns/${cid}/locations`, { token: tok.nyx }));
  const arr = Array.isArray(have) ? have : have.locations || [];
  const out = {};
  for (const [key, name, description] of wanted) {
    let r = arr.find((x) => x.name === name);
    if (!r) r = await must(api(`/campaigns/${cid}/locations`, { method: 'POST', token: tok.nyx, body: { name, type: 'custom', description } }));
    out[key] = r.id;
  }
  const ooc = arr.find((x) => String(x.type).toLowerCase() === 'ooc') ||
    (await must(api(`/campaigns/${cid}/locations`, { token: tok.nyx }))).find?.((x) => String(x.type).toLowerCase() === 'ooc');
  out.ooc = ooc?.id;
  return out;
}
const v5Rooms = await rooms(v5, [
  ['elysium', L('Elysium: The Rotunda', 'Elysium: Η Ροτόντα'), L('The 4th-century Rotunda, neutral ground under the Camarilla. Candles, mosaics, old grudges.', 'Η Ροτόντα του 4ου αιώνα, ουδέτερο έδαφος της Camarilla. Κεριά, ψηφιδωτά, παλιές έχθρες.')],
  ['ladadika', L('Ladadika After Midnight', 'Λαδάδικα μετά τα μεσάνυχτα'), L('Narrow streets of old warehouses turned bars near the port. Wet cobblestones, neon, smugglers and Anarchs.', 'Στενά δρομάκια με παλιές αποθήκες που έγιναν μπαρ κοντά στο λιμάνι. Βρεγμένο λιθόστρωτο, νέον, λαθρέμποροι και Anarchs.')],
  ['cisterns', L('The Cisterns', 'Οι Στέρνες'), L('Byzantine cisterns under the upper town, Nosferatu territory. Dripping water, echoes, old secrets.', 'Βυζαντινές στέρνες κάτω από την Άνω Πόλη, περιοχή των Nosferatu. Νερό που στάζει, αντίλαλοι, παλιά μυστικά.')],
]);
const clRooms = await rooms(cl, [
  ['palace', L("The Despot's Palace", 'Το Παλάτι του Δεσπότη'), L('The palace of the Palaiologoi, half in flames. Courtiers flee; the Kindred stay.', 'Το παλάτι των Παλαιολόγων, μισό στις φλόγες. Οι αυλικοί φεύγουν· τα Kindred μένουν.')],
  ['crypt', L('Pantanassa Crypt', 'Η κρύπτη της Παντάνασσας'), L('A crypt under the Pantanassa monastery: bones, icons, a Tremere library hidden behind the ossuary.', 'Κρύπτη κάτω από τη μονή της Παντάνασσας: οστά, εικόνες, μια βιβλιοθήκη των Tremere κρυμμένη πίσω από το οστεοφυλάκιο.')],
]);

for (const [cid, users] of [[v5, ['ianthe', 'stavros']], [cl, ['stavros']]]) {
  for (const u of users) {
    const r = await api(`/campaigns/${cid}/members`, { method: 'POST', token: tok.nyx, body: { username: u } });
    if (!r.ok && r.status !== 409 && !/already/i.test(JSON.stringify(r.data))) throw new Error(`member ${u}: ${JSON.stringify(r.data)}`);
  }
}

// ---------- characters ----------
const V5_SKILLS = {
  physical: ['athletics', 'brawl', 'craft', 'drive', 'firearms', 'larceny', 'melee', 'stealth', 'survival'],
  social: ['animal_ken', 'etiquette', 'insight', 'intimidation', 'leadership', 'performance', 'persuasion', 'streetwise', 'subterfuge'],
  mental: ['academics', 'awareness', 'finance', 'investigation', 'medicine', 'occult', 'politics', 'science', 'technology'],
};
/** Same storage shape as the forge's buildV5Payload (frontend/src/characterSheet/v5/validation.js). */
function v5Payload(c) {
  const skills = {};
  for (const [cat, keys] of Object.entries(V5_SKILLS)) skills[cat] = Object.fromEntries(keys.map((k) => [k, c.skills[k] || 0]));
  skills.specialties = c.specialties; skills.distribution = c.distribution;
  const advantages = c.advantages; const flaws = c.flaws;
  return {
    name: c.name, system_type: 'vampire', attributes: c.attributes, skills,
    merits_flaws: { entries: [...advantages.map((a) => ({ name: a.name, points: a.dots, note: a.kind === 'predator' ? 'predator type' : a.kind })), ...flaws.map((f) => ({ name: f.name, points: -f.dots, note: f.kind === 'predator' ? 'predator type' : 'flaw' }))] },
    wod_meta: {
      edition: 'v5', concept: c.concept, clan: c.clan, generation: 13, age: 'neonate', sire: c.sire || '', predator_type: c.predator,
      ambition: c.ambition, desire: c.desire, hunger: 1, humanity: c.humanity ?? 7, stains: 0, blood_potency: 1,
      health: { max: c.attributes.stamina + 3, superficial: 0, aggravated: 0 },
      willpower: { max: c.attributes.composure + c.attributes.resolve, superficial: 0, aggravated: 0 },
      disciplines: c.disciplines, touchstones: c.touchstones, chronicle_tenets: '', advantages, flaws,
    },
    background: c.background, sheet_locked: true, is_active: true,
  };
}
const IANTHE = {
  name: L('Ianthe Kallergi', 'Ιάνθη Καλλέργη'), clan: 'Toreador', predator: 'Siren',
  concept: L('Gallery owner who never sleeps', 'Γκαλερίστα που δεν κοιμάται ποτέ'),
  ambition: L('Own the city’s taste', 'Να ορίζει το γούστο της πόλης'), desire: L('Find out who bought the stolen icon', 'Να μάθει ποιος αγόρασε τη χαμένη εικόνα'),
  attributes: { strength: 1, dexterity: 3, stamina: 2, charisma: 4, manipulation: 3, composure: 2, intelligence: 2, wits: 3, resolve: 2 },
  distribution: 'balanced',
  skills: { persuasion: 3, etiquette: 3, insight: 3, stealth: 2, subterfuge: 2, awareness: 2, finance: 2, streetwise: 2, athletics: 1, drive: 1, larceny: 1, intimidation: 1, investigation: 1, occult: 1, politics: 1 },
  specialties: [{ skill: 'etiquette', name: L('Art collectors', 'Συλλέκτες τέχνης') }, { skill: 'persuasion', name: 'Seduction', source: 'predator' }],
  disciplines: [{ name: 'Presence', level: 3, powers: [] }, { name: 'Auspex', level: 1, powers: [] }],
  advantages: [{ name: 'Resources', dots: 3, kind: 'background' }, { name: 'Haven', dots: 2, kind: 'background' }, { name: 'Contacts', dots: 2, kind: 'background' }, { name: 'Looks: Beautiful', dots: 2, kind: 'predator' }],
  flaws: [{ name: 'Prey Exclusion (artists)', dots: 1, kind: 'flaw' }, { name: 'Enemy (spurned lover or jealous partner)', dots: 1, kind: 'predator' }],
  touchstones: [{ name: L('Daphne, her gallery assistant', 'Η Δάφνη, η βοηθός της στη γκαλερί'), conviction: L('Never destroy a work of art', 'Ποτέ μην καταστρέψεις έργο τέχνης') }],
  background: L('Ianthe runs a gallery on Proxenou Koromila and has not seen a sunrise since 1998.', 'Η Ιάνθη έχει γκαλερί στην Προξένου Κορομηλά και δεν έχει δει ανατολή από το 1998.'),
};
const STAVROS = {
  name: L('Stavros Morou', 'Σταύρος Μώρου'), clan: 'Nosferatu', predator: 'Sandman',
  concept: L('Information broker under the city', 'Μεσίτης πληροφοριών κάτω από την πόλη'),
  ambition: L('Know every secret in Thessaloniki', 'Να ξέρει κάθε μυστικό της Θεσσαλονίκης'), desire: L('Sell the Prince’s location twice', 'Να πουλήσει δύο φορές το πού βρίσκεται ο Prince'),
  attributes: { strength: 2, dexterity: 3, stamina: 2, charisma: 1, manipulation: 3, composure: 2, intelligence: 4, wits: 3, resolve: 2 },
  distribution: 'balanced',
  skills: { investigation: 3, stealth: 3, technology: 3, larceny: 2, streetwise: 2, subterfuge: 2, awareness: 2, insight: 2, brawl: 1, athletics: 1, intimidation: 1, occult: 1, politics: 1, finance: 1, survival: 1 },
  specialties: [{ skill: 'technology', name: L('Surveillance', 'Παρακολουθήσεις') }, { skill: 'stealth', name: 'Break-in', source: 'predator' }],
  disciplines: [{ name: 'Obfuscate', level: 3, powers: [] }, { name: 'Animalism', level: 1, powers: [] }],
  advantages: [{ name: 'Contacts', dots: 3, kind: 'background' }, { name: 'Haven', dots: 2, kind: 'background' }, { name: 'Mask', dots: 2, kind: 'background' }, { name: 'Resources', dots: 1, kind: 'predator' }],
  flaws: [{ name: 'Obvious Predator', dots: 2, kind: 'flaw' }],
  touchstones: [{ name: L('Eleni, the night-shift nurse at AHEPA', 'Η Ελένη, νοσηλεύτρια νυχτερινής βάρδιας στο ΑΧΕΠΑ'), conviction: L('Never sell out a friend', 'Ποτέ μην πουλήσεις φίλο') }],
  background: L('Stavros sells what he hears in the cisterns; the rats bring him the rest.', 'Ο Σταύρος πουλά ό,τι ακούει στις στέρνες· τα υπόλοιπα του τα φέρνουν οι αρουραίοι.'),
};
const ANSELM = {
  name: L('Brother Anselm', 'Αδελφός Άνσελμος'), system_type: 'vampire',
  attributes: { strength: 2, dexterity: 2, stamina: 2, charisma: 2, manipulation: 3, appearance: 3, perception: 3, intelligence: 4, wits: 3 },
  skills: {
    talents: { alertness: 2, athletics: 0, brawl: 0, dodge: 0, empathy: 1, expression: 1, intimidation: 0, leadership: 0, streetwise: 0, subterfuge: 1 },
    skills: { animal_ken: 0, crafts: 2, drive: 0, etiquette: 2, firearms: 0, melee: 1, performance: 0, security: 0, stealth: 2, survival: 2 },
    knowledges: { academics: 3, computer: 0, finance: 0, investigation: 2, law: 0, linguistics: 3, medicine: 1, occult: 4, politics: 0, science: 0 },
    allocation: { primary: 'knowledges', pools: { talents: 5, skills: 9, knowledges: 13 } }, notes: '',
  },
  merits_flaws: { entries: [] },
  wod_meta: {
    concept: L('Scholar-monk of Mistra', 'Λόγιος μοναχός του Μυστρά'), nature: 'Pedagogue', demeanor: 'Penitent', clan: 'Tremere', generation: '12',
    humanity: 7, willpower: 3, virtues: { conscience: 3, self_control: 4, courage: 3 },
    disciplines: [{ name: 'Thaumaturgy', dots: 2 }, { name: 'Auspex', dots: 1 }],
    backgrounds: [{ name: 'Mentor', dots: 2 }, { name: 'Resources', dots: 1 }, { name: 'Generation', dots: 1 }, { name: 'Status', dots: 1 }],
  },
  background: L('A Tremere copyist who hid the chantry’s books under the Pantanassa when the city began to burn.', 'Ένας Tremere αντιγραφέας που έκρυψε τα βιβλία του chantry κάτω από την Παντάνασσα όταν η πόλη άρχισε να καίγεται.'),
  sheet_locked: true, is_active: true,
};

async function ensureChar(user, cid, body) {
  const list = await must(api('/characters/', { token: tok[user] }));
  const arr = Array.isArray(list) ? list : list.characters || [];
  const hit = arr.find((c) => c.name === body.name && Number(c.campaign_id) === Number(cid));
  if (hit) return hit.id;
  const d = await must(api('/characters/', { method: 'POST', token: tok[user], body: { ...body, campaign_id: cid } }));
  return d.character_id;
}
const chars = {
  ianthe: await ensureChar('ianthe', v5, v5Payload(IANTHE)),
  stavros: await ensureChar('stavros', v5, v5Payload(STAVROS)),
  anselm: await ensureChar('stavros', cl, ANSELM),
};

// ---------- earlier chat ----------
async function msgs(cid, lid, token) {
  const d = await must(api(`/campaigns/${cid}/locations/${lid}`, { token }));
  return d.messages || d.data || d;
}
async function say(user, cid, lid, content, { asChar = null, ooc = false, replyTo = null } = {}) {
  const body = { content, message_type: ooc ? 'ooc' : 'ic', role: 'user', speak_as: asChar ? 'character' : 'player' };
  if (asChar) body.character_id = asChar;
  if (replyTo) body.reply_to_id = replyTo;
  const d = await must(api(`/campaigns/${cid}/locations/${lid}`, { method: 'POST', token: tok[user], body }));
  return d.data;
}
/** Ask the real Storyteller (as the app does after a player's line) and save its reply. */
async function storyteller(user, cid, lid, message, roomType = 'custom') {
  const t0 = Date.now();
  const ai = await api('/ai/chat', { method: 'POST', token: tok[user], body: { message, campaign_id: cid, location: lid, location_type: roomType } });
  if (!ai.ok) throw new Error('ai/chat ' + ai.status + ' ' + JSON.stringify(ai.data).slice(0, 300));
  const reply = String(ai.data.response ?? ai.data.message ?? '').trim();
  console.log(`  storyteller (${((Date.now() - t0) / 1000).toFixed(1)} s):`, reply.slice(0, 160).replace(/\n/g, ' '));
  if (!reply) return null;
  const d = await must(api(`/campaigns/${cid}/locations/${lid}`, { method: 'POST', token: tok[user], body: { content: reply, message_type: 'ic', role: 'assistant' } }));
  return d.data;
}

const seeded = (cid, lid) => msgs(cid, lid, tok.nyx).then((m) => (Array.isArray(m) ? m.length : 0));

if (!(await seeded(v5, v5Rooms.elysium))) {
  console.log('seeding Elysium');
  await say('nyx', v5, v5Rooms.elysium, L('*The Rotunda is lit by a hundred candles. The Harpies whisper under the mosaics: the Prince has not been seen for three nights.*', '*Η Ροτόντα φωτίζεται από εκατό κεριά. Οι Harpies ψιθυρίζουν κάτω από τα ψηφιδωτά: τον Prince δεν τον έχει δει κανείς εδώ και τρεις νύχτες.*'));
  const l1 = L('I glide past the Harpies with a glass I will never drink from and ask, sweetly, who benefits if the Prince stays gone.', 'Περνάω δίπλα από τις Harpies με ένα ποτήρι που δεν θα πιω ποτέ και ρωτάω γλυκά ποιος κερδίζει αν ο Prince δεν γυρίσει.');
  await say('ianthe', v5, v5Rooms.elysium, l1, { asChar: chars.ianthe });
  await storyteller('ianthe', v5, v5Rooms.elysium, l1);
}
if (!(await seeded(v5, v5Rooms.ladadika))) {
  console.log('seeding Ladadika');
  await say('stavros', v5, v5Rooms.ladadika, L('*From the shadow of a shuttered ouzeri, a voice:* You are late, Kallergi. The buyer is already inside.', '*Από τη σκιά ενός κλειστού ουζερί, μια φωνή:* Άργησες, Καλλέργη. Ο αγοραστής είναι ήδη μέσα.'), { asChar: chars.stavros });
  const l2 = L('Then he can wait. Tell me which door, Stavros, and what it costs me.', 'Τότε ας περιμένει. Πες μου ποια πόρτα, Σταύρο, και πόσο θα μου κοστίσει.');
  await say('ianthe', v5, v5Rooms.ladadika, l2, { asChar: chars.ianthe });
}
if (!(await seeded(v5, v5Rooms.cisterns))) {
  console.log('seeding Cisterns');
  await say('stavros', v5, v5Rooms.cisterns, L('*Water drips from the vaults. Stavros counts the rats that came back tonight: eleven. One is missing.*', '*Νερό στάζει από τους θόλους. Ο Σταύρος μετρά τους αρουραίους που γύρισαν απόψε: έντεκα. Λείπει ένας.*'), { asChar: chars.stavros });
}
if (v5Rooms.ooc && !(await seeded(v5, v5Rooms.ooc))) {
  console.log('seeding OOC');
  await say('nyx', v5, v5Rooms.ooc, L('Next session Thursday 21:00. Bring your Hunger.', 'Επόμενη συνεδρία Πέμπτη 21:00. Φέρτε και το Hunger σας.'), { ooc: true });
  await say('stavros', v5, v5Rooms.ooc, L('I’ll be there, might be 10 min late.', 'Θα είμαι εκεί, ίσως αργήσω 10 λεπτά.'), { ooc: true });
}
if (!(await seeded(cl, clRooms.palace))) {
  console.log('seeding Palace');
  await say('nyx', cl, clRooms.palace, L('*Smoke fills the great hall. Through the windows, the Ottoman fires ring the hill of Mistra.*', '*Καπνός γεμίζει τη μεγάλη αίθουσα. Από τα παράθυρα, οι φωτιές των Οθωμανών ζώνουν τον λόφο του Μυστρά.*'));
}
if (!(await seeded(cl, clRooms.crypt))) {
  console.log('seeding Crypt');
  const l = L('I lift the lamp to the ossuary wall and look for the mark of the chantry behind the skulls.', 'Σηκώνω το λυχνάρι στον τοίχο του οστεοφυλακίου και ψάχνω το σημάδι του chantry πίσω από τα κρανία.');
  await say('stavros', cl, clRooms.crypt, l, { asChar: chars.anselm });
  await storyteller('stavros', cl, clRooms.crypt, l);
}

const state = { lang: LANG, v5, cl, v5Rooms, clRooms, chars, users: ids, names: { v5: V5_NAME, cl: CL_NAME, ianthe: IANTHE.name, stavros: STAVROS.name, anselm: ANSELM.name } };
fs.writeFileSync(T + `demo-state.${LANG}.json`, JSON.stringify(state, null, 2));
console.log(JSON.stringify(state, null, 1));

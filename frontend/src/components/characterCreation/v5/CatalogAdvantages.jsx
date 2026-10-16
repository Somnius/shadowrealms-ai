/**
 * The Advantages step with the V5 catalog: Backgrounds, Merits and Flaws from dropdowns (grouped as
 * in the books, filtered for the clan), a dots picker bounded by the printed rating, a note and the
 * description; loresheets with their five levels; thin-blood Merits and Flaws; the clan's own Flaws
 * (Caitiff). A "Custom" row keeps anything the catalog lacks possible, for the Storyteller to approve.
 * Only entries from the chronicle's books are offered; one already chosen stays (the check says why).
 */
import { THIN_BLOOD, V5_THIN_BLOOD_MERITS } from '../../../characterSheet/v5/constants';
import {
  advantageDotChoices,
  advantageOptions,
  advantageUnrated,
  clanFlaws,
  clanInfo,
  loresheetLevelAllowed,
  loresheetOptions,
  resolvePredatorGrants,
  thinBloodOptions,
} from '../../../characterSheet/v5/validation';
import {
  advantageEntries,
  findAdvantage,
  findLoresheet,
  loresheetEntries,
  optionName,
  sharedNames,
} from '../../../characterSheet/v5/rulesData';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { newAdvRow, newLoreRow } from './useV5ForgeState';
import { CatalogNote, addButtonStyle, inputStyle, labelStyle, noteStyle, smallButtonStyle, useForge } from './forgeUi';

const dots = (n) => '●'.repeat(Math.max(0, n));
/** "1–6", "2/3", "2": the ratings of an entry, for its option label. */
const ratingLabel = (choices) => {
  if (!choices.length) return '';
  if (choices.length === 1) return String(choices[0]);
  const contiguous = choices.every((v, i) => !i || v === choices[i - 1] + 1);
  return contiguous ? `${choices[0]}–${choices[choices.length - 1]}` : choices.join('/');
};

// Game terms: English in both languages, but through t() so a locale can say otherwise.
const KIND_LABEL = {
  background: () => t('wizard:v5.kindBackground', 'Background'),
  merit: () => t('wizard:v5.kindMerit', 'Merit'),
  flaw: () => t('wizard:v5.kindFlaw', 'Flaw'),
  loresheet: () => t('wizard:v5.kindLoresheet', 'Loresheet'),
};
const sectionStyle = { marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--sr-night-700)' };
const headingStyle = { ...labelStyle, fontSize: '14px', fontFamily: 'var(--sr-font-display)', marginBottom: '8px' };

/** <optgroup>s of entries by their book group, keeping the catalog order. Two entries of one name
 * (Succubus Club's and the Ashfinders' Influencer) show their book. */
function GroupedOptions({ entries, takenIds, current }) {
  const shared = sharedNames(entries);
  const groups = [];
  entries.forEach((e) => {
    let g = groups.find((x) => x.name === e.group);
    if (!g) groups.push((g = { name: e.group, entries: [] }));
    g.entries.push(e);
  });
  return groups.map((g) => (
    <optgroup key={g.name} label={g.name}>
      {g.entries.map((e) => {
        const r = advantageUnrated(e) ? '?' : ratingLabel(advantageDotChoices(e));
        return (
          <option key={e.id} value={e.id} disabled={e.id !== current && takenIds(e)}>
            {optionName(e, shared)}
            {r ? ` (${r})` : ''}
          </option>
        );
      })}
    </optgroup>
  ));
}

/** One Background, Merit or Flaw row. `fixedIds`: the clan's and the predator type's entries. */
function AdvRow({ row, index, rows, setRows, clan, settings, fixedIds }) {
  const label = t('wizard:v5.advRowLabel', '{{kind}} {{n}}', { kind: KIND_LABEL[row.kind](), n: index + 1 });
  const set = (patch) => setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, ...patch } : r)));
  const options = advantageOptions(clan, row.kind, settings);
  // By id, or by name when the catalog doesn't know the id (then it shows as a custom row).
  const entry = row.id && row.id !== 'custom' ? findAdvantage({ id: row.id, name: row.name }, row.kind) : null;
  const custom = row.id === 'custom' || Boolean(row.id && !entry && String(row.name || '').trim());
  // Not offered any more (the clan changed, or its book isn't the chronicle's): kept visible so its error makes sense.
  const stray = entry && !options.some((o) => o.id === entry.id) ? entry : null;
  // A non-repeatable entry once; a repeatable one up to its max_instances. The rows the clan and
  // the predator type give count too (a Bagger isn't offered Iron Gullet again); Enemies and Dark
  // Secret are repeatable, so a player's own one can sit beside the predator type's.
  const taken = (e) => {
    const n = rows.filter((r) => r.id === e.id).length + fixedIds.filter((id) => id === e.id).length;
    return e.repeatable ? Boolean(e.max_instances && n >= e.max_instances) : n >= 1;
  };
  const choices = entry ? advantageDotChoices(entry) : [];
  const level = entry ? (entry.levels || []).find((l) => l.dots === Number(row.dots)) : null;
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <select
          aria-label={label}
          value={entry ? entry.id : custom ? 'custom' : row.id}
          onChange={(e) => {
            const id = e.target.value;
            const next = advantageEntries().find((a) => a.id === id);
            const first = next ? advantageDotChoices(next)[0] : null;
            // the name is kept with the id, so the row survives an id the catalog later renames
            set({ id, name: next ? next.name : id === 'custom' ? '' : row.name, dots: id === 'custom' ? 1 : first || 0 });
          }}
          style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
        >
          <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
          {stray ? <option value={stray.id}>{stray.name}</option> : null}
          <GroupedOptions entries={options} takenIds={taken} current={entry ? entry.id : row.id} />
          <option value="custom">{t('wizard:v5.advCustom', 'Custom (Storyteller approval)…')}</option>
        </select>
        {custom ? (
          <>
            <input
              value={row.name}
              aria-label={t('wizard:v5.advCustomName', '{{label}} name', { label })}
              placeholder={t('wizard:v5.advCustomPlaceholder', 'Name, as in your book')}
              maxLength={60}
              onChange={(e) => set({ name: e.target.value })}
              style={{ ...inputStyle, flex: '2 1 160px', width: 'auto', padding: '8px' }}
            />
            <select
              aria-label={t('wizard:v5.advDots', '{{name}} dots', { name: row.name || label })}
              value={row.dots}
              onChange={(e) => set({ dots: Number(e.target.value) })}
              style={{ ...inputStyle, width: '96px', padding: '8px' }}
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {dots(n)}
                </option>
              ))}
            </select>
          </>
        ) : null}
        {entry && choices.length > 1 ? (
          <select
            aria-label={t('wizard:v5.advDots', '{{name}} dots', { name: entry.name })}
            value={row.dots}
            onChange={(e) => set({ dots: Number(e.target.value) })}
            style={{ ...inputStyle, width: '110px', padding: '8px' }}
          >
            {choices.includes(Number(row.dots)) ? null : <option value={row.dots}>{dots(row.dots) || '–'}</option>}
            {choices.map((n) => (
              <option key={n} value={n}>
                {dots(n)}
              </option>
            ))}
          </select>
        ) : entry && choices.length === 1 ? (
          <span
            role="img"
            aria-label={t('wizard:v5.advFixedDots', { one: '{{name}}: {{count}} dot', other: '{{name}}: {{count}} dots' }, { name: entry.name, count: choices[0] })}
            style={{ color: 'var(--sr-blood-400)', minWidth: '60px' }}
          >
            {dots(choices[0])}
          </span>
        ) : null}
        {entry || custom ? (
          <input
            value={row.note}
            aria-label={t('wizard:v5.advNote', '{{label}} note', { label })}
            placeholder={t('wizard:merits.note', 'Note (optional)')}
            maxLength={80}
            onChange={(e) => set({ note: e.target.value })}
            style={{ ...inputStyle, flex: '1 1 140px', width: 'auto', padding: '8px' }}
          />
        ) : null}
        <button
          type="button"
          aria-label={t('wizard:v5.advRemove', 'Remove {{label}}', { label })}
          onClick={() => setRows((prev) => prev.filter((r) => r.key !== row.key))}
          style={smallButtonStyle}
        >
          ×
        </button>
      </div>
      {level ? (
        <div style={{ color: 'var(--sr-gold-400)', fontSize: '12px', marginTop: '4px' }}>
          {dots(level.dots)} {level.name}
        </div>
      ) : null}
      {advantageUnrated(entry) ? (
        <div style={{ color: 'var(--sr-gold-400)', fontSize: '12px', marginTop: '4px' }}>
          {t('wizard:v5.grantNoRating', 'the book prints no rating: ask your Storyteller')}
        </div>
      ) : null}
      {entry?.requires ? (
        <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginTop: '4px' }}>
          {t('wizard:v5.advRequires', 'Needs: {{req}}', { req: entry.requires })}
        </div>
      ) : null}
      <CatalogNote entry={entry} />
      {custom ? (
        <p style={{ ...noteStyle, fontSize: '12px', margin: '4px 0 0' }}>
          {t('wizard:v5.advCustomHint', 'Not in the catalog: your Storyteller has to approve it.')}
        </p>
      ) : null}
    </div>
  );
}

/** Backgrounds, Merits or Flaws: the rows of one kind and the add button. */
function AdvSection({ kind, title, children }) {
  const f = useForge();
  const rows = f.advRows.filter((r) => r.kind === kind);
  const pred = resolvePredatorGrants(f.sheet);
  const fixedIds = [...clanFlaws({ clan: f.clan }), ...pred.advantages, ...pred.flaws].map((r) => r.id).filter(Boolean);
  return (
    <div style={sectionStyle} data-adv-section={kind}>
      <div style={headingStyle}>{title}</div>
      {children}
      {rows.map((r, i) => (
        <AdvRow key={r.key} row={r} index={i} rows={rows} setRows={f.setAdvRows} clan={f.clan} settings={f.settings} fixedIds={fixedIds} />
      ))}
      <button type="button" onClick={() => f.setAdvRows((prev) => [...prev, newAdvRow(kind)])} style={addButtonStyle}>
        {t('wizard:v5.advAdd', '+ Add {{kind}}', { kind: KIND_LABEL[kind]() })}
      </button>
    </div>
  );
}

/** One loresheet: the sheet, then the levels taken (each its own benefit, its number in dots). */
function LoreRow({ row, index }) {
  const f = useForge();
  const label = t('wizard:v5.advRowLabel', '{{kind}} {{n}}', { kind: KIND_LABEL.loresheet(), n: index + 1 });
  const set = (patch) => f.setLoreRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, ...patch } : r)));
  const sheet = row.id ? findLoresheet({ id: row.id, name: row.name }) : null;
  const offered = loresheetOptions(f.sheet, f.settings);
  const shared = sharedNames(loresheetEntries());
  const takenElsewhere = f.loreRows.filter((r) => r.key !== row.key).map((r) => r.id);
  const total = row.levels.reduce((s, n) => s + n, 0);
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <select
          aria-label={label}
          value={sheet ? sheet.id : row.id}
          onChange={(e) => {
            const next = loresheetEntries().find((l) => l.id === e.target.value);
            set({ id: e.target.value, name: next ? next.name : '', levels: [] });
          }}
          style={{ ...inputStyle, flex: '2 1 260px', width: 'auto', padding: '8px' }}
        >
          <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
          {sheet && !offered.includes(sheet) ? <option value={sheet.id}>{optionName(sheet, shared)}</option> : null}
          {offered.map((l) => (
            <option key={l.id} value={l.id} disabled={takenElsewhere.includes(l.id)}>
              {optionName(l, shared)}
              {l.restriction ? ` (${l.restriction})` : ''}
            </option>
          ))}
        </select>
        {sheet ? (
          <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
            {t('wizard:v5.loreDots', { one: '{{count}} dot', other: '{{count}} dots' }, { count: total })}
          </span>
        ) : null}
        <button
          type="button"
          aria-label={t('wizard:v5.advRemove', 'Remove {{label}}', { label })}
          onClick={() => f.setLoreRows((prev) => prev.filter((r) => r.key !== row.key))}
          style={smallButtonStyle}
        >
          ×
        </button>
      </div>
      <CatalogNote entry={sheet} />
      {sheet && sheet.levels.some((lv) => !lv.name) ? (
        <p style={{ ...noteStyle, fontSize: '12px', margin: '4px 0 0' }}>
          {t('wizard:v5.loreNamesUnknown', '(names not in our sources)')}
        </p>
      ) : null}
      {sheet ? (
        <div role="group" aria-label={t('wizard:v5.loreLevels', '{{name}} levels', { name: sheet.name })} style={{ marginTop: '6px', display: 'grid', gap: '6px' }}>
          {sheet.levels.map((lv) => {
            const name = lv.name || t('wizard:v5.loreLevelUnnamed', 'Level {{n}}', { n: lv.dots });
            const taken = row.levels.includes(lv.dots);
            // A level with its own restriction (Tegyrius ••••: Banu Haqim only) isn't offered to
            // other clans; one already taken stays, so the check can say why.
            const open = loresheetLevelAllowed(lv, f.sheet);
            return (
              <div key={lv.dots}>
                <label style={{ display: 'flex', gap: '8px', alignItems: 'baseline', cursor: open || taken ? 'pointer' : 'default', color: open ? 'var(--sr-bone-100)' : 'var(--sr-bone-300)', fontSize: '13px' }}>
                  <input
                    type="checkbox"
                    aria-label={t('wizard:v5.loreLevelLabel', 'Level {{n}}: {{name}}', { n: lv.dots, name })}
                    checked={taken}
                    disabled={!open && !taken}
                    onChange={(e) =>
                      set({ levels: e.target.checked ? [...row.levels, lv.dots] : row.levels.filter((n) => n !== lv.dots) })
                    }
                  />
                  <span aria-hidden="true" style={{ color: 'var(--sr-blood-400)', minWidth: '52px' }}>{dots(lv.dots)}</span>
                  <span lang="en" aria-hidden="true">{name}</span>
                  {lv.restriction ? (
                    <span style={{ color: 'var(--sr-gold-400)', fontSize: '12px' }}>
                      {t('wizard:v5.loreLevelOnly', '({{restriction}})', { restriction: lv.restriction })}
                    </span>
                  ) : null}
                </label>
                <CatalogNote entry={lv.desc ? { desc: lv.desc } : null} style={{ marginLeft: '70px', marginTop: '0' }} />
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

/** Thin-blood Merits or Flaws from the catalog: names only, 1–3 of each in equal numbers. */
function ThinSelects({ kind }) {
  const f = useForge();
  const rows = kind === 'merit' ? f.thinBloodMerits : f.thinBloodFlaws;
  const setRows = kind === 'merit' ? f.setThinBloodMerits : f.setThinBloodFlaws;
  const word = KIND_LABEL[kind]();
  const options = thinBloodOptions(kind, f.settings);
  const [, hi] = V5_THIN_BLOOD_MERITS;
  const count = rows.filter((r) => String(r.name || '').trim()).length;
  // entries already picked on either side (an excluded pair is greyed out, core p. 183)
  const picked = [...f.thinBloodMerits, ...f.thinBloodFlaws]
    .map((r) => thinBloodOptions('merit').concat(thinBloodOptions('flaw')).find((o) => o.name === r.name))
    .filter(Boolean);
  const excluded = (o) => picked.some((x) => x.id !== o.id && ((x.excludes || []).includes(o.id) || (o.excludes || []).includes(x.id)));
  return (
    <div style={{ flex: '1 1 260px', minWidth: 0 }}>
      <div style={labelStyle}>
        {kind === 'merit'
          ? t('wizard:v5.thinMeritsHeader', 'Thin-blood Merits ({{n}})', { n: count })
          : t('wizard:v5.thinFlawsHeader', 'Thin-blood Flaws ({{n}})', { n: count })}
      </div>
      {rows.map((r, i) => {
        const entry = options.find((o) => o.name === r.name) || null;
        const others = rows.filter((_, j) => j !== i).map((x) => x.name);
        return (
          <div key={i} style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                value={r.name}
                aria-label={t('wizard:v5.thinRowLabel', 'Thin-blood {{kind}} {{n}}', { kind: word, n: i + 1 })}
                onChange={(e) => {
                  const pick = options.find((o) => o.name === e.target.value);
                  setRows((prev) => prev.map((x, j) => (j === i ? { name: e.target.value, id: pick?.id } : x)));
                }}
                style={{ ...inputStyle, flex: '1 1 auto', width: 'auto', padding: '8px' }}
              >
                <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
                {r.name && !entry ? <option value={r.name}>{r.name}</option> : null}
                {options.map((o) => (
                  <option key={o.id} value={o.name} disabled={others.includes(o.name) || (o.name !== r.name && excluded(o))}>
                    {o.name}
                  </option>
                ))}
              </select>
              {rows.length > 1 ? (
                <button
                  type="button"
                  aria-label={t('wizard:v5.removeThin', 'Remove thin-blood {{kind}} {{n}}', { kind: word, n: i + 1 })}
                  onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                  style={smallButtonStyle}
                >
                  ×
                </button>
              ) : null}
            </div>
            {entry?.requires ? (
              <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginTop: '4px' }}>
                {t('wizard:v5.advRequires', 'Needs: {{req}}', { req: entry.requires })}
              </div>
            ) : null}
            <CatalogNote entry={entry} />
          </div>
        );
      })}
      {rows.length < hi ? (
        <button type="button" onClick={() => setRows((prev) => [...prev, { name: '' }])} style={addButtonStyle}>
          {kind === 'merit' ? t('wizard:v5.addMerit', '+ Add Merit') : t('wizard:v5.addFlaw', '+ Add Flaw')}
        </button>
      ) : null}
    </div>
  );
}

export default function CatalogAdvantages() {
  const f = useForge();
  const clan = clanInfo(f.clan);
  const fixedFlaws = clanFlaws(f.sheet);
  const noStatus = Boolean(clan?.creation?.no_positive_status);
  const hasLore = loresheetEntries().length > 0;
  return (
    <div>
      <AdvSection kind="background" title={<Term id="backgrounds">Backgrounds</Term>}>
        {noStatus ? (
          <p style={{ ...noteStyle, fontSize: '12px', margin: '0 0 8px' }}>
            {t('wizard:v5.noPositiveStatus', '{{clan}} can\'t buy positive Status at creation.', { clan: f.clan })}
          </p>
        ) : null}
      </AdvSection>
      <AdvSection kind="merit" title={t('wizard:v5.sectionMerits', 'Merits')} />
      <AdvSection kind="flaw" title={t('wizard:v5.sectionFlaws', 'Flaws')}>
        {fixedFlaws.map((fl) => {
          const entry = advantageEntries().find((a) => a.id === fl.id);
          return (
            <div key={fl.id} data-clan-flaw={fl.id} style={{ marginBottom: '10px' }}>
              <div style={{ color: 'var(--sr-bone-100)', fontSize: '14px' }}>
                <span lang="en">{fl.name}</span> <span style={{ color: 'var(--sr-blood-400)' }}>{dots(fl.dots)}</span>{' '}
                <span style={{ color: 'var(--sr-gold-400)', fontSize: '12px' }}>
                  {t('wizard:v5.clanFlawV3', '{{clan}} start with it (core p. 107). It counts toward your {{min}} Flaw dots.', { clan: f.clan, min: f.derived.flaw_min_dots })}
                </span>
              </div>
              <CatalogNote entry={entry} />
            </div>
          );
        })}
      </AdvSection>
      {hasLore ? (
        <div style={sectionStyle} data-adv-section="loresheet">
          <div style={headingStyle}>{t('wizard:v5.sectionLoresheets', 'Loresheets')}</div>
          <p style={{ ...noteStyle, fontSize: '12px', margin: '0 0 8px' }}>
            {t('wizard:v5.loreHelpV3', 'Loresheets are bought with Advantage dots like any other Advantage (core p. 151). Each level is its own benefit, costs its number in dots and does not include the lower ones (p. 190). This app lets you take more than one at creation, a house ruling: the corebook has each player choose a Loresheet, more in play if the Storyteller allows (p. 151).')}
          </p>
          {f.loreRows.map((r, i) => (
            <LoreRow key={r.key} row={r} index={i} />
          ))}
          <button type="button" onClick={() => f.setLoreRows((prev) => [...prev, newLoreRow()])} style={addButtonStyle}>
            {t('wizard:v5.advAdd', '+ Add {{kind}}', { kind: KIND_LABEL.loresheet() })}
          </button>
        </div>
      ) : null}
      {f.clan === THIN_BLOOD ? (
        <div style={sectionStyle}>
          <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '0 0 10px', lineHeight: 1.5 }}>
            {t('wizard:v5.thinHelpCatalogV2', 'Thin-bloods also take {{lo}}–{{hi}} thin-blood Merits and the same number of thin-blood Flaws (core p. 182). They have no dot value and don\'t count toward the totals above. A few can\'t be taken together (p. 183).', { lo: V5_THIN_BLOOD_MERITS[0], hi: V5_THIN_BLOOD_MERITS[1] })}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            <ThinSelects kind="merit" />
            <ThinSelects kind="flaw" />
          </div>
        </div>
      ) : null}
      <label htmlFor="v5-field-merit-notes" style={{ ...labelStyle, marginTop: '16px' }}>
        {t('wizard:merits.extraNotes', 'Extra notes (optional)')}
      </label>
      <textarea
        id="v5-field-merit-notes"
        value={f.meritNotes}
        onChange={(e) => f.setMeritNotes(e.target.value)}
        rows={2}
        placeholder={t('wizard:merits.extraNotesPlaceholder', 'House rules, ST approval, page refs…')}
        style={{ ...inputStyle, resize: 'vertical' }}
      />
    </div>
  );
}

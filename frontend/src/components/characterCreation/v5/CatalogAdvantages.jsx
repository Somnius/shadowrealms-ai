/**
 * The Advantages step with the V5 catalog: Backgrounds, Merits and Flaws from dropdowns (grouped as
 * in the books, filtered for the clan), a dots picker bounded by the printed rating, a note and the
 * description; loresheets with their five levels; thin-blood Merits and Flaws; the clan's own Flaws
 * (Caitiff). A "Custom" row keeps anything the catalog lacks possible, for the Storyteller to approve.
 */
import { THIN_BLOOD, V5_THIN_BLOOD_MERITS } from '../../../characterSheet/v5/constants';
import {
  advantageDotChoices,
  advantageOptions,
  clanFlaws,
  clanInfo,
  loresheetAllowed,
  thinBloodOptions,
} from '../../../characterSheet/v5/validation';
import { advantageEntries, loresheetEntries } from '../../../characterSheet/v5/rulesData';
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

const KIND_LABEL = { background: 'Background', merit: 'Merit', flaw: 'Flaw' };
const sectionStyle = { marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--sr-night-700)' };
const headingStyle = { ...labelStyle, fontSize: '14px', fontFamily: 'var(--sr-font-display)', marginBottom: '8px' };

/** <optgroup>s of entries by their book group, keeping the catalog order. */
function GroupedOptions({ entries, takenIds, current }) {
  const groups = [];
  entries.forEach((e) => {
    let g = groups.find((x) => x.name === e.group);
    if (!g) groups.push((g = { name: e.group, entries: [] }));
    g.entries.push(e);
  });
  return groups.map((g) => (
    <optgroup key={g.name} label={g.name}>
      {g.entries.map((e) => {
        const r = ratingLabel(advantageDotChoices(e));
        return (
          <option key={e.id} value={e.id} disabled={e.id !== current && takenIds(e)}>
            {e.name}
            {r ? ` (${r})` : ''}
          </option>
        );
      })}
    </optgroup>
  ));
}

/** One Background, Merit or Flaw row. */
function AdvRow({ row, index, rows, setRows, clan }) {
  const label = t('wizard:v5.advRowLabel', '{{kind}} {{n}}', { kind: KIND_LABEL[row.kind], n: index + 1 });
  const set = (patch) => setRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, ...patch } : r)));
  const options = advantageOptions(clan, row.kind);
  const entry = row.id && row.id !== 'custom' ? advantageEntries().find((a) => a.id === row.id) : null;
  // Not offered any more (the clan changed): kept visible so its error makes sense.
  const stray = entry && !options.some((o) => o.id === entry.id) ? entry : null;
  // A non-repeatable entry once; a repeatable one up to its max_instances. The clan's own Flaws count.
  const fixed = clanFlaws({ clan }).map((f) => f.id);
  const taken = (e) => {
    const n = rows.filter((r) => r.id === e.id).length + fixed.filter((id) => id === e.id).length;
    return e.repeatable ? Boolean(e.max_instances && n >= e.max_instances) : n >= 1;
  };
  const choices = entry ? advantageDotChoices(entry) : [];
  const level = entry ? (entry.levels || []).find((l) => l.dots === Number(row.dots)) : null;
  const custom = row.id === 'custom';
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <select
          aria-label={label}
          value={row.id}
          onChange={(e) => {
            const id = e.target.value;
            const next = advantageEntries().find((a) => a.id === id);
            const first = next ? advantageDotChoices(next)[0] : null;
            set({ id, dots: id === 'custom' ? 1 : first || 0 });
          }}
          style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
        >
          <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
          {stray ? <option value={stray.id}>{stray.name}</option> : null}
          <GroupedOptions entries={options} takenIds={taken} current={row.id} />
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
          <span aria-label={t('wizard:v5.advDots', '{{name}} dots', { name: entry.name })} style={{ color: 'var(--sr-blood-400)', minWidth: '60px' }}>
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
  return (
    <div style={sectionStyle} data-adv-section={kind}>
      <div style={headingStyle}>{title}</div>
      {children}
      {rows.map((r, i) => (
        <AdvRow key={r.key} row={r} index={i} rows={rows} setRows={f.setAdvRows} clan={f.clan} />
      ))}
      <button type="button" onClick={() => f.setAdvRows((prev) => [...prev, newAdvRow(kind)])} style={addButtonStyle}>
        {t('wizard:v5.advAdd', '+ Add {{kind}}', { kind: KIND_LABEL[kind] })}
      </button>
    </div>
  );
}

/** One loresheet: the sheet, then the levels taken (each its own benefit, its number in dots). */
function LoreRow({ row, index }) {
  const f = useForge();
  const label = t('wizard:v5.advRowLabel', '{{kind}} {{n}}', { kind: 'Loresheet', n: index + 1 });
  const set = (patch) => f.setLoreRows((prev) => prev.map((r) => (r.key === row.key ? { ...r, ...patch } : r)));
  const sheet = loresheetEntries().find((l) => l.id === row.id) || null;
  const offered = loresheetEntries().filter((l) => loresheetAllowed(l, f.sheet));
  const takenElsewhere = f.loreRows.filter((r) => r.key !== row.key).map((r) => r.id);
  const total = row.levels.reduce((s, n) => s + n, 0);
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
        <select
          aria-label={label}
          value={row.id}
          onChange={(e) => set({ id: e.target.value, levels: [] })}
          style={{ ...inputStyle, flex: '2 1 260px', width: 'auto', padding: '8px' }}
        >
          <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
          {sheet && !offered.includes(sheet) ? <option value={sheet.id}>{sheet.name}</option> : null}
          {offered.map((l) => (
            <option key={l.id} value={l.id} disabled={takenElsewhere.includes(l.id)}>
              {l.name}
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
      {sheet ? (
        <div role="group" aria-label={t('wizard:v5.loreLevels', '{{name}} levels', { name: sheet.name })} style={{ marginTop: '6px', display: 'grid', gap: '6px' }}>
          {sheet.levels.map((lv) => (
            <div key={lv.dots}>
              <label style={{ display: 'flex', gap: '8px', alignItems: 'baseline', cursor: 'pointer', color: 'var(--sr-bone-100)', fontSize: '13px' }}>
                <input
                  type="checkbox"
                  checked={row.levels.includes(lv.dots)}
                  onChange={(e) =>
                    set({ levels: e.target.checked ? [...row.levels, lv.dots] : row.levels.filter((n) => n !== lv.dots) })
                  }
                />
                <span style={{ color: 'var(--sr-blood-400)', minWidth: '52px' }}>{dots(lv.dots)}</span>
                <span lang="en">{lv.name}</span>
              </label>
              <CatalogNote entry={lv.desc ? { desc: lv.desc } : null} style={{ marginLeft: '70px', marginTop: '0' }} />
            </div>
          ))}
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
  const word = kind === 'merit' ? 'Merit' : 'Flaw';
  const options = thinBloodOptions(kind);
  const [, hi] = V5_THIN_BLOOD_MERITS;
  return (
    <div style={{ flex: '1 1 260px', minWidth: 0 }}>
      <div style={labelStyle}>
        Thin-blood {word}s ({rows.filter((r) => String(r.name || '').trim()).length})
      </div>
      {rows.map((r, i) => {
        const entry = options.find((o) => o.name === r.name) || null;
        const others = rows.filter((_, j) => j !== i).map((x) => x.name);
        return (
          <div key={i} style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                value={r.name}
                aria-label={`Thin-blood ${word} ${i + 1}`}
                onChange={(e) => {
                  const pick = options.find((o) => o.name === e.target.value);
                  setRows((prev) => prev.map((x, j) => (j === i ? { name: e.target.value, id: pick?.id } : x)));
                }}
                style={{ ...inputStyle, flex: '1 1 auto', width: 'auto', padding: '8px' }}
              >
                <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
                {r.name && !entry ? <option value={r.name}>{r.name}</option> : null}
                {options.map((o) => (
                  <option key={o.id} value={o.name} disabled={others.includes(o.name)}>
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
      <AdvSection kind="merit" title="Merits" />
      <AdvSection kind="flaw" title="Flaws">
        {fixedFlaws.map((fl) => {
          const entry = advantageEntries().find((a) => a.id === fl.id);
          return (
            <div key={fl.id} data-clan-flaw={fl.id} style={{ marginBottom: '10px' }}>
              <div style={{ color: 'var(--sr-bone-100)', fontSize: '14px' }}>
                <span lang="en">{fl.name}</span> <span style={{ color: 'var(--sr-blood-400)' }}>{dots(fl.dots)}</span>{' '}
                <span style={{ color: 'var(--sr-gold-400)', fontSize: '12px' }}>
                  {t('wizard:v5.clanFlaw', '{{clan}} start with it; it counts as one of your own Flaws.', { clan: f.clan })}
                </span>
              </div>
              <CatalogNote entry={entry} />
            </div>
          );
        })}
      </AdvSection>
      {hasLore ? (
        <div style={sectionStyle} data-adv-section="loresheet">
          <div style={headingStyle}>Loresheets</div>
          <p style={{ ...noteStyle, fontSize: '12px', margin: '0 0 8px' }}>
            {t('wizard:v5.loreHelp', 'Each level is its own benefit and costs its number in Advantage dots; it does not include the lower ones (core p. 190).')}
          </p>
          {f.loreRows.map((r, i) => (
            <LoreRow key={r.key} row={r} index={i} />
          ))}
          <button type="button" onClick={() => f.setLoreRows((prev) => [...prev, newLoreRow()])} style={addButtonStyle}>
            {t('wizard:v5.advAdd', '+ Add {{kind}}', { kind: 'Loresheet' })}
          </button>
        </div>
      ) : null}
      {f.clan === THIN_BLOOD ? (
        <div style={sectionStyle}>
          <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '0 0 10px', lineHeight: 1.5 }}>
            {t('wizard:v5.thinHelpCatalog', 'Thin-bloods also take {{lo}}–{{hi}} thin-blood Merits and the same number of thin-blood Flaws (core p. 182). They have no dot value and don\'t count toward the totals above.', { lo: V5_THIN_BLOOD_MERITS[0], hi: V5_THIN_BLOOD_MERITS[1] })}
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

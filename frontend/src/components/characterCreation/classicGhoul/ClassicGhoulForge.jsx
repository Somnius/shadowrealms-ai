import { useState } from 'react';
import { GothicBox } from '../../GothicDecorations';
import DotTrack from '../DotTrack';
import SheetSection from '../SheetSection';
import PoolSummary from '../PoolSummary';
import AttributeColumns from '../AttributeColumns';
import AbilityColumns from '../AbilityColumns';
import MeritFlawRows from '../MeritFlawRows';
import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import FreebieSummary from '../FreebieSummary';
import BloodPoolBoxes from './BloodPoolBoxes';
import useClassicGhoulForgeState from './useClassicGhoulForgeState';
import { ARCHETYPE_CUSTOM, WOD_ARCHETYPES } from '../../../characterSheet/constants';
import {
  BLOOD_POOL_MAX,
  BLOOD_POOL_PER_TURN,
  BOND_DRINKS,
  CLASSIC_GHOUL_SECTION_IDS as S,
  GHOUL_BACKGROUND_DOTS,
  GHOUL_BACKGROUND_PRESETS,
  GHOUL_DISCIPLINE_DOTS,
  GHOUL_FREEBIE_RULES,
  buildClassicGhoulPayload,
  disciplineCap,
  isClassicDomitor,
  validateClassicGhoulSheet,
  classicGhoulServerErrors,
  CLASSIC_GHOUL_ROW_NAME_MAX,
  CLASSIC_GHOUL_TEXT_MAX as TEXT_MAX,
} from '../../../characterSheet/classicGhoul';
import { VIRTUE_TOTAL_AT_CREATION } from '../../../characterSheet/validation';
import { translateSheetErrors } from '../../../characterSheet/i18nErrors';
import { authFetch } from '../../../app/http';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';

const ACCENT = 'var(--sr-blood-500)';
const inputStyle = {
  width: '100%',
  padding: '10px',
  background: 'var(--sr-night-850)',
  color: 'var(--sr-bone-100)',
  border: '2px solid var(--sr-night-700)',
  borderRadius: '8px',
};
const smallInput = { ...inputStyle, padding: '8px', border: '1px solid var(--sr-night-700)', borderRadius: '6px' };
const labelStyle = { color: 'var(--sr-arcane-300)', display: 'block', marginBottom: '6px' };
const noteStyle = { color: 'var(--sr-bone-500)', fontSize: '12px', lineHeight: 1.5, margin: '6px 0 12px' };
const gridStyle = { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '14px', marginBottom: '14px' };
const smallButton = {
  padding: '6px 12px',
  background: 'var(--sr-night-800)',
  color: 'var(--sr-bone-100)',
  border: '1px solid var(--sr-night-600)',
  borderRadius: '6px',
  cursor: 'pointer',
};
const int = (v) => parseInt(v, 10) || 0;

// Labels are functions: t() runs at render time. Game terms stay English.
const SECTION_ORDER = [
  [S.identity, () => t('wizard:classicGhoul.section.identity', 'Ghoul & domitor')],
  [S.attributes, () => 'Attributes'],
  [S.abilities, () => 'Abilities'],
  [S.advantages, () => 'Advantages'],
  [S.bond, () => t('wizard:classicGhoul.section.bond', 'Blood Bond & feeding')],
  [S.story, () => t('wizard:section.story', 'Story')],
  [S.freebies, () => 'Freebies'],
];

function scrollToSection(id) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null;
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function Field({ id, label, value, onChange, placeholder, type = 'text', min, max, maxLength }) {
  return (
    <div>
      <label htmlFor={id} style={labelStyle}>
        {label}
      </label>
      <input id={id} type={type} min={min} max={max} maxLength={maxLength} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
    </div>
  );
}

function ArchetypePicker({ id, label, pick, setPick, custom, setCustom, maxLength }) {
  return (
    <div>
      <label htmlFor={id} style={labelStyle}>
        {label}
      </label>
      <select id={id} value={pick} onChange={(e) => setPick(e.target.value)} style={{ ...inputStyle, marginBottom: '8px' }}>
        {WOD_ARCHETYPES.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
        <option value={ARCHETYPE_CUSTOM}>{t('wizard:classic.customArchetype', 'Custom (enter below)')}</option>
      </select>
      <input
        aria-label={label}
        value={custom}
        maxLength={maxLength}
        onChange={(e) => setCustom(e.target.value)}
        placeholder={pick === ARCHETYPE_CUSTOM ? label : t('wizard:classic.archetypeExtra', 'Optional: extra detail, or wording for another system')}
        style={inputStyle}
      />
    </div>
  );
}

/** Potence (pinned), the one other Discipline, a third bought with freebies. */
function DisciplineRows({ f }) {
  const cap = disciplineCap(f.generation);
  const total = (rows) => rows.reduce((s, d) => s + int(d.dots), 0);
  const setRow = (i, patch) => f.setDisciplines((prev) => prev.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  const setDots = (i, n) => {
    const cur = int(f.disciplines[i].dots);
    let v = n;
    if (i === 0) v = Math.max(1, v); // every ghoul has Potence 1
    if (v > cap) return;
    const others = total(f.disciplines) - cur;
    if (!f.freebieMode && v > cur && others + v > GHOUL_DISCIPLINE_DOTS) return;
    setRow(i, { dots: v });
  };
  const rows = f.disciplines.map((d, i) => ({ d, i })).filter(({ d, i }) => i < 2 || f.freebieMode || d.name || int(d.dots));
  return (
    <div style={{ marginBottom: '20px' }}>
      <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '8px' }}>
        <Term id="discipline">Disciplines</Term>{' '}
        {t('wizard:classicGhoul.disciplinesHint', '(Potence 1 and one dot in another Discipline; up to {{cap}} for the ghoul of a generation {{gen}} domitor)', { cap, gen: f.generation })}
      </div>
      {rows.map(({ d, i }) => (
        <div key={i} data-discipline-row={i} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
          {i === 0 ? (
            <span lang="en" style={{ flex: '1 1 180px', color: 'var(--sr-bone-100)', padding: '8px' }}>
              Potence
            </span>
          ) : (
            <select
              aria-label={t('wizard:classicGhoul.disciplineN', 'Discipline {{n}}', { n: i + 1 })}
              value={d.name}
              onChange={(e) => setRow(i, { name: e.target.value, dots: e.target.value ? Math.max(int(d.dots), 0) : 0 })}
              style={{ ...smallInput, flex: '1 1 180px' }}
            >
              <option value="">—</option>
              {f.disciplineOptions
                .filter((o) => o === d.name || !f.disciplines.some((x, j) => j !== i && x.name === o))
                .map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
            </select>
          )}
          <DotTrack value={d.dots} maxRank={5} accent={ACCENT} label={i === 0 ? 'Potence' : d.name || undefined} onChange={(n) => setDots(i, n)} />
        </div>
      ))}
      <p style={noteStyle}>
        {f.kind === 'vassal'
          ? t('wizard:classicGhoul.vassalDisciplines', "A vassal learns one of its domitor's Disciplines, or Celerity or Fortitude, which the Blood teaches by instinct. Protean and Thaumaturgy only from a Gangrel or Tremere domitor.")
          : t('wizard:classicGhoul.independentDisciplines', 'An independent ghoul may take any Discipline (not Protean or Thaumaturgy); your Storyteller may ask for Celerity, Fortitude or Potence.')}
      </p>
    </div>
  );
}

function BackgroundRows({ f }) {
  const setRow = (i, patch) => f.setBackgrounds((prev) => prev.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  return (
    <div style={{ marginBottom: '20px' }}>
      <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '8px' }}>
        <Term id="backgrounds" /> {t('wizard:classic.dotsAtCreation', '({{n}} dots at creation; more with freebies)', { n: GHOUL_BACKGROUND_DOTS })}
      </div>
      <datalist id="classic-ghoul-backgrounds">
        {GHOUL_BACKGROUND_PRESETS.map((b) => (
          <option key={b} value={b} />
        ))}
      </datalist>
      {f.backgrounds.map((b, i) => (
        <div key={i} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <input
            aria-label={t('wizard:classicGhoul.backgroundN', 'Background {{n}}', { n: i + 1 })}
            list="classic-ghoul-backgrounds"
            placeholder={t('wizard:classic.backgroundPlaceholder', 'e.g. Resources')}
            value={b.name}
            maxLength={CLASSIC_GHOUL_ROW_NAME_MAX}
            onChange={(e) => setRow(i, { name: e.target.value })}
            style={{ ...smallInput, flex: '1 1 160px' }}
          />
          <DotTrack
            value={b.dots}
            maxRank={5}
            accent="var(--sr-arcane-400)"
            label={b.name || undefined}
            onChange={(n) => {
              const others = f.backgrounds.reduce((s, x, j) => (j === i ? s : s + int(x.dots)), 0);
              if (!f.freebieMode && n > int(b.dots) && others + n > GHOUL_BACKGROUND_DOTS) return;
              setRow(i, { dots: n });
            }}
          />
        </div>
      ))}
      <p style={noteStyle}>
        {t('wizard:classicGhoul.backgroundsHint', 'Domitor (vassals only, optional): your master cares what becomes of you; its generation sets the dots (11th or higher: 1 … 6th: 5). No Generation, Herd or Status; Mentor mostly for independents; domitors seldom allow Retainers.')}
      </p>
    </div>
  );
}

function VirtueRows({ f }) {
  const m = f.derived;
  const bought = Object.values(f.virtueFreebies).reduce((s, v) => s + int(v), 0);
  return (
    <>
      <div style={{ marginBottom: '16px' }}>
        <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginBottom: '8px' }}>
          <Term id="virtues" />{' '}
          {bought > 0
            ? t('wizard:classic.virtuesPlacedBought', "(1 free each + 7 = {{total}}; placed {{placed}} + {{bought}} bought with freebies; those don't change Humanity or Willpower)", { total: VIRTUE_TOTAL_AT_CREATION, placed: f.virtueTotal, bought })
            : t('wizard:classic.virtuesPlaced', '(1 free each + 7 = {{total}}; placed {{placed}})', { total: VIRTUE_TOTAL_AT_CREATION, placed: f.virtueTotal })}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {[
            ['conscience', 'Conscience'],
            ['self_control', 'Self-Control'],
            ['courage', 'Courage'],
          ].map(([key, label]) => (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span lang="en" style={{ color: 'var(--sr-bone-300)', fontSize: '12px', minWidth: '100px' }}>
                {label}
              </span>
              <DotTrack value={m.virtues[key]} maxRank={5} accent="#f472b6" label={label} onChange={(n) => f.setVirtueFinal(key, n)} />
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'grid', gap: '10px', marginBottom: '20px' }}>
        {[
          ['humanity', 'Humanity', m.humanity, 'Conscience + Self-Control', f.humanityBonus, f.setHumanityBonus],
          ['willpower', 'Willpower', m.willpower, 'Courage', f.willpowerBonus, f.setWillpowerBonus],
        ].map(([termId, label, value, from, bonus, setBonus]) => (
          <div key={label} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
            <span style={{ color: 'var(--sr-arcane-300)', fontSize: '12px', minWidth: '80px' }}>
              <Term id={termId} />
            </span>
            <DotTrack value={value} maxRank={10} accent="#f472b6" disabled onChange={() => {}} />
            <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
              {value} = {from}
              {bonus > 0 ? ` + ${t('wizard:classic.nFreebie', '{{n}} freebie', { n: bonus })}` : ''}
            </span>
            {f.freebieMode ? (
              <span style={{ display: 'inline-flex', gap: '4px' }}>
                <button type="button" aria-label={t('wizard:classic.lowerFreebie', 'Lower {{label}} freebie dots', { label })} disabled={bonus <= 0} onClick={() => setBonus(Math.max(0, bonus - 1))} style={smallButton}>
                  −
                </button>
                <button type="button" aria-label={t('wizard:classic.raiseFreebie', 'Raise {{label}} with freebies', { label })} disabled={value >= 10} onClick={() => setBonus(bonus + 1)} style={smallButton}>
                  +
                </button>
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </>
  );
}

function BloodPoolRow({ f }) {
  const r = f.lastRoll;
  return (
    <div data-section="blood-pool" style={{ padding: '12px', border: '1px solid var(--sr-night-700)', borderRadius: '8px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
        <strong style={{ color: 'var(--sr-arcane-300)' }}>
          <Term id="bloodPool" />
        </strong>
        <BloodPoolBoxes current={f.bloodPool || 0} max={BLOOD_POOL_MAX} />
        <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
          {t('wizard:classicGhoul.poolLine', '{{current}} / {{max}} · {{perTurn}} per turn', { current: f.bloodPool ?? '—', max: BLOOD_POOL_MAX, perTurn: BLOOD_POOL_PER_TURN })}
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
        <button type="button" onClick={f.rollPool} style={{ ...smallButton, borderColor: 'var(--sr-blood-700)' }}>
          {t('wizard:classicGhoul.roll', 'Roll 1d10')}
        </button>
        {r && r.rerollable ? (
          <button type="button" onClick={f.rollPool} style={smallButton}>
            {t('wizard:classicGhoul.reroll', "Reroll the 1 (Storyteller's option)")}
          </button>
        ) : null}
        <label htmlFor="classic-ghoul-pool" style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
          {t('wizard:classicGhoul.poolSet', 'Starting vitae')}
        </label>
        <input
          id="classic-ghoul-pool"
          type="number"
          min={1}
          max={BLOOD_POOL_MAX}
          value={f.bloodPool ?? ''}
          onChange={(e) => {
            const v = parseInt(e.target.value, 10);
            f.setBloodPool(Number.isInteger(v) ? Math.max(1, Math.min(BLOOD_POOL_MAX, v)) : null);
          }}
          style={{ ...smallInput, width: '80px' }}
        />
        {r ? (
          <span data-roll={r.roll} style={{ color: 'var(--sr-bone-100)', fontSize: '12px' }}>
            {f.kind === 'independent' ? t('wizard:classicGhoul.rolledHalf', 'Rolled {{roll}}, halved: {{pool}}', { roll: r.roll, pool: r.pool }) : t('wizard:classicGhoul.rolled', 'Rolled {{roll}}', { roll: r.roll })}
          </span>
        ) : null}
      </div>
      <p style={noteStyle}>
        {t('wizard:classicGhoul.poolHint', 'A ghoul holds up to 10 points of vitae and spends 1 per turn: to heal, to raise a Physical Attribute (up to twice the original), to use its Disciplines (they need at least 1 point). It starts with a roll of 1d10; an independent ghoul halves it, rounding up.')}
      </p>
    </div>
  );
}

/**
 * The Classic ghoul forge (docs/rules/CLASSIC_REVISED.md §7): a ghoul of one of the user's Classic
 * vampires, by Ghouls: Fatal Addiction (Revised p. 276), with no chronicle of its own. Rules:
 * characterSheet/classicGhoul.js; state: useClassicGhoulForgeState.js. `characters`: the user's own
 * rows (GET /api/characters/); `domitorId`: the vampire it starts from (?ghoul_of=); `rng`: the die.
 */
export default function ClassicGhoulForge({ token, characters, domitorId, onDone, onCancel, showError, showSuccess, rng }) {
  const domitors = (characters || []).filter(isClassicDomitor);
  const f = useClassicGhoulForgeState(domitors, domitorId, rng);
  const [submitting, setSubmitting] = useState(false);
  const errs = f.fieldErrors;
  const inlineErr = (id) => (errs[id] ? <p role="alert" style={{ color: 'var(--sr-danger-400)', fontSize: '13px', marginBottom: '12px' }}>{errs[id]}</p> : null);

  if (!domitors.length) {
    return (
      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '20px 16px 60px' }}>
        <GothicBox theme="vampire">
          <div style={{ padding: '8px' }}>
            <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>{t('wizard:classicGhoul.title', 'Ghoul forge · Classic (Revised)')}</h2>
            <p style={{ color: 'var(--sr-bone-300)' }}>{t('wizard:classicGhoul.noDomitor', 'A Classic ghoul belongs to one of your Classic vampires, and you have none yet. Forge the vampire first.')}</p>
            <button type="button" onClick={onCancel} style={smallButton}>
              {t('wizard:cancel', 'Cancel')}
            </button>
          </div>
        </GothicBox>
      </div>
    );
  }

  const handleSubmit = async () => {
    const err = translateSheetErrors(validateClassicGhoulSheet(f.sheet, f.domitor));
    f.setFieldErrors(err);
    const first = SECTION_ORDER.find(([id]) => err[id]);
    if (first) {
      showError?.(err[first[0]]);
      scrollToSection(first[0]);
      return;
    }
    const payload = buildClassicGhoulPayload(f.sheet, f.domitor);
    setSubmitting(true);
    try {
      const res = await authFetch('/api/characters/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: f.name.trim(),
          campaign_id: null,
          ...payload,
          background: f.background.trim(),
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // the server checks a Classic ghoul's bounds (backend/services/classic_ghoul.py): English problem lines
        if (Array.isArray(body.problems) && body.problems.length) {
          // each problem on its section (a too-long text as the client's own, translated)
          const bySection = translateSheetErrors(classicGhoulServerErrors(body.problems));
          const refused = t('wizard:problem.refused', 'The server refused the sheet:');
          const errs = Object.fromEntries(Object.entries(bySection).map(([k, v]) => [k, `${refused} ${v}`]));
          f.setFieldErrors(errs);
          showError?.(Object.values(errs)[0]);
          scrollToSection(SECTION_ORDER.map(([id]) => id).find((id) => errs[id]) || Object.keys(errs)[0]);
          return;
        }
        showError?.(body.error || t('wizard:error.createFailed', 'Could not create character.'));
        return;
      }
      showSuccess?.(t('wizard:classicGhoul.created', '{{name}} serves {{domitor}}. The sheet is on your Profile.', { name: f.name.trim(), domitor: f.domitor.name }));
      onDone?.(body);
    } catch {
      showError?.(t('wizard:error.network', 'Network error while creating character.'));
    } finally {
      setSubmitting(false);
    }
  };

  const freebies = f.derived.freebies;
  const domClan = f.domitor?.wod_meta?.clan;
  return (
    <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox theme="vampire">
        <div style={{ padding: '8px 8px 0' }}>
          <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>{t('wizard:classicGhoul.title', 'Ghoul forge · Classic (Revised)')}</h2>
          <p style={{ color: 'var(--sr-bone-500)', fontSize: '14px', lineHeight: 1.5 }}>
            {t('wizard:classicGhoul.intro', 'A ghoul by Ghouls: Fatal Addiction (Revised p. 276 points to it): a mortal kept on a vampire’s vitae. Place your creation dots, then spend 21 freebie points. It has no chronicle of its own: it goes where its domitor goes. Your Storyteller has the final say.')}
          </p>
        </div>

        <div
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            padding: '12px 16px',
            margin: '0 -4px 8px',
            background: 'linear-gradient(180deg, rgba(15,23,41,0.98) 70%, transparent)',
            borderBottom: '1px solid var(--sr-night-700)',
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
            {SECTION_ORDER.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => scrollToSection(id)}
                style={{
                  fontSize: '11px',
                  padding: '6px 12px',
                  borderRadius: '999px',
                  background: errs[id] ? 'rgba(248,113,113,0.15)' : 'var(--sr-night-800)',
                  color: errs[id] ? 'var(--sr-blood-300)' : 'var(--sr-blood-400)',
                  border: `1px solid ${errs[id] ? 'var(--sr-blood-700)' : 'var(--sr-night-600)'}`,
                  cursor: 'pointer',
                  fontFamily: 'var(--sr-font-display)',
                }}
              >
                {label()}
              </button>
            ))}
          </div>
          <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '12px', color: 'var(--sr-bone-300)' }}>
            <span>
              <strong style={{ color: 'var(--sr-bone-100)' }}>{f.name || '—'}</strong>
              {f.domitor ? ` · ${t('sheet:ghoul.ghoulOf', 'Ghoul of {{domitor}}', { domitor: f.domitor.name })}` : ''}
            </span>
            <label style={{ color: freebies.remaining < 0 ? 'var(--sr-blood-300)' : 'var(--sr-bone-300)', display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input type="checkbox" checked={f.freebieMode} onChange={(e) => f.setFreebieMode(e.target.checked)} />
              {t('wizard:classic.freebieMode', 'Freebie mode · {{spent}}/{{available}} spent', { spent: freebies.spent, available: freebies.available })}
            </label>
          </div>
        </div>

        <div style={{ padding: '8px 16px 24px' }}>
          <ResponsiveSheetBlock sectionId={S.identity} title={t('wizard:classicGhoul.section.identity', 'Ghoul & domitor')} subtitle={t('wizard:classicGhoul.identitySub', 'Whose ghoul, what kind, and who it is.')} accent={ACCENT}>
            {inlineErr(S.identity)}
            <label htmlFor="classic-ghoul-domitor" style={labelStyle}>
              <Term id="domitor" />
            </label>
            <select id="classic-ghoul-domitor" value={f.domitorId} onChange={(e) => f.setDomitorId(e.target.value)} style={{ ...inputStyle, marginBottom: '6px' }}>
              {f.domitors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                  {d.wod_meta?.clan ? ` — ${d.wod_meta.clan}` : ''}
                  {d.wod_meta?.generation ? `, ${t('wizard:classicGhoul.generationN', 'generation {{n}}', { n: d.wod_meta.generation })}` : ''}
                  {' · '}
                  {d.campaign_name || t('wizard:ghoul.noChronicle', 'no chronicle')}
                </option>
              ))}
            </select>
            <p style={noteStyle}>{t('wizard:ghoul.domitorNote', 'A ghoul has no chronicle of its own: it goes where its domitor goes. Their Storyteller sees its sheet.')}</p>
            <div style={gridStyle}>
              <div>
                <label htmlFor="classic-ghoul-kind" style={labelStyle}>
                  {t('wizard:classicGhoul.kind', 'Kind')}
                </label>
                <select id="classic-ghoul-kind" value={f.kind} onChange={(e) => f.setKind(e.target.value)} style={inputStyle}>
                  <option value="vassal">{t('wizard:classicGhoul.kindVassal', 'Vassal: serves the domitor')}</option>
                  <option value="independent">{t('wizard:classicGhoul.kindIndependent', 'Independent: no master, finds vitae on its own')}</option>
                </select>
              </div>
              <Field id="classic-ghoul-name" label={t('wizard:field.name', 'Character name')} value={f.name} onChange={f.setName} />
              <Field id="classic-ghoul-concept" maxLength={TEXT_MAX.concept} label={t('wizard:field.concept', 'Concept')} value={f.concept} onChange={f.setConcept} placeholder={t('wizard:classicGhoul.conceptPlaceholder', 'e.g. day-man and driver')} />
              <Field id="classic-ghoul-duties" maxLength={TEXT_MAX.duties} label={t('wizard:classicGhoul.duties', 'Duties')} value={f.duties} onChange={f.setDuties} placeholder={t('wizard:classicGhoul.dutiesPlaceholder', 'what the domitor has it do')} />
              <Field id="classic-ghoul-since" maxLength={TEXT_MAX.ghouledSince} label={t('wizard:ghoul.since', 'Ghoul since')} value={f.ghouledSince} onChange={f.setGhouledSince} placeholder={t('wizard:ghoul.sincePlaceholder', 'e.g. two years ago, before the move')} />
              <Field id="classic-ghoul-age" type="number" min={0} max={1000} label={t('wizard:ghoul.age', 'Age')} value={f.age} onChange={f.setAge} />
              <Field id="classic-ghoul-looks" type="number" min={0} max={150} label={t('wizard:ghoul.apparentAge', 'Looks (apparent age)')} value={f.apparentAge} onChange={f.setApparentAge} />
            </div>
            <div style={gridStyle}>
              <ArchetypePicker id="classic-ghoul-nature" label="Nature" pick={f.naturePick} setPick={f.setNaturePick} custom={f.natureCustom} setCustom={f.setNatureCustom} maxLength={TEXT_MAX.nature} />
              <ArchetypePicker id="classic-ghoul-demeanor" label="Demeanor" pick={f.demeanorPick} setPick={f.setDemeanorPick} custom={f.demeanorCustom} setCustom={f.setDemeanorCustom} maxLength={TEXT_MAX.demeanor} />
            </div>
            {domClan ? <p style={noteStyle}>{t('wizard:classicGhoul.domitorClan', "The domitor's clan: {{clan}}.", { clan: domClan })}</p> : null}
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.attributes} title={<Term id="attributes" />} subtitle={t('wizard:classicGhoul.attributesSub', 'Every attribute starts at 1. Add 6 / 4 / 3 dots across Physical, Social, Mental.')} accent={ACCENT}>
            {inlineErr(S.attributes)}
            <PoolSummary variant="attributes" attrs={f.attributes} pools={f.attrPools} />
            <label htmlFor="classic-ghoul-attr-priority" style={labelStyle}>
              {t('wizard:classicGhoul.attrPrimary', 'Which category is primary (+6 dots)?')}
            </label>
            <select id="classic-ghoul-attr-priority" value={f.attrPriority} onChange={(e) => f.setAttrPriority(e.target.value)} style={{ ...inputStyle, maxWidth: '360px', marginBottom: '20px' }}>
              <option value="physical">{t('wizard:classicGhoul.attrOrder.physical', 'Physical primary (+6) · Social (+4) · Mental (+3)')}</option>
              <option value="social">{t('wizard:classicGhoul.attrOrder.social', 'Social primary (+6) · Physical (+4) · Mental (+3)')}</option>
              <option value="mental">{t('wizard:classicGhoul.attrOrder.mental', 'Mental primary (+6) · Social (+4) · Physical (+3)')}</option>
            </select>
            <AttributeColumns attrs={f.attributes} setAttrs={f.setAttributes} pools={f.attrPools} freebieMode={f.freebieMode} />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.abilities} title={<Term id="abilities" />} subtitle={t('wizard:classicGhoul.abilitiesSub', '11 / 7 / 4 across Talents, Skills, Knowledges; no ability above 3 before freebies.')} accent={ACCENT}>
            {inlineErr(S.abilities)}
            <PoolSummary variant="abilities" abilities={f.abilities} abilityPools={f.abilityPools} customAbilities={f.customAbilities} />
            <label htmlFor="classic-ghoul-ability-priority" style={labelStyle}>
              {t('wizard:classicGhoul.abilityPrimary', 'Which column is primary (11 dots)?')}
            </label>
            <select id="classic-ghoul-ability-priority" value={f.abilityPriority} onChange={(e) => f.setAbilityPriority(e.target.value)} style={{ ...inputStyle, maxWidth: '400px', marginBottom: '20px' }}>
              <option value="talents">Talents 11 · Skills 7 · Knowledges 4</option>
              <option value="skills">Skills 11 · Talents 7 · Knowledges 4</option>
              <option value="knowledges">Knowledges 11 · Skills 7 · Talents 4</option>
            </select>
            <AbilityColumns
              abilities={f.abilities}
              setAbilities={f.setAbilities}
              pools={f.abilityPools}
              customAbilities={f.customAbilities}
              setCustomAbilities={f.setCustomAbilities}
              freebieMode={f.freebieMode}
            />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.advantages} title="Advantages" subtitle={t('wizard:classicGhoul.advantagesSub', 'Potence and one more Discipline, 5 Background dots, Virtues 1 free each + 7, and the Blood Pool.')} accent={ACCENT}>
            {inlineErr(S.advantages)}
            <SheetSection title={t('wizard:classicGhoul.advantagesTitle', 'Ghoul advantages')} accent={ACCENT}>
              <DisciplineRows f={f} />
              <BackgroundRows f={f} />
              <VirtueRows f={f} />
              <BloodPoolRow f={f} />
            </SheetSection>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.bond} title={t('wizard:classicGhoul.section.bond', 'Blood Bond & feeding')} subtitle={t('wizard:classicGhoul.bondSub', 'Drinks of the domitor’s vitae: the third binds.')} accent={ACCENT}>
            {inlineErr(S.bond)}
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
              <span lang="en" style={{ color: 'var(--sr-arcane-300)', fontSize: '13px' }}>
                Blood Bond
              </span>
              <DotTrack value={f.bondStage} maxRank={BOND_DRINKS} accent={ACCENT} label="Blood Bond" onChange={(n) => f.setBondStage(n)} />
              <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
                {t('wizard:classicGhoul.bondStage', { one: '{{count}} of {{max}} drinks', other: '{{count}} of {{max}} drinks' }, { count: f.bondStage, max: BOND_DRINKS })}
                {f.bondStage >= BOND_DRINKS ? ` · ${t('wizard:classicGhoul.bound', 'fully Bound')}` : ''}
              </span>
            </div>
            <p style={noteStyle}>{t('wizard:classicGhoul.bondHint', 'A vassal begins play Blood Bound to its domitor (3 drinks); an independent ghoul starts with none. Your Storyteller has the last word.')}</p>
            <div style={gridStyle}>
              <Field id="classic-ghoul-bond-note" maxLength={TEXT_MAX.bondNote} label={t('wizard:classicGhoul.bondNote', 'Bond note')} value={f.bondNote} onChange={f.setBondNote} placeholder={t('wizard:classicGhoul.bondNotePlaceholder', 'e.g. third drink in 1998')} />
              <Field id="classic-ghoul-last-fed" maxLength={TEXT_MAX.feedingLast} label={t('wizard:classicGhoul.lastFed', "Last fed on the domitor's vitae")} value={f.feedingLast} onChange={f.setFeedingLast} placeholder={t('wizard:ghoul.lastFedPlaceholder', 'e.g. early October')} />
              <Field id="classic-ghoul-feeding-note" maxLength={TEXT_MAX.feedingNote} label={t('wizard:ghoul.feedingNote', 'Feeding note: how often, from whom, what it costs')} value={f.feedingNote} onChange={f.setFeedingNote} />
              <Field id="classic-ghoul-overdosing" maxLength={TEXT_MAX.overdosing} label={t('wizard:classicGhoul.overdosing', 'Overdosing?')} value={f.overdosing} onChange={f.setOverdosing} placeholder={t('wizard:classicGhoul.overdosingPlaceholder', 'e.g. can cram 2 extra points (Stamina 2)')} />
            </div>
            <p style={noteStyle}>{t('wizard:classicGhoul.overdosingHint', 'Overdosing: a ghoul can force down one extra point per dot of Stamina (a Stamina roll, difficulty 8), at a price (Fatal Addiction).')}</p>
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.story} title={t('wizard:classic.storyTitle', 'Story & merits')} subtitle={t('wizard:classic.storySub', 'Background narrative and structured merits / flaws.')} accent="var(--sr-arcane-500)">
            {inlineErr(S.story)}
            <label htmlFor="classic-ghoul-background" style={labelStyle}>
              {t('wizard:classic.backgroundStory', 'Background & hooks')}
            </label>
            <textarea
              id="classic-ghoul-background"
              value={f.background}
              onChange={(e) => f.setBackground(e.target.value)}
              rows={6}
              placeholder={t('wizard:classicGhoul.backgroundPlaceholder', 'How the domitor found you, what you do for it, what you would do for the next drink…')}
              style={{ ...inputStyle, marginBottom: '20px', resize: 'vertical', fontFamily: 'var(--sr-font-body)', lineHeight: 1.6 }}
            />
            <p style={noteStyle}>{t('wizard:classicGhoul.meritsHint', 'Fatal Addiction recommends some Vampire Merits and Flaws for ghouls, bars others (no Kindred ties, Deep Sleeper, Eat Food, Light-Sensitive…) and adds its own. Flaws give up to 7 more freebie points.')}</p>
            <MeritFlawRows rows={f.meritRows} setRows={f.setMeritRows} globalNotes={f.meritNotes} setGlobalNotes={f.setMeritNotes} />
          </ResponsiveSheetBlock>

          <ResponsiveSheetBlock sectionId={S.freebies} title={<Term id="freebie" />} subtitle={t('wizard:classicGhoul.freebiesSub', '21 points (+ up to 7 from Flaws) to raise anything above the creation budgets; a Discipline dot costs 10.')} accent={ACCENT}>
            {inlineErr(S.freebies)}
            <FreebieSummary freebies={freebies} freebieMode={f.freebieMode} setFreebieMode={f.setFreebieMode} isVampire costs={GHOUL_FREEBIE_RULES.costs} base={GHOUL_FREEBIE_RULES.points} />
          </ResponsiveSheetBlock>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '24px', justifyContent: 'space-between' }}>
            <button type="button" onClick={onCancel} style={{ ...smallButton, padding: '10px 18px', borderRadius: '8px' }}>
              {t('wizard:cancel', 'Cancel')}
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={handleSubmit}
              style={{
                padding: '10px 22px',
                background: submitting ? 'var(--sr-night-500)' : 'var(--sr-arcane-500)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: submitting ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                fontFamily: 'var(--sr-font-display)',
              }}
            >
              {submitting ? t('wizard:submitting', 'Sealing sheet…') : t('wizard:classicGhoul.submit', 'Create the ghoul')}
            </button>
          </div>
        </div>
      </GothicBox>
    </div>
  );
}

import { useId, useState } from 'react';
import { Button, Checkbox, Input, Panel, Select, Textarea } from '../../design';
import { V5_AGE_BRACKETS } from '../../characterSheet/v5/constants';
import { bookEntries, clanNames, predatorNames } from '../../characterSheet/v5/rulesData';
import { useV5Catalog } from '../../rules/v5Catalog';
import { CORE_BOOK, CREATION_AGES, normalizeCreationSettings } from '../../characterSheet/v5/creationSettings';
import { t } from '../../i18n';

/**
 * One "allowed" list: every box ticked is stored as null (everything allowed, including what
 * later catalogs add); at least one box must stay ticked. `locked`: names always allowed (ticked
 * and disabled, kept in every list); `noteOf`: a short note after a label (in the UI language);
 * `hint`: a line under the boxes.
 */
function AllowedList({ legend, names, labelOf = (n) => n, noteOf = null, hint = null, locked = [], value, onChange }) {
  const hintId = useId();
  if (!names.length) return null;
  const ticked = value ? [...locked.filter((n) => !value.includes(n)), ...value] : names;
  // Stored names this list doesn't show (e.g. added through the API) are kept as they are.
  const unknown = (value || []).filter((n) => !names.includes(n));
  const toggle = (name, on) => {
    if (locked.includes(name)) return;
    const next = on ? [...ticked, name] : ticked.filter((n) => n !== name);
    if (!next.some((n) => names.includes(n))) return;
    onChange(names.every((n) => next.includes(n)) && !unknown.length ? null : [...names.filter((n) => next.includes(n)), ...unknown]);
  };
  return (
    <fieldset className="sr-creation-rules__list" aria-describedby={hint ? hintId : undefined}>
      <legend>{legend}</legend>
      <div className="sr-creation-rules__grid">
        {names.map((n) => (
          <Checkbox
            key={n}
            label={
              <>
                <span lang="en">{labelOf(n)}</span>
                {noteOf && noteOf(n) ? <span className="sr-muted sr-small"> · {noteOf(n)}</span> : null}
              </>
            }
            checked={ticked.includes(n)}
            disabled={locked.includes(n)}
            onChange={(e) => toggle(n, e.target.checked)}
          />
        ))}
      </div>
      {hint ? (
        <p id={hintId} className="sr-muted sr-small">
          {hint}
        </p>
      ) : null}
    </fieldset>
  );
}

/**
 * The Storyteller's creation rules for a V5 chronicle (campaigns.creation_settings): which books
 * the forge takes its catalog entries from (allowed_books, core books first), which clans,
 * predator types and ages it offers, a cap on Flaws, the Humanity 8 fledgling option, house
 * rules shown at the top of the forge, how many points a player may save for later and who
 * approves spending them (st_mode: a human Storyteller, or the AI Storyteller's rule check).
 * `suggestAi`: the Storyteller plays a character here, so the AI mode is suggested.
 */
export default function CreationRulesPanel({ campaign, saving, onSave, suggestAi = false }) {
  useV5Catalog();
  const [s, setS] = useState(() => normalizeCreationSettings(campaign.creation_settings));
  const set = (patch) => setS((prev) => ({ ...prev, ...patch }));
  const [flawsText, setFlawsText] = useState(() => (s.flaws_max_dots == null ? '' : String(s.flaws_max_dots)));
  const [capText, setCapText] = useState(() => String(s.saved_points.advantage_dots_cap));
  const modeHintId = useId();
  const suggestId = useId();
  const showSuggest = suggestAi && s.st_mode === 'human';
  const books = bookEntries();
  const bookOf = Object.fromEntries(books.map((b) => [b.book_id, b]));
  // The server refuses book ids its catalog doesn't list: a stored one it dropped since goes; every book = null.
  const cleanBooks = (list) => {
    if (!list || !books.length) return list;
    const known = list.filter((id) => bookOf[id]);
    return books.every((b) => known.includes(b.book_id)) ? null : known;
  };
  const bookNote = (id) =>
    [
      Number.isFinite(bookOf[id]?.tier) ? t('chronicle:creation.bookTier', 'Tier {{tier}}', { tier: bookOf[id].tier }) : '',
      id === CORE_BOOK ? t('chronicle:creation.bookCore', 'always allowed (the core rules)') : '',
    ]
      .filter(Boolean)
      .join(' · ');
  const submit = (e) => {
    e.preventDefault();
    const n = parseInt(flawsText, 10);
    const cap = parseInt(capText, 10);
    onSave({
      ...s,
      allowed_books: cleanBooks(s.allowed_books),
      flaws_max_dots: Number.isFinite(n) ? Math.max(2, Math.min(20, n)) : null,
      saved_points: {
        ...s.saved_points,
        advantage_dots_cap: Number.isFinite(cap) ? Math.max(0, Math.min(20, cap)) : s.saved_points.advantage_dots_cap,
      },
    });
  };
  return (
    <Panel title={t('chronicle:creation.title', 'Character creation rules')} icon="scroll">
      <form className="sr-form" onSubmit={submit}>
        <p className="sr-muted sr-small">
          {t('chronicle:creation.intro', 'What the V5 forge offers new characters in this chronicle. Characters already made are not changed.')}
        </p>
        <AllowedList
          legend={t('chronicle:creation.books', 'Allowed books')}
          names={books.map((b) => b.book_id)}
          labelOf={(id) => bookOf[id]?.title || id}
          noteOf={bookNote}
          locked={bookOf[CORE_BOOK] ? [CORE_BOOK] : []}
          hint={t('chronicle:creation.booksHint', 'The forge offers clans, predator types, powers, rituals, ceremonies, Advantages and loresheets from the ticked books only; one printed in several books needs one of them. With every book ticked, books added to the catalog later count too.')}
          value={s.allowed_books}
          onChange={(v) => set({ allowed_books: v })}
        />
        <AllowedList
          legend={t('chronicle:creation.clans', 'Allowed clans')}
          names={clanNames()}
          value={s.allowed_clans}
          onChange={(v) => set({ allowed_clans: v })}
        />
        <AllowedList
          legend={t('chronicle:creation.predators', 'Allowed predator types')}
          names={predatorNames()}
          value={s.allowed_predators}
          onChange={(v) => set({ allowed_predators: v })}
        />
        <AllowedList
          legend={t('chronicle:creation.ages', 'Allowed ages')}
          names={CREATION_AGES}
          labelOf={(a) => V5_AGE_BRACKETS[a].label}
          value={s.allowed_ages}
          onChange={(v) => set({ allowed_ages: v })}
        />
        <Input
          type="number"
          min={2}
          max={20}
          label={t('chronicle:creation.flawsMax', 'Most Flaw dots a player may take (empty = no limit)')}
          value={flawsText}
          onChange={(e) => setFlawsText(e.target.value)}
          fieldClassName="sr-field--short"
        />
        <p className="sr-muted sr-small">
          {t('chronicle:creation.flawsHint', 'Ancillae take 4 Flaw dots, so a limit under 4 needs ancillae left out.')}
        </p>
        <Checkbox
          label={t('chronicle:creation.fledgling', 'Offer just-Embraced fledglings the Humanity 8 start')}
          checked={s.fledgling_humanity_8}
          onChange={(e) => set({ fledgling_humanity_8: e.target.checked })}
        />
        <fieldset className="sr-creation-rules__list sr-creation-rules__fields">
          <legend>{t('chronicle:creation.savedTitle', 'Saved points and approvals')}</legend>
          <Input
            type="number"
            min={0}
            max={20}
            label={t('chronicle:creation.savedCap', 'Advantage dots a player may leave unspent and save for later (0–20)')}
            value={capText}
            onChange={(e) => setCapText(e.target.value)}
            fieldClassName="sr-field--short"
          />
          <Checkbox
            label={t('chronicle:creation.savedSpecialty', 'Players may save the free specialty of their choice')}
            checked={s.saved_points.allow_specialty}
            onChange={(e) => set({ saved_points: { ...s.saved_points, allow_specialty: e.target.checked } })}
          />
          <Select
            label={t('chronicle:creation.stMode', 'Who approves spending saved points')}
            value={s.st_mode}
            aria-describedby={showSuggest ? `${modeHintId} ${suggestId}` : modeHintId}
            onChange={(e) => set({ st_mode: e.target.value })}
            options={[
              { value: 'human', label: t('chronicle:creation.stModeHuman', 'A human Storyteller (you or staff)') },
              { value: 'ai', label: t('chronicle:creation.stModeAi', 'The AI Storyteller (rule check)') },
            ]}
          />
          <p id={modeHintId} className="sr-muted sr-small">
            {s.st_mode === 'ai'
              ? t('chronicle:creation.stModeAiHint', 'Spends that follow the rules are approved at once by a fixed rule check (not the language model) and logged under Approvals, where you can reverse any of them. House rules always wait for you.')
              : t('chronicle:creation.stModeHumanHint', 'Every spend waits for you under Approvals.')}
          </p>
          {showSuggest ? (
            <p id={suggestId} className="sr-warnbox">
              {t('chronicle:creation.stModeSuggest', 'You play a character in this chronicle yourself. With the AI Storyteller, the rule check approves your own spends instead of you.')}
            </p>
          ) : null}
        </fieldset>
        <Textarea
          label={t('chronicle:creation.houseRules', 'House rules (shown at the top of the forge)')}
          value={s.house_rules}
          maxLength={2000}
          rows={4}
          onChange={(e) => set({ house_rules: e.target.value })}
        />
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={saving}>
            {t('chronicle:creation.save', 'Save creation rules')}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

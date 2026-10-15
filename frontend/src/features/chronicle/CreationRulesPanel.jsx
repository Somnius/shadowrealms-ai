import { useState } from 'react';
import { Button, Checkbox, Input, Panel, Textarea } from '../../design';
import { V5_AGE_BRACKETS, V5_CLAN_NAMES, V5_PREDATOR_TYPES } from '../../characterSheet/v5/constants';
import { CREATION_AGES, normalizeCreationSettings } from '../../characterSheet/v5/creationSettings';
import { t } from '../../i18n';

const PREDATOR_NAMES = V5_PREDATOR_TYPES.map((p) => p.name);

/**
 * One "allowed" list: every box ticked is stored as null (everything allowed, including what
 * later catalogs add); at least one box must stay ticked.
 */
function AllowedList({ legend, names, labelOf = (n) => n, value, onChange }) {
  const ticked = value || names;
  const toggle = (name, on) => {
    const next = on ? [...ticked, name] : ticked.filter((n) => n !== name);
    if (!next.length) return;
    onChange(names.every((n) => next.includes(n)) ? null : names.filter((n) => next.includes(n)));
  };
  return (
    <fieldset className="sr-creation-rules__list">
      <legend>{legend}</legend>
      <div className="sr-creation-rules__grid">
        {names.map((n) => (
          <Checkbox
            key={n}
            label={<span lang="en">{labelOf(n)}</span>}
            checked={ticked.includes(n)}
            onChange={(e) => toggle(n, e.target.checked)}
          />
        ))}
      </div>
    </fieldset>
  );
}

/**
 * The Storyteller's creation rules for a V5 chronicle (campaigns.creation_settings): which clans,
 * predator types and ages the forge offers, a cap on Flaws, the Humanity 8 fledgling option and
 * house rules shown at the top of the forge.
 */
export default function CreationRulesPanel({ campaign, saving, onSave }) {
  const [s, setS] = useState(() => normalizeCreationSettings(campaign.creation_settings));
  const set = (patch) => setS((prev) => ({ ...prev, ...patch }));
  const submit = (e) => {
    e.preventDefault();
    onSave(s);
  };
  return (
    <Panel title={t('chronicle:creation.title', 'Character creation rules')} icon="scroll">
      <form className="sr-form" onSubmit={submit}>
        <p className="sr-muted sr-small">
          {t('chronicle:creation.intro', 'What the V5 forge offers new characters in this chronicle. Characters already made are not changed.')}
        </p>
        <AllowedList
          legend={t('chronicle:creation.clans', 'Allowed clans')}
          names={V5_CLAN_NAMES}
          value={s.allowed_clans}
          onChange={(v) => set({ allowed_clans: v })}
        />
        <AllowedList
          legend={t('chronicle:creation.predators', 'Allowed predator types')}
          names={PREDATOR_NAMES}
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
          value={s.flaws_max_dots ?? ''}
          onChange={(e) => {
            const n = parseInt(e.target.value, 10);
            set({ flaws_max_dots: Number.isFinite(n) ? Math.max(2, Math.min(20, n)) : null });
          }}
          fieldClassName="sr-field--short"
        />
        <Checkbox
          label={t('chronicle:creation.fledgling', 'Offer just-Embraced fledglings the Humanity 8 start')}
          checked={s.fledgling_humanity_8}
          onChange={(e) => set({ fledgling_humanity_8: e.target.checked })}
        />
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

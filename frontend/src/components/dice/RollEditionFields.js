import { V5_DIFFICULTY_TABLE, V5_MAX_HUNGER } from '../../rules/v5Rules';
import { t } from '../../i18n';
import { Term } from '../../i18n/glossary';
import { Button, Checkbox, Glyph, Select } from '../../design';
import './dice.css';

/** Help text for the roll modal, per edition. */
export function RollHelp({ edition }) {
  if (edition === 'v5') {
    return (
      <p className="sr-roll__help">
        <Glyph name="d10-hunger" size={16} className="sr-roll__help-glyph" />
        <strong>V5</strong>:{' '}
        {t(
          'dice:help.v5',
          'pool of d10; each 6+ is a success and every pair of 10s counts as 4. Difficulty is the number of successes you need. Your current Hunger replaces that many dice with Hunger dice (messy criticals and bestial failures). After the roll you can spend Willpower to reroll up to 3 normal dice.'
        )}
      </p>
    );
  }
  return (
    <p className="sr-roll__help">
      <Glyph name="d10" size={16} className="sr-roll__help-glyph" />
      <strong>{t('dice:edition.classicLong', 'Classic (Revised)')}</strong>:{' '}
      {t(
        'dice:help.classic',
        'pool of d10, difficulty (target number) usually 6–9. Each die ≥ difficulty is a success; 1s cancel successes. A botch needs no successes at all and at least one 1. Specialty: 10s are rerolled for more successes. Willpower: one automatic success (declare before rolling).'
      )}
    </p>
  );
}

/**
 * Edition-specific roll inputs.
 * classic: difficulty (TN 2–10), specialty, willpower
 * v5: difficulty (successes needed 0–10), hunger 0–5, rouse check button
 */
export default function RollEditionFields({
  edition,
  disabled,
  classicDifficulty,
  setClassicDifficulty,
  specialty,
  setSpecialty,
  willpower,
  setWillpower,
  v5Difficulty,
  setV5Difficulty,
  hunger,
  setHunger,
  hungerSource,
  onRouse,
  rousing,
}) {
  if (edition === 'v5') {
    return (
      <>
        <Select
          id="roll-v5-difficulty"
          label={t('dice:field.v5Difficulty', 'Difficulty (successes needed)')}
          value={v5Difficulty}
          onChange={(e) => setV5Difficulty(Number(e.target.value))}
          disabled={disabled}
        >
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
            <option key={n} value={n}>
              {n}
              {n === 0 ? ` ${t('dice:field.justCount', '(just count successes)')}` : ''}
              {V5_DIFFICULTY_TABLE[String(Math.min(n, 7))] && n > 0
                ? ` — ${t(`dice:v5difficulty.${Math.min(n, 7)}`, V5_DIFFICULTY_TABLE[String(Math.min(n, 7))])}`
                : ''}
            </option>
          ))}
        </Select>
        <div className="sr-roll__hunger">
          <Select
            id="roll-v5-hunger"
            label={
              <>
                <Term id="hunger" /> {hungerSource ? <span className="sr-roll__source">({hungerSource})</span> : null}
              </>
            }
            value={hunger}
            onChange={(e) => setHunger(Number(e.target.value))}
            disabled={disabled}
            fieldClassName="sr-roll__hunger-field"
          >
            {Array.from({ length: V5_MAX_HUNGER + 1 }, (_, n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
          <span className="sr-roll__hunger-track" aria-hidden="true">
            {Array.from({ length: V5_MAX_HUNGER }, (_, i) => (
              <Glyph key={i} name="blood-drop" size={18} className={i < hunger ? 'is-full' : 'is-empty'} />
            ))}
          </span>
          {onRouse ? (
            <Button
              variant="danger"
              size="sm"
              icon="blood-drop"
              onClick={onRouse}
              disabled={disabled}
              loading={rousing}
              loadingLabel={t('dice:field.rousing', 'Rousing…')}
              title={t('dice:field.rouseHint', 'One die: 6+ means no Hunger gain, otherwise Hunger +1')}
              className="sr-roll__rouse"
            >
              <span lang="en">{t('dice:field.rouse', 'Rouse check')}</span>
            </Button>
          ) : null}
        </div>
      </>
    );
  }
  return (
    <>
      <Select
        id="roll-classic-difficulty"
        label={t('dice:field.classicDifficulty', 'Difficulty (target number, 2–10)')}
        value={classicDifficulty}
        onChange={(e) => setClassicDifficulty(Number(e.target.value))}
        disabled={disabled}
      >
        {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
          <option key={n} value={n}>
            {n}
            {n === 6 ? ` ${t('dice:field.commonDefault', '(common default)')}` : ''}
          </option>
        ))}
      </Select>
      <Checkbox
        label={t('dice:field.specialty', 'Specialty (10s are rerolled for extra successes)')}
        checked={specialty}
        onChange={(e) => setSpecialty(e.target.checked)}
        disabled={disabled}
      />
      <Checkbox
        label={t('dice:field.willpower', 'Spend Willpower (+1 automatic success, can’t be cancelled)')}
        checked={willpower}
        onChange={(e) => setWillpower(e.target.checked)}
        disabled={disabled}
      />
    </>
  );
}

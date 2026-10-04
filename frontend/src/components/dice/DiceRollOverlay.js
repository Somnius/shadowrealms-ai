import { useEffect } from 'react';
import { Badge, Glyph, RollFx, rollMood, useReducedMotionPref } from '../../design';
import DiceFace from './DiceFace';
import OutcomeBadges from './OutcomeBadges';
import { classicOutcome, classicSummaryLine } from '../../dice/classicDiceDisplay';
import { v5Badges, v5SummaryLine } from '../../dice/v5DiceDisplay';
import { t } from '../../i18n';
import './dice.css';

/** Small numeric key from a roll id (seeds the drip / crack shapes, so each roll looks different). */
export function hashKey(id) {
  const str = String(id || '');
  let h = 0;
  for (let i = 0; i < str.length; i += 1) h = (h * 31 + str.charCodeAt(i)) % 9973;
  return h;
}

/** Text read out by screen readers once the roll settles. */
export function overlayAnnouncement(overlay) {
  if (!overlay?.settled || !overlay.result) return '';
  const v5 = overlay.rulesEdition === 'v5';
  const labels = v5 ? v5Badges(overlay.result).map((b) => b.label) : [classicOutcome(overlay.result).label];
  const summary = v5 ? v5SummaryLine(overlay.result) : classicSummaryLine(overlay.result);
  return t('dice:overlay.announce', 'Dice result: {{labels}}. {{summary}}.', { labels: labels.join(', '), summary });
}

/**
 * Full-screen dice overlay. While rolling, the d10s tumble and their faces flicker; once
 * `settled`, they land one after another, the outcome is shown, and the result plays its effect:
 * blood drips and a crack for a botch / bestial failure, a gold-to-blood sweep for a messy
 * critical, a gold flare for a critical / exceptional success. Reduced motion: no tumble,
 * final faces at once, the effects' static end state.
 *
 * `overlay` fields: visible, animationId, settled, rulesEdition, difficulty, diceFinal,
 * diceRolling, hungerFlags, extraDiceCount, specialtyRerolls (classic), result.
 *
 * A11y: it never takes focus, because rolls from other players pop up while you may be
 * typing and stealing focus would eat your keystrokes. Escape (or a click once settled)
 * dismisses it, and the outcome is announced through a polite live region that stays
 * mounted (so screen readers pick up the change).
 */
export default function DiceRollOverlay({ overlay, onDismiss }) {
  const visible = Boolean(overlay?.visible);
  const reduced = useReducedMotionPref();

  useEffect(() => {
    if (!visible) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onDismiss?.();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
    // Re-run only when the overlay opens/closes or a new roll starts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, overlay?.animationId]);

  // Kept after the overlay hides, so a queued announcement isn't cut short.
  const announcement = overlayAnnouncement(overlay);
  const liveRegion = (
    <div role="status" aria-live="polite" aria-atomic="true" data-testid="dice-overlay-live" className="sr-visually-hidden">
      {announcement}
    </div>
  );
  if (!visible) return liveRegion;
  const v5 = overlay.rulesEdition === 'v5';
  const settled = Boolean(overlay.settled);
  const summary = v5 ? v5SummaryLine(overlay.result) : classicSummaryLine(overlay.result);
  const rerolls = !v5 && Array.isArray(overlay.specialtyRerolls) ? overlay.specialtyRerolls : [];
  const mood = settled ? rollMood({ rules_edition: v5 ? 'v5' : 'classic', ...overlay.result }) : null;
  const size = overlay.diceFinal.length > 6 ? 48 : 56;
  return (
    <>
      {liveRegion}
      <div
        role="presentation"
        className={`sr-diceov${settled ? ' is-settled' : ' is-rolling'}`}
        data-mood={mood || undefined}
        onClick={settled ? onDismiss : undefined}
      >
        <div className="sr-diceov__backdrop" aria-hidden="true" />
        <div
          role="dialog"
          aria-label={
            settled
              ? t('dice:overlay.resultLabel', 'Dice roll result (Escape to close)')
              : t('dice:overlay.rollingLabel', 'Dice rolling (Escape to close)')
          }
          data-testid="dice-overlay"
          className="sr-diceov__panel"
          data-mood={mood || undefined}
        >
          <div className="sr-diceov__head">
            <div className="sr-diceov__title">
              <Glyph name={settled ? 'd10-crit' : 'dice'} size={22} className="sr-diceov__title-glyph" />
              <span>{settled ? t('dice:overlay.result', 'Result') : t('dice:overlay.rolling', 'Rolling…')}</span>
              <Badge edition={v5 ? t('dice:edition.v5', 'V5') : t('dice:edition.classic', 'Classic')} tone={v5 ? 'blood' : 'neutral'} />
            </div>
            <div className="sr-diceov__summary">
              {settled
                ? summary
                : v5
                ? t('dice:overlay.difficulty', 'Difficulty {{n}}', { n: overlay.difficulty })
                : t('dice:summary.tn', 'TN {{tn}}', { tn: overlay.difficulty })}
            </div>
          </div>

          <div className="sr-diceov__tray">
            {overlay.diceFinal.map((_, i) => {
              const v = settled ? overlay.diceFinal[i] : overlay.diceRolling[i] ?? overlay.diceFinal[i] ?? 1;
              return (
                <DiceFace
                  key={`${overlay.animationId}-die-${i}`}
                  value={v}
                  edition={overlay.rulesEdition}
                  difficulty={overlay.difficulty}
                  hunger={Boolean(overlay.hungerFlags?.[i])}
                  size={size}
                  rolling={!settled}
                  landed={settled}
                  index={i}
                  hidden={!settled && reduced}
                />
              );
            })}
            {settled && rerolls.length > 0 && (
              <div
                role="group"
                aria-label={t('dice:overlay.rerollsLabel', 'Specialty rerolls: {{list}}', { list: rerolls.join(', ') })}
                data-testid="specialty-rerolls"
                className="sr-diceov__rerolls"
              >
                <span className="sr-diceov__rerolls-label">
                  <Glyph name="reroll" size={14} /> {t('dice:overlay.rerollsTitle', 'Specialty rerolls')}
                </span>
                {rerolls.map((v, i) => (
                  <DiceFace
                    key={`${overlay.animationId}-rr-${i}`}
                    value={v}
                    edition="classic"
                    difficulty={overlay.difficulty}
                    reroll
                    size={Math.round(size * 0.8)}
                    landed
                    index={overlay.diceFinal.length + i}
                  />
                ))}
              </div>
            )}
            {overlay.extraDiceCount > 0 && (
              <div className="sr-diceov__more">{t('dice:overlay.more', '+{{count}} more', { count: overlay.extraDiceCount })}</div>
            )}
          </div>

          <div className="sr-diceov__foot">
            {settled ? (
              <OutcomeBadges result={overlay.result} size="lg" />
            ) : (
              <div className="sr-diceov__hint">
                {v5 && overlay.hungerFlags?.some(Boolean) ? `${t('dice:overlay.redHunger', 'Red dice are Hunger dice.')} ` : ''}
                {t('dice:overlay.resolves', 'The roll resolves right after the dice stop.')}
              </div>
            )}
          </div>
          {settled ? <RollFx mood={mood} playKey={hashKey(overlay.animationId)} /> : null}
        </div>
      </div>
    </>
  );
}

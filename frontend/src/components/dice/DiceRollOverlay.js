import React, { useEffect } from 'react';
import DiceFace from './DiceFace';
import OutcomeBadges from './OutcomeBadges';
import { classicOutcome, classicSummaryLine } from '../../dice/classicDiceDisplay';
import { v5Badges, v5SummaryLine } from '../../dice/v5DiceDisplay';
import { t } from '../../i18n';

const SR_ONLY = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: 0,
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

/** Text read out by screen readers once the roll settles. */
export function overlayAnnouncement(overlay) {
  if (!overlay?.settled || !overlay.result) return '';
  const v5 = overlay.rulesEdition === 'v5';
  const labels = v5 ? v5Badges(overlay.result).map((b) => b.label) : [classicOutcome(overlay.result).label];
  const summary = v5 ? v5SummaryLine(overlay.result) : classicSummaryLine(overlay.result);
  return t('dice:overlay.announce', 'Dice result: {{labels}}. {{summary}}.', { labels: labels.join(', '), summary });
}

/**
 * Full-screen dice overlay. While rolling, faces flicker; once `settled`, the final dice
 * and the outcome badges (edition-specific) are shown briefly.
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
    <div role="status" aria-live="polite" aria-atomic="true" data-testid="dice-overlay-live" style={SR_ONLY}>
      {announcement}
    </div>
  );
  if (!visible) return liveRegion;
  const v5 = overlay.rulesEdition === 'v5';
  const summary = v5 ? v5SummaryLine(overlay.result) : classicSummaryLine(overlay.result);
  const rerolls = !v5 && Array.isArray(overlay.specialtyRerolls) ? overlay.specialtyRerolls : [];
  return (
    <>
    {liveRegion}
    <div
      role="presentation"
      onClick={overlay.settled ? onDismiss : undefined}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 3000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.35)',
        padding: '16px',
      }}
    >
      <div
        role="dialog"
        aria-label={
          overlay.settled
            ? t('dice:overlay.resultLabel', 'Dice roll result (Escape to close)')
            : t('dice:overlay.rollingLabel', 'Dice rolling (Escape to close)')
        }
        data-testid="dice-overlay"
        style={{
          outline: 'none',
          width: 'min(760px, 100%)',
          background: 'linear-gradient(135deg, rgba(157, 78, 221, 0.18) 0%, rgba(233, 69, 96, 0.12) 100%)',
          border: '2px solid rgba(233, 69, 96, 0.35)',
          borderRadius: '14px',
          boxShadow: '0 20px 70px rgba(0,0,0,0.65)',
          padding: '18px 18px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px', marginBottom: '10px', flexWrap: 'wrap' }}>
          <div style={{ color: '#e94560', fontFamily: 'Cinzel, serif', fontSize: '18px', fontWeight: 700 }}>
            <i className="fas fa-dice" style={{ marginRight: '10px' }} />
            {overlay.settled ? t('dice:overlay.result', 'Result') : t('dice:overlay.rolling', 'Rolling…')}
            <span style={{ marginLeft: '10px', fontSize: '12px', color: '#94a3b8' }}>{v5 ? t('dice:edition.v5', 'V5') : t('dice:edition.classic', 'Classic')}</span>
          </div>
          <div style={{ color: '#b5b5c3', fontFamily: 'Crimson Text, serif', fontSize: '12px' }}>
            {overlay.settled
              ? summary
              : v5
              ? t('dice:overlay.difficulty', 'Difficulty {{n}}', { n: overlay.difficulty })
              : t('dice:summary.tn', 'TN {{tn}}', { tn: overlay.difficulty })}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
          {overlay.diceFinal.map((_, i) => {
            const v = overlay.settled
              ? overlay.diceFinal[i]
              : overlay.diceRolling[i] ?? overlay.diceFinal[i] ?? 1;
            return (
              <DiceFace
                key={`${overlay.animationId}-die-${i}`}
                value={v}
                edition={overlay.rulesEdition}
                difficulty={overlay.difficulty}
                hunger={Boolean(overlay.hungerFlags?.[i])}
              />
            );
          })}
          {overlay.settled && rerolls.length > 0 && (
            <div
              role="group"
              aria-label={t('dice:overlay.rerollsLabel', 'Specialty rerolls: {{list}}', { list: rerolls.join(', ') })}
              data-testid="specialty-rerolls"
              style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center', paddingLeft: '10px', borderLeft: '1px dashed #fbbf24' }}
            >
              <span style={{ color: '#fbbf24', fontFamily: 'Crimson Text, serif', fontSize: '12px' }}>
                ↻ {t('dice:overlay.rerollsTitle', 'Specialty rerolls')}
              </span>
              {rerolls.map((v, i) => (
                <DiceFace
                  key={`${overlay.animationId}-rr-${i}`}
                  value={v}
                  edition="classic"
                  difficulty={overlay.difficulty}
                  reroll
                />
              ))}
            </div>
          )}
          {overlay.extraDiceCount > 0 && (
            <div style={{ alignSelf: 'center', color: '#8b8b9f', fontFamily: 'Crimson Text, serif', fontSize: '14px', marginLeft: '4px' }}>
              {t('dice:overlay.more', '+{{count}} more', { count: overlay.extraDiceCount })}
            </div>
          )}
        </div>

        <div style={{ marginTop: '12px' }}>
          {overlay.settled ? (
            <OutcomeBadges result={overlay.result} />
          ) : (
            <div style={{ color: '#b5b5c3', fontFamily: 'Crimson Text, serif', fontSize: '12px', textAlign: 'center' }}>
              {v5 && overlay.hungerFlags?.some(Boolean) ? `${t('dice:overlay.redHunger', 'Red dice are Hunger dice.')} ` : ''}
              {t('dice:overlay.resolves', 'The roll resolves right after the dice stop.')}
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}

import { useId, useMemo, useRef } from 'react';
import { LazyMotion, domAnimation, m } from 'motion/react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { line, curveNatural } from 'd3-shape';
import DieFace from '../glyphs/DieFace';
import Glyph from '../glyphs/Glyph';
import { BloodDrip } from './Atmosphere';
import { analyzeClassic, analyzeV5, outcomeLabels } from './diceAnalysis';
import { t } from '../../i18n';
import { useInView, useReducedMotionPref } from '../motion';
import { cx } from '../components/internal';
import './atmosphere.css';

const DIE = 40;
const ROW_GAP = 26; // room above each row for crit-pair arcs
const PER_ROW_MAX = 10;
const OUTCOME_GLYPH = {
  'messy-critical': 'fangs',
  critical: 'd10-crit',
  success: 'd10',
  'bestial-failure': 'd10-hunger',
  'total-failure': 'skull',
  failure: 'eye-shut',
  botch: 'd10-botch',
  exceptional: 'd10-crit',
  phenomenal: 'd10-crit',
};

/** Normalise props / an API roll_result into analysis input. */
function analyze(props) {
  const { result, edition } = props;
  if (result) {
    const ed = result.rules_edition === 'v5' || edition === 'v5' ? 'v5' : 'classic';
    if (ed === 'v5') {
      return analyzeV5({
        normal: result.normal_dice || [],
        hunger: result.hunger_dice || [],
        difficulty: result.difficulty != null ? result.difficulty : 1,
        flags: result,
      });
    }
    return analyzeClassic({
      dice: result.results || result.dice || [],
      rerolls: result.specialty_rerolls || [],
      difficulty: result.difficulty != null ? result.difficulty : 6,
      willpower: !!result.willpower,
      flags: result,
    });
  }
  if (edition === 'v5') {
    return analyzeV5({ normal: props.normal, hunger: props.hunger, difficulty: props.difficulty != null ? props.difficulty : 1 });
  }
  return analyzeClassic({
    dice: props.dice,
    rerolls: props.rerolls,
    difficulty: props.difficulty != null ? props.difficulty : 6,
    willpower: props.willpower,
  });
}

export function describeRoll(a, labels = outcomeLabels()) {
  const outcome = labels[a.outcome] || a.outcome;
  if (a.edition === 'v5') {
    const hungerCount = a.dice.filter((d) => d.hunger).length;
    const parts = [
      t('dice:viz.dice', { one: '{{count}} die', other: '{{count}} dice' }, { count: a.dice.length }) +
        (hungerCount ? t('dice:viz.hungerPart', ', {{count}} Hunger', { count: hungerCount }) : ''),
      t('dice:viz.successesOf', { one: '{{count}} success of {{difficulty}} needed', other: '{{count}} successes of {{difficulty}} needed' }, { count: a.successes, difficulty: a.difficulty }),
    ];
    if (a.pairs.length) parts.push(t('dice:viz.pairs', { one: '{{count}} critical pair', other: '{{count}} critical pairs' }, { count: a.pairs.length }));
    return `${outcome}. ${parts.join('; ')}.`;
  }
  const parts = [
    t('dice:viz.diceAt', { one: '{{count}} die at difficulty {{difficulty}}', other: '{{count}} dice at difficulty {{difficulty}}' }, { count: a.dice.length, difficulty: a.difficulty }),
    t('dice:viz.net', { one: '{{count}} net success', other: '{{count}} net successes' }, { count: a.successes }),
  ];
  if (a.ones) parts.push(t('dice:viz.ones', { one: '{{count}} one', other: '{{count}} ones' }, { count: a.ones }));
  if (a.willpower) parts.push(t('dice:viz.willpower', 'Willpower spent'));
  return `${outcome}. ${parts.join('; ')}.`;
}

/**
 * DiceRollViz: d10 pool visualisation (d3-scale for layout, d3-shape for the crit-pair arcs,
 * React renders the SVG, Motion staggers the reveal).
 *
 * Either pass the API `result` (roll_result of /roll, V5 or classic), or raw dice:
 *   V5:      edition="v5" normal={[...]} hunger={[...]} difficulty={successes needed}
 *   classic: edition="classic" dice={[...]} difficulty={TN} rerolls={[...]} willpower
 * Accessible: a <figure> whose caption states the outcome in words; the dice values are listed
 * for screen readers; the SVG itself is decorative.
 * Reduced motion: no tumble, no drip — final state at once.
 */
export default function DiceRollViz(props) {
  const { title, labels = outcomeLabels(), showMeter = true, drip = true, rollKey = 0, className } = props;
  const reduced = useReducedMotionPref();
  const ref = useRef(null);
  const inView = useInView(ref);
  const capId = useId();
  const a = useMemo(
    () => analyze(props),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.result, props.edition, props.normal, props.hunger, props.dice, props.rerolls, props.difficulty, props.willpower]
  );

  const n = a.dice.length;
  const perRow = Math.max(1, Math.min(PER_ROW_MAX, n));
  const rows = Math.max(1, Math.ceil(n / perRow));
  const width = Math.max(perRow * (DIE + 8), 200);
  const x = scaleBand()
    .domain(Array.from({ length: perRow }, (_, i) => i))
    .range([0, width])
    .paddingInner(0.15)
    .paddingOuter(0.05);
  const dieSize = Math.min(DIE, x.bandwidth());
  const rowY = (r) => ROW_GAP + r * (dieSize + ROW_GAP);
  const pos = (i) => {
    const r = Math.floor(i / perRow);
    const c = i % perRow;
    return { x: x(c) + (x.bandwidth() - dieSize) / 2, y: rowY(r) };
  };
  const diceHeight = rowY(rows - 1) + dieSize;

  const meterMax = Math.max(a.edition === 'v5' ? a.difficulty : 5, a.successes, 1);
  const meterX = scaleLinear().domain([0, meterMax]).range([0, width]).clamp(true);
  const meterY = diceHeight + 18;
  const height = showMeter ? meterY + 24 : diceHeight + 8;

  const arc = line().curve(curveNatural);
  const pairPaths = a.pairs.map(([i, j]) => {
    const p = pos(i);
    const q = pos(j);
    const x1 = p.x + dieSize / 2;
    const x2 = q.x + dieSize / 2;
    const y1 = p.y - 2;
    const y2 = q.y - 2;
    const lift = Math.min(ROW_GAP - 4, 10 + Math.abs(x2 - x1) * 0.08);
    return arc([
      [x1, y1],
      [(x1 + x2) / 2, Math.min(y1, y2) - lift],
      [x2, y2],
    ]);
  });

  const animate = !reduced && inView;
  const stagger = 0.06;
  const revealEnd = n * stagger + 0.35;
  const caption = describeRoll(a, labels);
  const isFoul = a.outcome === 'bestial-failure' || a.outcome === 'botch';

  return (
    <figure ref={ref} className={cx('sr-dice-viz', `sr-dice-viz--${a.outcome}`, className)} aria-labelledby={capId} data-outcome={a.outcome}>
      {title ? <div className="sr-dice-viz__title">{title}</div> : null}
      <div className="sr-dice-viz__stage">
        <LazyMotion features={domAnimation}>
          <svg
            className="sr-dice-viz__svg"
            viewBox={`0 0 ${width} ${height}`}
            width="100%"
            style={{ maxWidth: width }}
            aria-hidden="true"
            focusable="false"
            key={rollKey}
          >
            {a.dice.map((d, i) => {
              const p = pos(i);
              const face = (
                <DieFace
                  value={d.value}
                  hunger={!!d.hunger}
                  state={d.state}
                  size={dieSize}
                  decorative
                  className={cx(d.paired && 'is-paired', d.reroll && 'is-reroll')}
                />
              );
              return animate ? (
                <m.g
                  key={i}
                  initial={{ opacity: 0, y: -14, rotate: -120, scale: 0.6 }}
                  animate={{ opacity: 1, y: 0, rotate: 0, scale: 1 }}
                  transition={{ duration: 0.45, delay: i * stagger, ease: [0.2, 0.8, 0.2, 1] }}
                  style={{ originX: 0.5, originY: 0.5 }}
                >
                  <g transform={`translate(${p.x} ${p.y})`}>{face}</g>
                </m.g>
              ) : (
                <g key={i} transform={`translate(${p.x} ${p.y})`}>
                  {face}
                </g>
              );
            })}
            {pairPaths.map((d, i) =>
              animate ? (
                <m.path
                  key={`pair-${i}`}
                  d={d}
                  className="sr-dice-viz__pair"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 0.5, delay: revealEnd }}
                />
              ) : (
                <path key={`pair-${i}`} d={d} className="sr-dice-viz__pair" />
              )
            )}
            {showMeter ? (
              <g className="sr-dice-viz__meter" transform={`translate(0 ${meterY})`}>
                <rect className="sr-dice-viz__meter-track" x="0" y="0" width={width} height="6" rx="3" />
                {animate ? (
                  <m.rect
                    className="sr-dice-viz__meter-fill"
                    x="0"
                    y="0"
                    height="6"
                    rx="3"
                    initial={{ width: 0 }}
                    animate={{ width: meterX(a.successes) }}
                    transition={{ duration: 0.6, delay: revealEnd }}
                  />
                ) : (
                  <rect className="sr-dice-viz__meter-fill" x="0" y="0" height="6" rx="3" width={meterX(a.successes)} />
                )}
                {a.edition === 'v5' && a.difficulty > 0 ? (
                  <g transform={`translate(${meterX(a.difficulty)} 0)`}>
                    <path className="sr-dice-viz__mark" d="M0 -5V11" />
                    <text className="sr-dice-viz__mark-label" x={a.difficulty === meterMax ? -4 : 4} y="20" textAnchor={a.difficulty === meterMax ? 'end' : 'start'}>
                      {a.difficulty}
                    </text>
                  </g>
                ) : null}
              </g>
            ) : null}
          </svg>
        </LazyMotion>
        {drip && isFoul ? (
          <div className="sr-dice-viz__drip">
            <BloodDrip playKey={rollKey} drips={6} maxLength={46} />
          </div>
        ) : null}
      </div>
      <figcaption id={capId} className="sr-dice-viz__caption">
        <Glyph name={OUTCOME_GLYPH[a.outcome] || 'd10'} size={20} className="sr-dice-viz__outcome-glyph" />
        <span className="sr-dice-viz__outcome" aria-hidden="true">{labels[a.outcome] || a.outcome}</span>
        <span className="sr-dice-viz__count" aria-hidden="true">
          {a.successes} {a.edition === 'v5' ? `/ ${a.difficulty}` : ''}
        </span>
        <span className="sr-visually-hidden">
          {caption}{' '}
          {t('dice:viz.list', 'Dice: {{list}}.', {
            list: a.dice
              .map((d) => `${d.value}${d.hunger ? t('dice:viz.hungerTag', ' (Hunger)') : ''}${d.reroll ? t('dice:viz.rerollTag', ' (reroll)') : ''}`)
              .join(', '),
          })}
        </span>
      </figcaption>
    </figure>
  );
}

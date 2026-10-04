import { useEffect, useRef, useState } from 'react';
import { Badge, Button, Card, ChronicleSigil, DiceRollViz, DotTrack, Glyph, RollFx, Select, useReducedMotionPref } from '../../design';
import DiceRollOverlay from '../../components/dice/DiceRollOverlay';
import OutcomeBadges from '../../components/dice/OutcomeBadges';
import { classicSummaryLine } from '../../dice/classicDiceDisplay';
import { v5SummaryLine } from '../../dice/v5DiceDisplay';
import { t } from '../../i18n';
import { CLASSIC_OUTCOMES, V5_OUTCOMES, rollClassic, rollV5, seededRandom } from './diceDemo';
import { PillGroup, Section } from './parts';

const ROLL_MS = 1400;

function outcomeOptions(edition) {
  const label = {
    random: t('showcase:editions.random', 'Fate decides'),
    success: edition === 'v5' ? t('dice:outcome.win', 'Win') : t('dice:outcome.success', 'Success'),
    exceptional: t('dice:outcome.exceptional', 'Exceptional success'),
    failure: t('dice:outcome.failure', 'Failure'),
    botch: t('dice:outcome.botch', 'Botch'),
    critical: t('dice:outcome.criticalWin', 'Critical win'),
    messy: t('dice:outcome.messyCritical', 'Messy critical'),
    bestial: t('dice:outcome.bestialFailure', 'Bestial failure'),
    total: t('dice:outcome.totalFailure', 'Total failure'),
  };
  return (edition === 'v5' ? V5_OUTCOMES : CLASSIC_OUTCOMES).map((value) => ({ value, label: label[value] }));
}

/** What the visitor just saw, in words (keyed by the badge key). */
function explain(key) {
  return {
    success: t('showcase:explain.success', 'Hits at or above the difficulty, minus one for every 1. One to four is a plain success.'),
    exceptional: t('showcase:explain.exceptional', 'Five or more net successes: an exceptional success.'),
    failure: t('showcase:explain.failure', 'The 1s cancelled every hit (or nothing hit). Nothing happens, for better or worse.'),
    botch: t('showcase:explain.botch', 'Not one die hit and a 1 showed: a botch. Something goes badly wrong.'),
    win: t('showcase:explain.win', 'Successes (6 or more) meet the Difficulty.'),
    critical: t('showcase:explain.critical', 'A pair of 10s adds two more successes: a critical win.'),
    messy: t('showcase:explain.messy', 'A critical with a 10 on a Hunger die: you win, but the Beast decides how.'),
    fail: t('showcase:explain.fail', 'Some successes, but fewer than the Difficulty.'),
    bestial: t('showcase:explain.bestial', 'A failure with a 1 on a Hunger die: the Beast lashes out.'),
    total: t('showcase:explain.total', 'Not a single success.'),
  }[key];
}

function adjustedNote(adjusted) {
  if (!adjusted || !adjusted.length) return '';
  const parts = adjusted.map((a) => {
    if (a.field === 'pool') return t('showcase:editions.adjPool', 'pool set to {{n}}', { n: a.value });
    if (a.field === 'hunger') return t('showcase:editions.adjHunger', 'Hunger set to {{n}}', { n: a.value });
    return t('showcase:editions.adjDifficulty', 'Difficulty set to {{n}}', { n: a.value });
  });
  return t('showcase:editions.adjusted', 'To make this result possible: {{changes}}.', { changes: parts.join(', ') });
}

/** Simulated table overlay: tumble for ROLL_MS, then settle (same component the game uses). */
function useDemoOverlay() {
  const reduced = useReducedMotionPref();
  const [overlay, setOverlay] = useState({ visible: false });
  const timers = useRef([]);
  const clear = () => {
    timers.current.forEach((id) => {
      clearTimeout(id);
      clearInterval(id);
    });
    timers.current = [];
  };
  useEffect(() => clear, []);
  const play = (roll) => {
    clear();
    const v5 = roll.edition === 'v5';
    const diceFinal = v5 ? [...roll.result.normal_dice, ...roll.result.hunger_dice] : roll.result.results;
    const hungerFlags = v5 ? [...roll.result.normal_dice.map(() => false), ...roll.result.hunger_dice.map(() => true)] : diceFinal.map(() => false);
    const base = {
      visible: true,
      animationId: `demo-${Date.now()}`,
      rulesEdition: v5 ? 'v5' : 'classic',
      difficulty: roll.result.difficulty,
      diceFinal,
      hungerFlags,
      extraDiceCount: 0,
      specialtyRerolls: [],
      result: roll.result,
    };
    const tumble = () => diceFinal.map(() => 1 + Math.floor(Math.random() * 10));
    setOverlay({ ...base, settled: false, diceRolling: tumble() });
    if (!reduced) {
      const iv = setInterval(() => setOverlay((o) => (o.settled ? o : { ...o, diceRolling: tumble() })), 90);
      timers.current.push(iv);
    }
    timers.current.push(
      setTimeout(() => {
        clear();
        setOverlay((o) => ({ ...o, settled: true }));
      }, reduced ? 400 : ROLL_MS)
    );
  };
  const dismiss = () => {
    clear();
    setOverlay((o) => ({ ...o, visible: false }));
  };
  return { overlay, play, dismiss };
}

function EditionCard({ edition, onOverlay }) {
  const v5 = edition === 'v5';
  const [pool, setPool] = useState(v5 ? 6 : 6);
  const [hunger, setHunger] = useState(2);
  const [difficulty, setDifficulty] = useState(v5 ? 3 : 6);
  const [outcome, setOutcome] = useState('random');
  const [roll, setRoll] = useState(() =>
    v5 ? rollV5({ pool: 6, hunger: 2, difficulty: 3, outcome: 'success' }, seededRandom(4)) : rollClassic({ pool: 6, difficulty: 6, outcome: 'success' }, seededRandom(9))
  );
  const [rollKey, setRollKey] = useState(0);

  const doRoll = () => {
    const next = v5 ? rollV5({ pool, hunger, difficulty, outcome }) : rollClassic({ pool, difficulty, outcome });
    // A forced outcome may have needed different numbers: show them in the controls.
    setPool(next.params.pool);
    setDifficulty(next.params.difficulty);
    if (v5) setHunger(next.params.hunger);
    setRoll(next);
    setRollKey((k) => k + 1);
  };

  const diceCount = Math.min(10, v5 ? roll.result.normal_dice.length + roll.result.hunger_dice.length : roll.result.results.length);
  const summary = v5 ? v5SummaryLine(roll.result) : classicSummaryLine(roll.result);
  const diffOptions = (v5 ? [1, 2, 3, 4, 5, 6, 7, 8] : [3, 4, 5, 6, 7, 8, 9, 10]).map((n) => ({ value: String(n), label: String(n) }));
  const title = v5 ? t('showcase:editions.v5Title', 'Vampire: the Masquerade 5th edition') : t('showcase:editions.classicTitle', 'Classic World of Darkness (Revised)');

  return (
    <Card ornate className={`sc-edition sc-edition--${edition}`} data-testid={`edition-${edition}`}>
      <header className="sc-edition__head">
        <ChronicleSigil line="vampire" edition={v5 ? 'v5' : 'classic'} size={64} />
        <div>
          <Badge lang="en" edition={v5 ? 'V5' : 'Revised'} tone={v5 ? 'blood' : 'gold'} icon={v5 ? 'line-vampire' : 'book'} />
          <h3 className="sc-edition__title" lang="en">
            {title}
          </h3>
        </div>
      </header>
      <ul className="sc-edition__rules">
        {v5 ? (
          <>
            <li>{t('showcase:editions.v5r1', 'Every die showing 6 or more is a success; the Difficulty is how many you need.')}</li>
            <li>{t('showcase:editions.v5r2', 'Each pair of 10s adds two more: a critical.')}</li>
            <li>{t('showcase:editions.v5r3', 'Red Hunger dice can make a win messy or a failure bestial.')}</li>
          </>
        ) : (
          <>
            <li>{t('showcase:editions.c1', 'Roll your pool against a difficulty from 3 to 10.')}</li>
            <li>{t('showcase:editions.c2', 'Every 1 cancels a success. Five or more is exceptional.')}</li>
            <li>{t('showcase:editions.c3', 'No successes and a 1 on the table: a botch.')}</li>
          </>
        )}
      </ul>

      <div className="sc-edition__controls">
        <DotTrack
          label={t('showcase:editions.pool', 'Dice pool')}
          value={pool}
          min={1}
          max={10}
          showValue
          tone={v5 ? 'blood' : 'gold'}
          onChange={(n) => {
            setPool(n);
            if (hunger > n) setHunger(n);
          }}
        />
        {v5 ? (
          <DotTrack
            label={t('showcase:editions.hunger', 'Hunger')}
            value={hunger}
            max={5}
            shape="square"
            showValue
            tone="blood"
            onChange={(n) => setHunger(Math.min(n, pool))}
          />
        ) : null}
        <Select
          label={v5 ? t('showcase:editions.difficultyV5', 'Difficulty (successes needed)') : t('showcase:editions.difficulty', 'Difficulty')}
          value={String(difficulty)}
          onChange={(e) => setDifficulty(Number(e.target.value))}
          options={diffOptions}
        />
        <PillGroup
          label={t('showcase:editions.force', 'Force an outcome')}
          name={`sc-outcome-${edition}`}
          value={outcome}
          onChange={setOutcome}
          options={outcomeOptions(edition)}
          testId={`outcome-picker-${edition}`}
          className="sc-pills--outcomes"
        />
      </div>

      <div className="sc-edition__actions">
        <Button variant={v5 ? 'primary' : 'arcane'} icon="dice" onClick={doRoll} data-testid={`roll-${edition}`}>
          {t('showcase:editions.roll', 'Roll the dice')}
        </Button>
        <Button variant="ghost" icon="eye" onClick={() => onOverlay(roll)}>
          {t('showcase:editions.overlay', 'Watch at the table')}
        </Button>
      </div>

      <div
        className="sc-stage"
        data-testid={`stage-${edition}`}
        data-outcome={roll.outcomeKey}
        data-mood={roll.mood || undefined}
        style={{ '--vizw': `${Math.round(Math.max(diceCount * 48, 200) * 1.45)}px` }}
      >
        <DiceRollViz result={roll.result} rollKey={rollKey} drip={false} />
        <div className="sc-stage__result" aria-live="polite">
          <OutcomeBadges result={roll.result} size="lg" />
          <p className="sc-stage__summary">{summary}</p>
          <p className="sc-stage__explain">{explain(roll.outcomeKey)}</p>
          {roll.adjusted.length ? (
            <p className="sc-stage__adjusted">
              <Glyph name="info" size={14} /> {adjustedNote(roll.adjusted)}
            </p>
          ) : null}
        </div>
        <RollFx mood={roll.mood} playKey={rollKey} play={rollKey > 0} />
      </div>
    </Card>
  );
}

export default function Editions() {
  const { overlay, play, dismiss } = useDemoOverlay();
  return (
    <Section
      id="editions"
      numeral="I"
      kicker={t('showcase:editions.kicker', 'Two editions, one table')}
      title={t('showcase:editions.title', 'Roll the bones')}
      lede={t(
        'showcase:editions.lede',
        'Each chronicle picks its rules: the classic Revised dice or V5 with Hunger. Pick a pool and roll, or force an outcome to see every effect the table can show. The dice are resolved by the same code the game uses.'
      )}
    >
      <div className="sc-editions">
        <EditionCard edition="classic" onOverlay={play} />
        <EditionCard edition="v5" onOverlay={play} />
      </div>
      <DiceRollOverlay overlay={overlay} onDismiss={dismiss} />
    </Section>
  );
}

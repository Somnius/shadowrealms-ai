/**
 * Guided mode of the V5 forge (Forge v2 part E): one scenario question per screen, then the
 * suggested clan and predator type with their catalog descriptions and the answers behind them.
 * "Build this character" hands the prefill to the forge (onBuild); answers that leave the path
 * (characterSheet/v5/guided.js) send the player to the full forge instead.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { V5_ATTRIBUTES, V5_SKILL_DISTRIBUTIONS, V5_SKILL_LABELS } from '../../../characterSheet/v5/constants';
import { NONE_LIMIT, NONE_OF_THESE, guidedQuestions, guidedResult, noneCount } from '../../../characterSheet/v5/guided';
import { descIn } from '../../../characterSheet/v5/rulesData';
import { clanInfo, predatorInfo } from '../../../characterSheet/v5/validation';
import { useV5Guided } from '../../../rules/v5Guided';
import { formatList, getLanguage, t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, CatalogNote, buttonStyle, noteStyle, primaryButtonStyle } from './forgeUi';

const textIn = (text) => descIn(text, getLanguage());
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const headingStyle = {
  fontFamily: 'var(--sr-font-display)',
  color: 'var(--sr-bone-100)',
  fontSize: '18px',
  lineHeight: 1.4,
  margin: '0 0 14px',
  outline: 'none',
};
const cardStyle = {
  padding: '12px 14px',
  marginBottom: '12px',
  borderRadius: '8px',
  border: '1px solid var(--sr-night-600)',
  background: 'rgba(0,0,0,0.25)',
};
const smallLabelStyle = { color: 'var(--sr-arcane-300)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.04em' };
const rowStyle = { display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'space-between', marginTop: '18px' };
const disabledStyle = { ...primaryButtonStyle, background: 'var(--sr-night-500)', cursor: 'not-allowed' };

function Choice({ id, name, checked, onChange, muted, children }) {
  return (
    <label
      htmlFor={id}
      style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-start',
        padding: '10px 12px',
        borderRadius: '8px',
        border: `1px solid ${checked ? ACCENT : 'var(--sr-night-600)'}`,
        background: checked ? 'rgba(127,29,29,0.28)' : 'var(--sr-night-850)',
        color: muted ? 'var(--sr-bone-300)' : 'var(--sr-bone-100)',
        fontSize: '14px',
        lineHeight: 1.45,
        cursor: 'pointer',
      }}
    >
      <input type="radio" id={id} name={name} checked={checked} onChange={onChange} style={{ marginTop: '3px', accentColor: 'var(--sr-blood-500)' }} />
      <span>{children}</span>
    </label>
  );
}

/** "Because you chose:" and the answers that gave the points. */
function Why({ reasons }) {
  if (!reasons.length) return null;
  return (
    <div style={{ ...noteStyle, marginTop: '8px' }}>
      {t('wizard:guided.because', 'Because you chose:')}
      <ul style={{ margin: '4px 0 0', paddingLeft: '20px' }}>
        {reasons.map((r) => (
          <li key={`${r.question}:${r.option}`}>{t('wizard:guided.quoted', '“{{text}}”', { text: textIn(r.text) })}</li>
        ))}
      </ul>
    </div>
  );
}

function Suggestion({ result, headingRef, onBuild, onChangeAnswers, onFullForge }) {
  const clan = clanInfo(result.clan);
  const predator = result.predator ? predatorInfo(result.predator) : null;
  const { attributes } = result.prefill;
  const [first, second, third] = result.categories;
  const best = V5_ATTRIBUTES[first].find(([k]) => attributes[k] === 4)?.[1];
  const distribution = V5_SKILL_DISTRIBUTIONS[result.distribution].label;
  return (
    <section aria-labelledby="guided-result-title">
      <h3 id="guided-result-title" ref={headingRef} tabIndex={-1} style={headingStyle}>
        {t('wizard:guided.resultTitle', 'The guide suggests')}
      </h3>
      <div style={cardStyle}>
        <div style={smallLabelStyle}>
          <Term id="clan" />
        </div>
        <div lang="en" style={{ fontFamily: 'var(--sr-font-display)', fontSize: '20px', color: ACCENT }}>
          {result.clan}
        </div>
        <CatalogNote entry={clan} style={{ fontSize: '13px' }} />
        <Why reasons={result.why.clan} />
      </div>
      <div style={cardStyle}>
        <div style={smallLabelStyle}>
          <Term id="predator" />
        </div>
        {result.predator ? (
          <>
            <div lang="en" style={{ fontFamily: 'var(--sr-font-display)', fontSize: '20px', color: ACCENT }}>
              {result.predator}
            </div>
            <CatalogNote entry={predator} style={{ fontSize: '13px' }} />
            <Why reasons={result.why.predator} />
          </>
        ) : (
          <p style={{ ...noteStyle, margin: '4px 0 0' }}>
            {t('wizard:guided.noPredator', 'No predator type stood out in your answers: you pick one in the forge.')}
          </p>
        )}
      </div>
      <div style={{ ...cardStyle, ...noteStyle }}>
        <p style={{ margin: '0 0 6px' }}>
          {t('wizard:guided.attributesLine', 'Attributes: {{first}} first, then {{second}}, then {{third}}; {{best}} starts at 4.', {
            first: capital(first),
            second: capital(second),
            third: capital(third),
            best,
          })}
        </p>
        <p style={{ margin: '0 0 6px' }}>
          {result.skillFocus.length
            ? t('wizard:guided.skillsLine', 'Skills: {{distribution}}, built around {{top}}.', {
                distribution,
                top: formatList(result.skillFocus.map((k) => V5_SKILL_LABELS[k])),
              })
            : t('wizard:guided.skillsLinePlain', 'Skills: {{distribution}}.', { distribution })}
        </p>
        <p style={{ margin: 0 }}>{t('wizard:guided.changeLater', 'Everything stays editable in the forge.')}</p>
      </div>
      <div style={rowStyle}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          <button type="button" onClick={onChangeAnswers} style={buttonStyle}>
            {t('wizard:guided.changeAnswers', 'Change my answers')}
          </button>
          <button type="button" onClick={onFullForge} style={buttonStyle}>
            {t('wizard:guided.fullForgeInstead', 'Open the full forge instead')}
          </button>
        </div>
        <button type="button" onClick={() => onBuild(result.prefill, result)} style={primaryButtonStyle}>
          {t('wizard:guided.build', 'Build this character')}
        </button>
      </div>
    </section>
  );
}

function OffPath({ reason, headingRef, onChangeAnswers, onFullForge }) {
  const why = {
    none: t('wizard:guided.offNone', 'You picked “None of these” twice, so these questions don’t fit the character you have in mind.'),
    not_allowed: t('wizard:guided.offNotAllowed', 'Your answers point to a clan this chronicle doesn’t offer.'),
    unclear: t('wizard:guided.offUnclear', 'Your answers point in several directions, so no clan stands out.'),
  }[reason];
  return (
    <section aria-labelledby="guided-off-title">
      <h3 id="guided-off-title" ref={headingRef} tabIndex={-1} style={headingStyle}>
        {t('wizard:guided.offTitle', 'This path doesn’t fit')}
      </h3>
      <p style={noteStyle}>{why}</p>
      <p style={noteStyle}>{t('wizard:guided.offHelp', 'In the full forge you choose everything yourself, step by step.')}</p>
      <div style={rowStyle}>
        <button type="button" onClick={onChangeAnswers} style={buttonStyle}>
          {t('wizard:guided.changeAnswers', 'Change my answers')}
        </button>
        <button type="button" onClick={onFullForge} style={primaryButtonStyle}>
          {t('wizard:guided.fullForge', 'Open the full forge')}
        </button>
      </div>
    </section>
  );
}

/**
 * props: token; settings (the chronicle's normalised creation settings); onBuild(initial, result)
 * with the forge prefill; onFullForge(); onBack() (before the first question).
 */
export default function GuidedWizard({ token, settings, onBuild, onFullForge, onBack }) {
  const { status, set } = useV5Guided(token);
  const questions = useMemo(() => guidedQuestions(set), [set]);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [phase, setPhase] = useState('questions'); // questions | result
  const headingRef = useRef(null);

  // Focus follows the screen: the question, the suggestion or the off-path panel.
  useEffect(() => {
    headingRef.current?.focus();
  }, [status, step, phase]);

  if (status === 'loading') {
    return (
      <p role="status" style={noteStyle}>
        {t('wizard:guided.loading', 'Loading the questions…')}
      </p>
    );
  }
  if (status === 'error' || !questions.length) {
    return (
      <section aria-labelledby="guided-off-title">
        <h3 id="guided-off-title" ref={headingRef} tabIndex={-1} style={headingStyle}>
          {t('wizard:guided.unavailableNow', 'The guide isn’t available right now')}
        </h3>
        <p style={noteStyle}>{t('wizard:guided.unavailableHelp', 'You can still build your character in the full forge.')}</p>
        <div style={rowStyle}>
          <button type="button" onClick={onBack} style={buttonStyle}>
            {t('wizard:guided.back', 'Back')}
          </button>
          <button type="button" onClick={onFullForge} style={primaryButtonStyle}>
            {t('wizard:guided.fullForge', 'Open the full forge')}
          </button>
        </div>
      </section>
    );
  }

  const backToQuestions = () => setPhase('questions');
  if (phase === 'result') {
    const result = guidedResult(set, answers, settings);
    return result.offPath ? (
      <OffPath reason={result.reason} headingRef={headingRef} onChangeAnswers={backToQuestions} onFullForge={onFullForge} />
    ) : (
      <Suggestion result={result} headingRef={headingRef} onBuild={onBuild} onChangeAnswers={backToQuestions} onFullForge={onFullForge} />
    );
  }

  const q = questions[Math.min(step, questions.length - 1)];
  const answer = answers[q.id];
  const last = step >= questions.length - 1;
  const choose = (value) => setAnswers((prev) => ({ ...prev, [q.id]: value }));
  const next = () => {
    // A second "none of these" ends the path at once; otherwise the result comes after the last question.
    if (last || noneCount(set, answers) >= NONE_LIMIT) setPhase('result');
    else setStep(step + 1);
  };
  const back = () => (step === 0 ? onBack() : setStep(step - 1));
  const name = `guided-${q.id}`;

  return (
    <section aria-labelledby="guided-question">
      <div id="guided-progress" style={{ ...noteStyle, fontSize: '12px' }}>
        {t('wizard:guided.progress', 'Question {{n}} of {{total}}', { n: step + 1, total: questions.length })}
      </div>
      <div
        role="progressbar"
        aria-labelledby="guided-progress"
        aria-valuemin={1}
        aria-valuemax={questions.length}
        aria-valuenow={step + 1}
        style={{ height: '4px', background: 'var(--sr-night-700)', borderRadius: '2px', margin: '6px 0 16px' }}
      >
        <div style={{ width: `${((step + 1) / questions.length) * 100}%`, height: '100%', background: ACCENT, borderRadius: '2px' }} />
      </div>
      <h3 id="guided-question" ref={headingRef} tabIndex={-1} style={headingStyle}>
        {textIn(q.text)}
      </h3>
      <div role="radiogroup" aria-labelledby="guided-question" style={{ display: 'grid', gap: '8px' }}>
        {q.options.map((o) => (
          <Choice key={o.id} id={`${name}-${o.id}`} name={name} checked={answer === o.id} onChange={() => choose(o.id)}>
            {textIn(o.text)}
          </Choice>
        ))}
        <Choice id={`${name}-none`} name={name} checked={answer === NONE_OF_THESE} onChange={() => choose(NONE_OF_THESE)} muted>
          {t('wizard:guided.none', 'None of these')}
        </Choice>
      </div>
      <div style={rowStyle}>
        <button type="button" onClick={back} style={buttonStyle}>
          {t('wizard:guided.back', 'Back')}
        </button>
        <button type="button" onClick={next} disabled={answer === undefined} style={answer === undefined ? disabledStyle : primaryButtonStyle}>
          {last ? t('wizard:guided.finish', 'See the suggestion') : t('wizard:guided.next', 'Next')}
        </button>
      </div>
    </section>
  );
}

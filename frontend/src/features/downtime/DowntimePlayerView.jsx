import { useState } from 'react';
import { Link } from 'react-router';
import { Badge, Button, Checkbox, Input, Panel, Select, Textarea } from '../../design';
import { t } from '../../i18n';
import { downtimeApi } from './downtimeApi';
import { downtimeErrorText } from './downtimeErrors';

export const resultKindLabel = (kind) =>
  ({
    scene: () => t('downtime:kind.scene', 'Scene'),
    result: () => t('downtime:kind.result', 'Result'),
    feedback: () => t('downtime:kind.feedback', 'Feedback'),
    skip: () => t('downtime:kind.skip', 'No result (skip)'),
  })[kind]?.() || kind;

export function RoundBanner({ round }) {
  if (!round) {
    return <p className="sr-downtime__banner sr-muted">{t('downtime:round.none', 'No downtime round is open right now.')}</p>;
  }
  const title = round.title || t('downtime:round.untitled', 'Downtime round');
  const text = {
    open: () => t('downtime:round.openText', 'Open: declare what your character does between sessions.'),
    resolving: () => t('downtime:round.resolvingText', 'Closed to players: the Storyteller is resolving this round.'),
    released: () => t('downtime:round.releasedText', 'Released: the results are below.'),
  }[round.status];
  return (
    <div className="sr-downtime__banner" data-status={round.status}>
      <Badge tone={round.status === 'open' ? 'ok' : round.status === 'resolving' ? 'warn' : 'arcane'}>{roundStatusLabel(round.status)}</Badge>
      <strong className="sr-usertitle">{title}</strong>
      {text ? <span className="sr-small">{text()}</span> : null}
    </div>
  );
}

export const roundStatusLabel = (s) =>
  ({
    open: () => t('downtime:status.open', 'Open'),
    resolving: () => t('downtime:status.resolving', 'Closed to players'),
    released: () => t('downtime:status.released', 'Released'),
  })[s]?.() || s;

function RollSummary({ roll }) {
  if (!roll) return null;
  if (roll.outcome_hidden) {
    // The server sends no faces while the difficulty is hidden (they would give the outcome away).
    return <p className="sr-small sr-muted sr-downtime__roll">{t('downtime:roll.hidden', 'Rolled. The result shows when the round is released.')}</p>;
  }
  const faces = roll.normal_dice && roll.normal_dice.length ? roll.normal_dice : roll.results || [];
  return (
    <div className="sr-small sr-downtime__roll">
      <span>{t('downtime:roll.dice', 'Dice: {{faces}}', { faces: faces.join(', ') })}</span>
      {roll.hunger_dice && roll.hunger_dice.length ? (
        <span>{t('downtime:roll.hunger', 'Hunger dice: {{faces}}', { faces: roll.hunger_dice.join(', ') })}</span>
      ) : null}
      <span>
        {t('downtime:roll.successes', { one: '{{count}} success', other: '{{count}} successes' }, { count: roll.successes ?? 0 })}
        {roll.is_botch ? ` · ${t('downtime:roll.botch', 'Botch')}` : ''}
        {roll.is_critical ? ` · ${t('downtime:roll.critical', 'Critical')}` : ''}
      </span>
    </div>
  );
}

function RollForm({ isV5, busy, onRoll }) {
  const [pool, setPool] = useState('');
  const [specialty, setSpecialty] = useState(false);
  const [willpower, setWillpower] = useState(false);
  return (
    <form
      className="sr-row sr-row--end"
      onSubmit={(e) => {
        e.preventDefault();
        const body = { pool_size: parseInt(pool, 10) || 0 };
        if (!isV5) Object.assign(body, { specialty, willpower });
        onRoll(body);
      }}
    >
      <Input
        type="number"
        min={1}
        max={50}
        label={t('downtime:roll.pool', 'Dice pool')}
        hint={isV5 ? t('downtime:roll.hungerHint', 'Hunger comes from your sheet.') : undefined}
        value={pool}
        onChange={(e) => setPool(e.target.value)}
        fieldClassName="sr-field--short"
        required
      />
      {!isV5 ? (
        <>
          <Checkbox label={t('downtime:roll.specialty', 'Specialty')} checked={specialty} onChange={(e) => setSpecialty(e.target.checked)} />
          <Checkbox label={t('downtime:roll.willpower', 'Spend Willpower')} checked={willpower} onChange={(e) => setWillpower(e.target.checked)} />
        </>
      ) : null}
      <Button type="submit" variant="primary" icon="dice" loading={busy}>
        {t('downtime:roll.button', 'Roll')}
      </Button>
    </form>
  );
}

function PhaseItem({ phase, cid, isV5, liveRound, canPlay, busy, onRoll }) {
  const live = liveRound && phase.round_id === liveRound.id && liveRound.status === 'open';
  const showDifficulty = phase.difficulty != null;
  return (
    <li className="sr-downtime__phase">
      <div className="sr-row">
        <span className="sr-muted sr-small">{phase.round_title || t('downtime:round.untitled', 'Downtime round')}</span>
        {showDifficulty ? <Badge>{t('downtime:phase.difficulty', 'Difficulty {{value}}', { value: phase.difficulty })}</Badge> : null}
        {phase.difficulty_hidden && !showDifficulty ? <Badge tone="arcane">{t('downtime:phase.hiddenDifficulty', 'Hidden difficulty')}</Badge> : null}
      </div>
      <p className="sr-downtime__action">{phase.action}</p>
      <RollSummary roll={phase.roll} />
      {live && !phase.roll && canPlay ? (
        phase.ready ? (
          <RollForm isV5={isV5} busy={busy} onRoll={(body) => onRoll(phase, body)} />
        ) : (
          <p className="sr-muted sr-small">{t('downtime:phase.waiting', 'Waiting for the Storyteller to set the difficulty.')}</p>
        )
      ) : null}
      {phase.status === 'resolved' ? (
        <div className="sr-downtime__result">
          <Badge tone="gold">{resultKindLabel(phase.result_kind)}</Badge>
          {phase.result_text ? <p>{phase.result_text}</p> : null}
          {phase.result_kind === 'scene' && phase.result_location ? (
            <Link to={`/c/${cid}/${phase.result_location.id}`} className="sr-small">
              {t('downtime:phase.sceneRoom', 'Scene in {{room}}', { room: phase.result_location.name })}
            </Link>
          ) : null}
        </div>
      ) : null}
      {phase.status === 'skipped' ? <p className="sr-muted sr-small">{t('downtime:phase.skipped', 'No result this round.')}</p> : null}
      {phase.status === 'unresolved' ? <p className="sr-muted sr-small">{t('downtime:phase.unresolved', 'The Storyteller released the round without a result for this.')}</p> : null}
    </li>
  );
}

function DeclareForm({ busy, onDeclare }) {
  const [action, setAction] = useState('');
  return (
    <form
      className="sr-stack sr-downtime__declare"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await onDeclare(action.trim())) setAction('');
      }}
    >
      <Textarea
        label={t('downtime:declare.label', 'What does your character do this round?')}
        value={action}
        rows={3}
        maxLength={2000}
        onChange={(e) => setAction(e.target.value)}
        required
      />
      <div className="sr-form__actions">
        <Button type="submit" variant="primary" loading={busy} disabled={!action.trim()}>
          {t('downtime:declare.button', 'Declare')}
        </Button>
      </div>
    </form>
  );
}

function NewProjectForm({ projects, busy, onCreate }) {
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');
  const [parent, setParent] = useState('');
  return (
    <form
      className="sr-stack"
      onSubmit={async (e) => {
        e.preventDefault();
        if (await onCreate({ title: title.trim(), goal: goal.trim(), parent_id: parent ? Number(parent) : null })) {
          setTitle('');
          setGoal('');
          setParent('');
        }
      }}
    >
      <Input label={t('downtime:project.title', 'Title')} value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} required />
      <Textarea label={t('downtime:project.goal', 'Goal')} value={goal} rows={2} maxLength={2000} onChange={(e) => setGoal(e.target.value)} />
      {projects.length ? (
        <Select
          label={t('downtime:project.parent', 'Belongs to project (optional)')}
          value={parent}
          onChange={(e) => setParent(e.target.value)}
          options={[{ value: '', label: t('downtime:project.noParent', 'None') }, ...projects.map((p) => ({ value: String(p.id), label: p.title }))]}
        />
      ) : null}
      <div className="sr-form__actions">
        <Button type="submit" variant="primary" icon="plus" loading={busy} disabled={!title.trim()}>
          {t('downtime:project.create', 'Create project')}
        </Button>
      </div>
    </form>
  );
}

const projectStatusLabel = (s) =>
  ({
    active: () => t('downtime:projectStatus.active', 'Active'),
    done: () => t('downtime:projectStatus.done', 'Done'),
    abandoned: () => t('downtime:projectStatus.abandoned', 'Abandoned'),
  })[s]?.() || s;
export { projectStatusLabel };

/** The player's side: own projects (flat, parent as a breadcrumb), declare, roll, results. */
export default function DowntimePlayerView({ api, campaignId, isV5, data, reload, toast, title, embedded = false }) {
  const [busy, setBusy] = useState(null);
  const { round, can_play: canPlay, player_problem: problem, projects = [], character } = data;

  const run = async (key, call, okText) => {
    setBusy(key);
    const r = await call();
    setBusy(null);
    if (!r.ok) {
      toast({ tone: 'danger', title: downtimeErrorText(r.data) });
      reload();
      return false;
    }
    if (okText) toast({ tone: 'ok', title: okText });
    reload();
    return true;
  };

  return (
    <div className="sr-stack">
      {embedded ? null : <RoundBanner round={round} />}
      {!canPlay ? (
        <p className="sr-downtime__readonly" role="status">
          {problem ? downtimeErrorText({ code: problem }) : t('downtime:readOnly', 'You can read your projects but not act on them.')}
        </p>
      ) : null}
      {character ? <p className="sr-muted sr-small">{t('downtime:character', 'Playing as {{name}}', { name: character.name })}</p> : null}

      <Panel title={title || t('downtime:projects.title', 'Your projects')} icon="hourglass">
        {projects.length === 0 ? <p className="sr-muted">{t('downtime:projects.none', 'No projects yet.')}</p> : null}
        <ul className="sr-downtime__list">
          {projects.map((p) => {
            const inLive = round && p.phases.some((ph) => ph.round_id === round.id);
            const canDeclare = canPlay && round && round.status === 'open' && !inLive && p.status === 'active';
            return (
              <li key={p.id} className="sr-downtime__project">
                {p.parent_title ? (
                  <nav className="sr-small sr-muted sr-downtime__crumb" aria-label={t('downtime:project.crumb', 'Belongs to project')}>
                    {p.parent_title} ›
                  </nav>
                ) : null}
                <div className="sr-row">
                  <strong>{p.title}</strong>
                  {p.status !== 'active' ? <Badge>{projectStatusLabel(p.status)}</Badge> : null}
                </div>
                {p.goal ? <p className="sr-small">{p.goal}</p> : null}
                {p.phases.length ? (
                  <ul className="sr-downtime__phases">
                    {p.phases.map((ph) => (
                      <PhaseItem
                        key={ph.id}
                        phase={ph}
                        cid={campaignId}
                        isV5={isV5}
                        liveRound={round}
                        canPlay={canPlay}
                        busy={busy === `roll-${ph.id}`}
                        onRoll={(phase, body) =>
                          run(`roll-${phase.id}`, () => downtimeApi.rollPhase(api, campaignId, phase.id, body), t('downtime:roll.done', 'Rolled.'))
                        }
                      />
                    ))}
                  </ul>
                ) : null}
                {canDeclare ? (
                  <DeclareForm
                    busy={busy === `declare-${p.id}`}
                    onDeclare={(action) =>
                      run(`declare-${p.id}`, () => downtimeApi.declarePhase(api, campaignId, p.id, action), t('downtime:declare.done', 'Declared.'))
                    }
                  />
                ) : null}
              </li>
            );
          })}
        </ul>
      </Panel>

      {canPlay ? (
        <Panel title={t('downtime:project.new', 'New project')} icon="quill">
          <NewProjectForm
            projects={projects.filter((p) => p.status === 'active')}
            busy={busy === 'create'}
            onCreate={(body) => run('create', () => downtimeApi.createProject(api, campaignId, body), t('downtime:project.created', 'Project created.'))}
          />
        </Panel>
      ) : null}
    </div>
  );
}

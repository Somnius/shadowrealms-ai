import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Checkbox, Input, Panel, Select, Textarea } from '../../design';
import { t } from '../../i18n';
import { downtimeApi } from './downtimeApi';
import { downtimeErrorText, isVersionConflict } from './downtimeErrors';
import { RoundBanner, projectStatusLabel, resultKindLabel, roundStatusLabel } from './DowntimePlayerView';

const KINDS = ['result', 'scene', 'feedback', 'skip'];

/** Net change this phase has already applied per target ("indicator:3" → +2). */
function appliedNet(changes) {
  const out = {};
  (changes || []).forEach((c) => {
    const k = `${c.target_kind}:${c.target_id}`;
    out[k] = (out[k] || 0) + Number(c.delta || 0);
  });
  return out;
}

function SetupForm({ phase, isV5, busy, onSave }) {
  const [difficulty, setDifficulty] = useState(phase.difficulty == null ? '' : String(phase.difficulty));
  const [hidden, setHidden] = useState(Boolean(phase.difficulty_hidden));
  if (!phase.no_roll) {
    return <p className="sr-small">{t('downtime:st.difficultyFixed', 'Difficulty {{value}} (fixed after the roll)', { value: phase.difficulty ?? '–' })}</p>;
  }
  return (
    <form
      className="sr-row sr-row--end"
      onSubmit={(e) => {
        e.preventDefault();
        if (difficulty === '') return;
        onSave({ version: phase.version, difficulty: Number(difficulty), difficulty_hidden: hidden });
      }}
    >
      <Input
        type="number"
        min={isV5 ? 0 : 2}
        max={10}
        required
        label={t('downtime:st.difficulty', 'Difficulty')}
        hint={isV5 ? t('downtime:st.rangeV5', '0 to 10 successes') : t('downtime:st.rangeClassic', '2 to 10')}
        value={difficulty}
        onChange={(e) => setDifficulty(e.target.value)}
        fieldClassName="sr-field--short"
      />
      <Checkbox label={t('downtime:st.hidden', 'Hide from the player')} checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
      <Button type="submit" size="sm" variant="secondary" loading={busy} disabled={difficulty === ''}>
        {phase.ready ? t('downtime:st.updateSetup', 'Update') : t('downtime:st.setReady', 'Set and let them roll')}
      </Button>
    </form>
  );
}

function ResolveForm({ phase, project, variables, locations, busy, onResolve }) {
  const net = appliedNet(phase.changes);
  const [kind, setKind] = useState(phase.result_kind || 'result');
  const [text, setText] = useState(phase.result_text || '');
  const [room, setRoom] = useState(phase.result_location_id ? String(phase.result_location_id) : '');
  const [note, setNote] = useState(phase.st_note || '');
  // Only what the Storyteller typed; an untouched or blank box keeps the change already applied.
  const [typed, setTyped] = useState({});
  const targets = [
    ...((project && project.indicators) || []).map((i) => ({ kind: 'indicator', id: i.id, name: i.name, value: i.value })),
    ...variables.map((v) => ({ kind: 'variable', id: v.id, name: v.name, value: v.value })),
  ];
  return (
    <form
      className="sr-stack sr-downtime__resolve"
      onSubmit={(e) => {
        e.preventDefault();
        // Targets that still exist only: a deleted indicator/variable is left out (the server skips
        // reversing what it can no longer find), so it never blocks a re-resolve.
        const list = targets
          .map((x) => {
            const k = `${x.kind}:${x.id}`;
            const raw = typed[k];
            const delta = raw != null && String(raw).trim() !== '' ? parseInt(raw, 10) : net[k] || 0;
            return { target_kind: x.kind, target_id: x.id, delta: Number.isFinite(delta) ? delta : net[k] || 0, explicit: raw != null && String(raw).trim() !== '' };
          })
          .filter((d) => d.delta || d.explicit || net[`${d.target_kind}:${d.target_id}`])
          .map(({ target_kind, target_id, delta }) => ({ target_kind, target_id, delta }));
        onResolve({
          version: phase.version,
          result_kind: kind,
          result_text: text,
          result_location_id: kind === 'scene' && room ? Number(room) : null,
          st_note: note,
          deltas: list,
        });
      }}
    >
      <Select
        label={t('downtime:st.kind', 'Kind of result')}
        value={kind}
        onChange={(e) => setKind(e.target.value)}
        options={KINDS.map((k) => ({ value: k, label: resultKindLabel(k) }))}
      />
      {kind !== 'skip' ? (
        <Textarea label={t('downtime:st.resultText', 'What the player reads')} value={text} rows={3} maxLength={5000} onChange={(e) => setText(e.target.value)} />
      ) : null}
      {kind === 'scene' ? (
        <Select
          label={t('downtime:st.room', 'Room for the scene')}
          value={room}
          onChange={(e) => setRoom(e.target.value)}
          options={[{ value: '', label: t('downtime:st.noRoom', 'No room') }, ...locations.map((l) => ({ value: String(l.id), label: l.name }))]}
        />
      ) : null}
      <Textarea label={t('downtime:st.note', 'Storyteller note (never shown to players)')} value={note} rows={2} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
      {targets.length ? (
        <fieldset className="sr-downtime__deltas">
          <legend className="sr-small">{t('downtime:st.deltas', 'Changes from this phase')}</legend>
          {targets.map((x) => {
            const k = `${x.kind}:${x.id}`;
            return (
              <Input
                key={k}
                type="number"
                min={-1000}
                max={1000}
                label={`${x.name} (${x.value})`}
                hint={x.kind === 'variable' ? t('downtime:st.variableHint', 'Chronicle variable') : t('downtime:st.indicatorHint', 'Project indicator')}
                value={k in typed ? typed[k] : net[k] ?? ''}
                onChange={(e) => setTyped((d) => ({ ...d, [k]: e.target.value }))}
                fieldClassName="sr-field--short"
              />
            );
          })}
        </fieldset>
      ) : null}
      <div className="sr-form__actions">
        <Button type="submit" variant="primary" loading={busy}>
          {phase.resolved ? t('downtime:st.updateResult', 'Update result') : t('downtime:st.resolve', 'Resolve')}
        </Button>
      </div>
    </form>
  );
}

function StRoll({ roll }) {
  if (!roll) return <p className="sr-muted sr-small">{t('downtime:st.notRolled', 'Not rolled yet.')}</p>;
  const faces = roll.normal_dice && roll.normal_dice.length ? roll.normal_dice : roll.results || [];
  return (
    <p className="sr-small">
      {t('downtime:st.rollLine', 'Pool {{pool}}, dice {{faces}}', { pool: roll.dice_pool ?? '?', faces: faces.join(', ') })}
      {roll.hunger_dice && roll.hunger_dice.length ? ` · ${t('downtime:roll.hunger', 'Hunger dice: {{faces}}', { faces: roll.hunger_dice.join(', ') })}` : ''}
      {' · '}
      {t('downtime:roll.successes', { one: '{{count}} success', other: '{{count}} successes' }, { count: roll.successes ?? 0 })}
      {roll.is_botch ? ` · ${t('downtime:roll.botch', 'Botch')}` : ''}
      {roll.is_critical ? ` · ${t('downtime:roll.critical', 'Critical')}` : ''}
      {roll.specialty ? ` · ${t('downtime:roll.specialty', 'Specialty')}` : ''}
      {roll.willpower ? ` · ${t('downtime:roll.willpower', 'Spend Willpower')}` : ''}
    </p>
  );
}

function PhaseCard({ phase, project, inbox, isV5, busyKey, onSetup, onResolve }) {
  return (
    <li className="sr-approvals__item" data-testid={`phase-${phase.id}`}>
      <div className="sr-row">
        <strong>{project ? project.title : '?'}</strong>
        <span className="sr-muted sr-small">{project ? project.character_name : ''}</span>
        {phase.resolved ? <Badge tone="ok">{resultKindLabel(phase.result_kind)}</Badge> : <Badge tone="warn">{t('downtime:st.unresolvedBadge', 'No result yet')}</Badge>}
        {phase.ready ? null : <Badge>{t('downtime:st.needsSetup', 'Needs a difficulty')}</Badge>}
      </div>
      <p className="sr-downtime__action">{phase.action}</p>
      {phase.round_status !== 'released' ? <SetupForm key={`s${phase.id}`} phase={phase} isV5={isV5} busy={busyKey === `setup-${phase.id}`} onSave={(b) => onSetup(phase, b)} /> : null}
      <StRoll roll={phase.roll} />
      {phase.round_status === 'resolving' ? (
        <ResolveForm
          key={`r${phase.id}`}
          phase={phase}
          project={project}
          variables={inbox.variables || []}
          locations={inbox.locations || []}
          busy={busyKey === `resolve-${phase.id}`}
          onResolve={(b) => onResolve(phase, b)}
        />
      ) : phase.resolved ? (
        <>
          <p className="sr-small">{phase.result_text}</p>
          {phase.st_note ? <p className="sr-small sr-muted">{t('downtime:st.noteShown', 'Your note: {{note}}', { note: phase.st_note })}</p> : null}
        </>
      ) : null}
    </li>
  );
}

const isNumber = (v) => /^-?\d+$/.test(String(v).trim());

/** Indicators of one project or the chronicle variables: add, edit (with version), delete. */
function ValueList({ rows, busy, onAdd, onEdit, onDelete, withNote = false, scope }) {
  const [name, setName] = useState('');
  const [value, setValue] = useState('0');
  return (
    <div className="sr-stack">
      <ul className="sr-downtime__values">
        {rows.map((r) => (
          <ValueRow key={r.id} row={r} busy={busy} withNote={withNote} onEdit={onEdit} onDelete={onDelete} />
        ))}
      </ul>
      <form
        className="sr-row sr-row--end"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!isNumber(value)) return;
          if (await onAdd({ name: name.trim(), value: parseInt(value, 10) })) {
            setName('');
            setValue('0');
          }
        }}
      >
        <Input
          label={t('downtime:values.name', 'Name')}
          aria-label={t('downtime:values.newName', 'New name in {{scope}}', { scope })}
          value={name}
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
          required
          fieldClassName="sr-grow"
        />
        <Input
          type="number"
          label={t('downtime:values.value', 'Value')}
          aria-label={t('downtime:values.newValue', 'New value in {{scope}}', { scope })}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          required
          fieldClassName="sr-field--short"
        />
        <Button type="submit" size="sm" variant="secondary" icon="plus" disabled={busy || !name.trim() || !isNumber(value)}>
          {t('downtime:values.add', 'Add')}
        </Button>
      </form>
    </div>
  );
}

function ValueRow({ row, busy, withNote, onEdit, onDelete }) {
  const [name, setName] = useState(row.name);
  const [value, setValue] = useState(String(row.value));
  const [note, setNote] = useState(row.note || '');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [version, setVersion] = useState(row.version);
  // A fresh row from the server (saved here or elsewhere) replaces the fields.
  if (version !== row.version) {
    setVersion(row.version);
    setName(row.name);
    setValue(String(row.value));
    setNote(row.note || '');
  }
  const vars = { name: row.name };
  return (
    <li>
      <form
        className="sr-row sr-row--end"
        onSubmit={(e) => {
          e.preventDefault();
          if (!isNumber(value) || !name.trim()) return;
          const body = { version: row.version, name: name.trim(), value: parseInt(value, 10) };
          if (withNote) body.note = note;
          onEdit(row, body);
        }}
      >
        <Input label={t('downtime:values.name', 'Name')} aria-label={t('downtime:values.nameOf', 'Name of {{name}}', vars)} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} fieldClassName="sr-grow" />
        <Input type="number" label={t('downtime:values.value', 'Value')} aria-label={t('downtime:values.valueOf', 'Value of {{name}}', vars)} value={value} onChange={(e) => setValue(e.target.value)} fieldClassName="sr-field--short" />
        {withNote ? <Input label={t('downtime:values.note', 'Note')} aria-label={t('downtime:values.noteOf', 'Note for {{name}}', vars)} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} fieldClassName="sr-grow" /> : null}
        {confirmDelete ? (
          <>
            <span className="sr-small">{t('downtime:values.confirmDelete', 'Delete {{name}}? Its history stays.', vars)}</span>
            <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
              {t('downtime:cancel', 'Cancel')}
            </Button>
            <Button size="sm" variant="danger" disabled={busy} aria-label={t('downtime:values.deleteOf', 'Delete {{name}}', vars)} onClick={() => onDelete(row)}>
              {t('downtime:values.delete', 'Delete')}
            </Button>
          </>
        ) : (
          <>
            <Button type="submit" size="sm" variant="secondary" disabled={busy || !isNumber(value) || !name.trim()} aria-label={t('downtime:values.saveOf', 'Save {{name}}', vars)}>
              {t('downtime:values.save', 'Save')}
            </Button>
            <Button size="sm" variant="ghost" icon="trash" disabled={busy} aria-label={t('downtime:values.deleteOf', 'Delete {{name}}', vars)} onClick={() => setConfirmDelete(true)}>
              {t('downtime:values.delete', 'Delete')}
            </Button>
          </>
        )}
      </form>
    </li>
  );
}

/** The Storyteller's side: rounds, the inbox, indicators, chronicle variables and history. */
export default function DowntimeStView({ api, campaignId, toast, isV5 = false }) {
  const [rounds, setRounds] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [roundId, setRoundId] = useState('');
  const [unresolved, setUnresolved] = useState(false);
  const [inbox, setInbox] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [newTitle, setNewTitle] = useState('');
  const [confirmRelease, setConfirmRelease] = useState(null);
  const [history, setHistory] = useState(null);

  const load = useCallback(async () => {
    const [r, i] = await Promise.all([
      downtimeApi.rounds(api, campaignId),
      downtimeApi.inbox(api, campaignId, { roundId, unresolved }),
    ]);
    if (!r.ok || !i.ok) {
      setLoadError(downtimeErrorText(!r.ok ? r.data : i.data, t('downtime:loadFailed', 'Could not load downtime.')));
      return;
    }
    setLoadError(null);
    setRounds(Array.isArray(r.data.rounds) ? r.data.rounds : []);
    setInbox(i.data);
  }, [api, campaignId, roundId, unresolved]);

  useEffect(() => {
    load();
  }, [load]);

  /** Run one call; on any refusal say why, and on a conflict reload so the form shows fresh data. */
  const run = async (key, call, okText) => {
    setBusyKey(key);
    setConfirmRelease(null);
    const r = await call();
    setBusyKey(null);
    if (!r.ok) {
      if (isVersionConflict(r)) {
        toast({ tone: 'warn', title: downtimeErrorText(r.data) });
      } else {
        toast({ tone: 'danger', title: downtimeErrorText(r.data) });
      }
      if (r.status === 409 || r.status === 404) load();
      return r;
    }
    if (okText) toast({ tone: 'ok', title: okText });
    load();
    if (history) loadHistory();
    return r;
  };

  const loadHistory = async () => {
    const r = await downtimeApi.changes(api, campaignId);
    setHistory(r.ok && Array.isArray(r.data.changes) ? r.data.changes : []);
  };

  const live = (rounds || []).find((r) => r.status !== 'released') || null;
  const projects = (inbox && inbox.projects) || [];
  const projectById = Object.fromEntries(projects.map((p) => [p.id, p]));
  const variables = (inbox && inbox.variables) || [];

  const release = async (round, force) => {
    const r = await run(`release-${round.id}`, () => downtimeApi.releaseRound(api, campaignId, round.id, force), t('downtime:st.released', 'Round released to the players.'));
    if (!r.ok && r.data && r.data.code === 'unresolved_phases') setConfirmRelease({ id: round.id, count: r.data.count });
  };

  const targetName = (c) => {
    if (c.target_kind === 'variable') return (variables.find((v) => v.id === c.target_id) || {}).name || `#${c.target_id}`;
    for (const p of projects) {
      const i = (p.indicators || []).find((x) => x.id === c.target_id);
      if (i) return `${p.title}: ${i.name}`;
    }
    return `#${c.target_id}`;
  };

  if (loadError && !rounds) {
    return (
      <div className="sr-downtime__readonly" role="alert">
        <p>{loadError}</p>
        <Button size="sm" variant="secondary" onClick={load}>
          {t('downtime:retry', 'Try again')}
        </Button>
      </div>
    );
  }
  if (!rounds || !inbox) return null;

  return (
    <div className="sr-stack">
      {loadError ? (
        <div className="sr-downtime__readonly" role="alert">
          <p>{loadError}</p>
          <Button size="sm" variant="secondary" onClick={load}>
            {t('downtime:retry', 'Try again')}
          </Button>
        </div>
      ) : null}
      <Panel title={t('downtime:st.rounds', 'Rounds')} icon="hourglass">
        <RoundBanner round={live} />
        {live ? (
          <div className="sr-row">
            {live.status === 'open' ? (
              <Button variant="primary" loading={busyKey === 'close'} onClick={() => run('close', () => downtimeApi.closeRound(api, campaignId, live.id), t('downtime:st.closed', 'Closed to players.'))}>
                {t('downtime:st.close', 'Close to players')}
              </Button>
            ) : (
              <>
                <Button variant="secondary" loading={busyKey === 'reopen'} onClick={() => run('reopen', () => downtimeApi.reopenRound(api, campaignId, live.id), t('downtime:st.reopened', 'Reopened to players.'))}>
                  {t('downtime:st.reopen', 'Reopen to players')}
                </Button>
                <Button variant="primary" loading={busyKey === `release-${live.id}`} onClick={() => release(live, false)}>
                  {t('downtime:st.release', 'Release results')}
                </Button>
              </>
            )}
          </div>
        ) : (
          <form
            className="sr-row sr-row--end"
            onSubmit={async (e) => {
              e.preventDefault();
              const r = await run('open', () => downtimeApi.openRound(api, campaignId, newTitle.trim()), t('downtime:st.opened', 'Round opened.'));
              if (r.ok) setNewTitle('');
            }}
          >
            <Input label={t('downtime:st.roundTitle', 'Title (optional)')} value={newTitle} maxLength={120} onChange={(e) => setNewTitle(e.target.value)} fieldClassName="sr-grow" />
            <Button type="submit" variant="primary" icon="plus" loading={busyKey === 'open'}>
              {t('downtime:st.open', 'Open a round')}
            </Button>
          </form>
        )}
        {confirmRelease ? (
          <div className="sr-downtime__confirm" role="alert">
            <p>{t('downtime:st.releaseConfirm', { one: '{{count}} phase has no result yet. Release anyway?', other: '{{count}} phases have no result yet. Release anyway?' }, { count: confirmRelease.count || 0 })}</p>
            <div className="sr-row">
              <Button variant="ghost" onClick={() => setConfirmRelease(null)}>
                {t('downtime:cancel', 'Cancel')}
              </Button>
              <Button variant="danger" loading={busyKey === `release-${confirmRelease.id}`} onClick={() => release({ id: confirmRelease.id }, true)}>
                {t('downtime:st.releaseAnyway', 'Release anyway')}
              </Button>
            </div>
          </div>
        ) : null}
        {rounds && rounds.length ? (
          <ul className="sr-downtime__rounds sr-small">
            {rounds.map((r) => (
              <li key={r.id}>
                <span className="sr-usertitle">{r.title || t('downtime:round.untitled', 'Downtime round')}</span> · {roundStatusLabel(r.status)} ·{' '}
                {t('downtime:st.roundCounts', { one: '{{count}} phase, {{open}} without a result', other: '{{count}} phases, {{open}} without a result' }, { count: r.phase_count, open: r.unresolved_count })}
              </li>
            ))}
          </ul>
        ) : null}
      </Panel>

      <Panel title={t('downtime:st.inbox', 'Inbox')} icon="scroll">
        <div className="sr-row sr-row--end">
          <Select
            label={t('downtime:st.round', 'Round')}
            value={roundId}
            onChange={(e) => setRoundId(e.target.value)}
            options={[
              { value: '', label: t('downtime:st.currentRound', 'Current round') },
              ...(rounds || []).map((r) => ({ value: String(r.id), label: `${r.title || t('downtime:round.untitled', 'Downtime round')} (${roundStatusLabel(r.status)})` })),
            ]}
          />
          <Checkbox label={t('downtime:st.onlyUnresolved', 'Only without a result')} checked={unresolved} onChange={(e) => setUnresolved(e.target.checked)} />
        </div>
        {inbox && inbox.round && inbox.round.status === 'open' ? (
          <p className="sr-muted sr-small">{t('downtime:st.openHint', 'Set difficulties now; close the round to players to write results.')}</p>
        ) : null}
        {inbox && inbox.phases.length === 0 ? <p className="sr-muted">{t('downtime:st.noPhases', 'No phases here.')}</p> : null}
        <ul className="sr-approvals">
          {(inbox ? inbox.phases : []).map((ph) => (
            <PhaseCard
              key={ph.id}
              phase={ph}
              isV5={isV5}
              project={projectById[ph.project_id]}
              inbox={inbox}
              busyKey={busyKey}
              onSetup={(phase, body) => run(`setup-${phase.id}`, () => downtimeApi.setupPhase(api, campaignId, phase.id, body), t('downtime:st.setupSaved', 'Difficulty saved.'))}
              onResolve={(phase, body) => run(`resolve-${phase.id}`, () => downtimeApi.resolvePhase(api, campaignId, phase.id, body), t('downtime:st.resolved', 'Result saved.'))}
            />
          ))}
        </ul>
      </Panel>

      <Panel title={t('downtime:st.projects', 'Projects and indicators')} icon="book">
        {projects.length === 0 ? <p className="sr-muted">{t('downtime:st.noProjects', 'No projects yet.')}</p> : null}
        <ul className="sr-approvals">
          {projects.map((p) => (
            <li key={p.id} className="sr-approvals__item">
              {p.parent_title ? <span className="sr-small sr-muted">{p.parent_title} ›</span> : null}
              <div className="sr-row">
                <strong>{p.title}</strong>
                <span className="sr-muted sr-small">{p.character_name}</span>
                {p.orphaned ? <Badge tone="warn">{t('downtime:st.orphaned', 'Character gone')}</Badge> : null}
              </div>
              {p.goal ? <p className="sr-small">{p.goal}</p> : null}
              <Select
                label={t('downtime:st.projectStatus', 'Status')}
                value={p.status}
                onChange={(e) => run(`status-${p.id}`, () => downtimeApi.setProjectStatus(api, campaignId, p.id, e.target.value), t('downtime:st.statusSaved', 'Status saved.'))}
                options={['active', 'done', 'abandoned'].map((s) => ({ value: s, label: projectStatusLabel(s) }))}
                fieldClassName="sr-field--short"
              />
              <ValueList
                scope={p.title}
                rows={p.indicators || []}
                busy={Boolean(busyKey)}
                onAdd={async (body) => (await run(`ind-${p.id}`, () => downtimeApi.addIndicator(api, campaignId, p.id, body), t('downtime:values.saved', 'Saved.'))).ok}
                onEdit={(row, body) => run(`ind-${row.id}`, () => downtimeApi.editIndicator(api, campaignId, row.id, body), t('downtime:values.saved', 'Saved.'))}
                onDelete={(row) => run(`ind-${row.id}`, () => downtimeApi.deleteIndicator(api, campaignId, row.id), t('downtime:values.deleted', 'Deleted.'))}
              />
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title={t('downtime:st.variables', 'Chronicle variables')} icon="crown">
        <ValueList
          scope={t('downtime:st.variables', 'Chronicle variables')}
          rows={variables}
          withNote
          busy={Boolean(busyKey)}
          onAdd={async (body) => (await run('var-new', () => downtimeApi.addVariable(api, campaignId, body), t('downtime:values.saved', 'Saved.'))).ok}
          onEdit={(row, body) => run(`var-${row.id}`, () => downtimeApi.editVariable(api, campaignId, row.id, body), t('downtime:values.saved', 'Saved.'))}
          onDelete={(row) => run(`var-${row.id}`, () => downtimeApi.deleteVariable(api, campaignId, row.id), t('downtime:values.deleted', 'Deleted.'))}
        />
      </Panel>

      <Panel title={t('downtime:st.history', 'Change history')} icon="quill">
        {history == null ? (
          <Button variant="secondary" onClick={loadHistory}>
            {t('downtime:st.showHistory', 'Show history')}
          </Button>
        ) : history.length === 0 ? (
          <p className="sr-muted">{t('downtime:st.noHistory', 'No changes yet.')}</p>
        ) : (
          <ul className="sr-downtime__history sr-small">
            {history.map((c) => (
              <li key={c.id}>
                {targetName(c)}: {c.old_value} → {c.new_value} ({c.delta > 0 ? `+${c.delta}` : c.delta}){' '}
                <span className="sr-muted">{c.phase_id ? t('downtime:st.fromPhase', 'from a phase') : t('downtime:st.manual', 'by hand')}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

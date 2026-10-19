import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Card, EmptyState, Input, Modal, Panel, Select, Spinner } from '../../design';
import { api } from '../../utils/api';
import { editionLabel, editionOf, V5 } from '../../rules/rulesEdition';
import { t } from '../../i18n';
import formatWhen from './formatWhen';

export const DEATH_TYPES = ['soft', 'mid', 'horrible'];

/** Labels are read at render time so a language switch picks them up. */
export const deathTypeLabels = () => ({
  soft: t('admin:characters.type.soft', 'Soft'),
  mid: t('admin:characters.type.mid', 'Sacrifice'),
  horrible: t('admin:characters.type.horrible', 'Horrible'),
});

const deathTypeHints = () => ({
  soft: t('admin:characters.typeHint.soft', 'A quiet end: the character fades away, their story complete.'),
  mid: t('admin:characters.typeHint.mid', 'A bittersweet end: the character falls for someone or something.'),
  horrible: t('admin:characters.typeHint.horrible', 'A brutal, terrifying end.'),
});

/** Who passes the search and the alive/fallen filter. */
export function filterCharacters(list, query, status) {
  const q = String(query || '').trim().toLowerCase();
  return (list || []).filter((c) => {
    if (status === 'alive' && c.death) return false;
    if (status === 'fallen' && !c.death) return false;
    if (!q) return true;
    return [c.name, c.owner_name, c.campaign_name].some((v) => String(v || '').toLowerCase().includes(q));
  });
}

/** The death text with whether the model wrote it. `generated` is only known right after a kill. */
export function DeathText({ text, generated }) {
  return (
    <div className="sr-admin__death">
      <p className="sr-admin__entry-text">{text}</p>
      {generated === true ? <Badge tone="arcane" icon="ai-sigil">{t('admin:characters.byAi', 'Written by the AI')}</Badge> : null}
      {generated === false ? (
        <Badge tone="neutral">{t('admin:characters.byFallback', 'Fixed sentence (the AI could not write it)')}</Badge>
      ) : null}
    </div>
  );
}

/** Choose the death, confirm, wait for the model (up to ~25 s), then show the text. */
function KillDialog({ token, character, onClose, onKilled }) {
  const [type, setType] = useState('mid');
  const [step, setStep] = useState('choose'); // choose | writing | done
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const labels = deathTypeLabels();
  const hints = deathTypeHints();

  const kill = async () => {
    setStep('writing');
    setError('');
    try {
      const r = await api.killCharacter(token, character.id, type);
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setError(
          d && d.error_code === 'character_fallen'
            ? t('admin:characters.error.alreadyFallen', 'This character has already fallen.')
            : t('admin:characters.error.kill', 'Could not kill the character.')
        );
        setStep('choose');
        return;
      }
      setResult({ text: d.death_description, generated: !!d.generated });
      setStep('done');
      onKilled();
    } catch {
      setError(t('admin:characters.error.kill', 'Could not kill the character.'));
      setStep('choose');
    }
  };

  const writing = step === 'writing';
  return (
    <Modal
      open
      onClose={writing ? undefined : onClose}
      title={t('admin:characters.kill.title', 'Kill {{name}}', { name: character.name })}
      icon="skull"
      size="sm"
      footer={
        step === 'done' ? (
          <Button variant="primary" onClick={onClose}>{t('admin:characters.kill.close', 'Close')}</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose} disabled={writing}>{t('admin:common.cancel', 'Cancel')}</Button>
            <Button variant="danger" icon="skull" onClick={kill} loading={writing} loadingLabel={t('admin:characters.kill.writing', 'Writing the death…')}>
              {t('admin:characters.kill.confirm', 'Kill for good')}
            </Button>
          </>
        )
      }
    >
      {step === 'done' && result ? (
        <div className="sr-stack">
          <p className="sr-admin__muted">{t('admin:characters.kill.done', '{{name}} has fallen. The owner sees this on their profile and sheet.', { name: character.name })}</p>
          <DeathText text={result.text} generated={result.generated} />
        </div>
      ) : writing ? (
        <div className="sr-row" role="status">
          <Spinner variant="candle" decorative />
          <span>{t('admin:characters.kill.writingLong', 'The chronicler is writing the death. This can take up to 25 seconds.')}</span>
        </div>
      ) : (
        <div className="sr-stack">
          <p className="sr-admin__warn">
            {t('admin:characters.kill.warning', 'This retires the character for good: no more play, rolls or AI scenes. The death is written once, in the chronicle’s language, from what the players have seen.')}
          </p>
          <fieldset className="sr-admin__choices">
            <legend className="sr-admin__group-title">{t('admin:characters.kill.type', 'How do they die?')}</legend>
            {DEATH_TYPES.map((id) => (
              <label key={id} className="sr-admin__choice">
                <input type="radio" name="death_type" value={id} checked={type === id} onChange={() => setType(id)} />
                <span>
                  <strong className="sr-admin__strong">{labels[id]}</strong>
                  <span className="sr-admin__muted">{hints[id]}</span>
                </span>
              </label>
            ))}
          </fieldset>
          {error ? <p className="sr-admin__error" role="alert">{error}</p> : null}
        </div>
      )}
    </Modal>
  );
}

function ReviveDialog({ token, character, onClose, onRevived, showError }) {
  const [busy, setBusy] = useState(false);
  const revive = async () => {
    setBusy(true);
    try {
      const r = await api.reviveCharacter(token, character.id);
      if (!r.ok) throw new Error(String(r.status));
      onRevived();
      onClose();
    } catch {
      showError(t('admin:characters.error.revive', 'Could not revive the character.'));
      setBusy(false);
    }
  };
  return (
    <Modal
      open
      onClose={busy ? undefined : onClose}
      title={t('admin:characters.revive.title', 'Revive {{name}}', { name: character.name })}
      icon="warning"
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>{t('admin:common.cancel', 'Cancel')}</Button>
          <Button variant="primary" onClick={revive} loading={busy}>{t('admin:characters.revive.confirm', 'Revive')}</Button>
        </>
      }
    >
      <p className="sr-admin__confirm">
        {t('admin:characters.revive.body', 'Undo the death: the character can be played again. The death stays in the log.')}
      </p>
    </Modal>
  );
}

function CharacterCard({ c, onKill, onRevive }) {
  const v5 = editionOf(c) === V5;
  return (
    <Card className={`sr-admin__char${c.death ? ' is-fallen' : ''}`}>
      <div className="sr-admin__char-head">
        <strong className="sr-admin__char-name">{c.name}</strong>
        <Badge edition={editionLabel(c)} tone={v5 ? 'blood' : 'neutral'} />
        {c.death ? (
          <Badge tone="danger" icon="skull">{t('admin:characters.fallen', 'Fallen')}</Badge>
        ) : (
          <Badge tone="ok">{t('admin:characters.alive', 'Alive')}</Badge>
        )}
      </div>
      <p className="sr-admin__muted">
        {t('admin:characters.ownerChronicle', '{{owner}} · {{chronicle}}', {
          owner: c.owner_name || '—',
          chronicle: c.campaign_name || t('admin:characters.noChronicle', 'no chronicle'),
        })}
      </p>
      {c.death ? <DeathText text={c.death.death_description} /> : null}
      <div className="sr-admin__row">
        {c.death ? (
          <Button size="sm" variant="secondary" onClick={() => onRevive(c)}>{t('admin:characters.revive.action', 'Revive')}</Button>
        ) : (
          <Button size="sm" variant="danger" icon="skull" onClick={() => onKill(c)}>{t('admin:characters.kill.action', 'Kill')}</Button>
        )}
      </div>
    </Card>
  );
}

/** Kill and revive rows: who, whom, when, death type and the text. */
function DeathsLog({ token, displayTimezone, version }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.getCharacterDeaths(token);
        const d = await r.json().catch(() => null);
        if (!cancelled) setRows(r.ok && Array.isArray(d) ? d : []);
      } catch {
        if (!cancelled) setRows([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, version]);
  const labels = deathTypeLabels();
  if (rows === null) return <Spinner label={t('admin:characters.loading', 'Loading characters…')} />;
  if (rows.length === 0) return <EmptyState glyph="coffin" title={t('admin:characters.log.empty', 'No deaths yet')} />;
  return (
    <div className="sr-admin__log">
      {rows.map((e) => (
        <div key={e.id} className={`sr-admin__entry${e.action === 'revive' ? ' sr-admin__entry--user' : ''}`}>
          <div className="sr-admin__entry-head">
            <span className="sr-admin__strong">
              {e.action === 'revive'
                ? t('admin:characters.log.revived', '{{admin}} revived {{name}}', { admin: e.admin_username || '—', name: e.character_name || '—' })
                : t('admin:characters.log.killed', '{{admin}} killed {{name}} ({{type}})', {
                    admin: e.admin_username || '—',
                    name: e.character_name || '—',
                    type: labels[e.death_type] || e.death_type || '—',
                  })}
            </span>
            <span className="sr-admin__muted">{formatWhen(e.moderated_at, displayTimezone)}</span>
          </div>
          <div className="sr-admin__muted">
            {t('admin:characters.ownerChronicle', '{{owner}} · {{chronicle}}', {
              owner: e.owner_name || '—',
              chronicle: e.campaign_name || t('admin:characters.noChronicle', 'no chronicle'),
            })}
          </div>
          {e.action === 'kill' && e.death_description ? <div className="sr-admin__entry-text">{e.death_description}</div> : null}
        </div>
      ))}
    </div>
  );
}

/** Admin → Characters: every player character, kill and revive, and the deaths log. */
export default function CharactersPanel({ token, displayTimezone = null, showError }) {
  const [list, setList] = useState(null);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [killing, setKilling] = useState(null);
  const [reviving, setReviving] = useState(null);
  const [version, setVersion] = useState(0);
  // AdminPage makes a new showError every render; the loader must not change with it
  const errorRef = useRef(showError);
  errorRef.current = showError;

  // Only the newest request may set the list: a slow reload after a kill must not land after a revive.
  const latest = useRef(0);
  const load = useCallback(async () => {
    const mine = ++latest.current;
    let data = null;
    try {
      const r = await api.listAdminCharacters(token);
      const d = await r.json().catch(() => null);
      if (r.ok && Array.isArray(d)) data = d;
    } catch {
      /* falls through to the error */
    }
    if (mine !== latest.current) return;
    setList(data || []);
    if (!data) errorRef.current(t('admin:characters.error.load', 'Could not load characters.'));
  }, [token]);

  useEffect(() => {
    load();
    return () => {
      latest.current += 1; // unmounted or reloading: drop the answer in flight
    };
  }, [load, version]);

  const shown = useMemo(() => filterCharacters(list, query, status), [list, query, status]);
  const changed = () => setVersion((v) => v + 1);

  return (
    <div className="sr-admin__section" data-testid="characters-panel">
      <h2 className="sr-admin__title">{t('admin:characters.title', 'Characters')}</h2>
      <p className="sr-admin__lead">
        {t('admin:characters.lead', 'Every player character. Killing one retires it for good and writes its death, which the owner sees on their profile and sheet. Revive undoes a death.')}
      </p>
      <div className="sr-admin__row">
        <Input
          type="search"
          fieldClassName="sr-admin__grow"
          label={t('admin:characters.search', 'Search name, owner or chronicle')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Select
          label={t('admin:characters.status', 'Status')}
          fieldClassName="sr-admin__select"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[
            { value: 'all', label: t('admin:characters.filter.all', 'All') },
            { value: 'alive', label: t('admin:characters.alive', 'Alive') },
            { value: 'fallen', label: t('admin:characters.fallen', 'Fallen') },
          ]}
        />
      </div>
      {list === null ? (
        <Spinner label={t('admin:characters.loading', 'Loading characters…')} />
      ) : shown.length === 0 ? (
        <EmptyState glyph="mask" title={t('admin:characters.empty', 'No characters match')} />
      ) : (
        <ul className="sr-admin__chars">
          {shown.map((c) => (
            <li key={c.id}>
              <CharacterCard c={c} onKill={setKilling} onRevive={setReviving} />
            </li>
          ))}
        </ul>
      )}
      <Panel className="sr-admin__panel" title={t('admin:characters.log.title', 'Deaths and revivals')} icon="coffin">
        <DeathsLog token={token} displayTimezone={displayTimezone} version={version} />
      </Panel>
      {killing ? <KillDialog token={token} character={killing} onClose={() => setKilling(null)} onKilled={changed} /> : null}
      {reviving ? (
        <ReviveDialog token={token} character={reviving} onClose={() => setReviving(null)} onRevived={changed} showError={showError} />
      ) : null}
    </div>
  );
}

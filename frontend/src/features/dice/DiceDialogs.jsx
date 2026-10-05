import { useEffect, useRef, useState } from 'react';
import { Button, Checkbox, Input, Modal, Select, Spinner, Textarea } from '../../design';
import RollEditionFields, { RollHelp } from '../../components/dice/RollEditionFields';
import { describeRollRow } from '../../dice/historyRow';
import { editionLabel, editionOf, V5 } from '../../rules/rulesEdition';
import { formatDateTimeInZone } from '../../utils/userTimeFormat';
import { t } from '../../i18n';

function sheetHunger(character) {
  const h = parseInt(character?.wod_meta?.hunger, 10);
  return Number.isFinite(h) ? Math.max(0, Math.min(5, h)) : 0;
}

/**
 * Roll dialog (phase 1 roll modal on the design system Modal: Esc, focus trap, return focus).
 * Classic: pool, difficulty, specialty, Willpower. V5: pool, successes needed, Hunger + Rouse check.
 * prefill (a Storyteller roll request, features/dice/rollRequests.js rollPrefill): the fields to
 * open with; V5 Hunger still follows the sheet when the character has one.
 */
export function RollDialog({ open, onClose, campaign, location, character, speakAs, canHide, isAdmin, dice, onOpenHistory, prefill }) {
  const edition = editionOf(campaign);
  const [pool, setPool] = useState('5');
  const [difficulty, setDifficulty] = useState(6);
  const [specialty, setSpecialty] = useState(false);
  const [willpower, setWillpower] = useState(false);
  const [v5Difficulty, setV5Difficulty] = useState(1);
  const [hunger, setHunger] = useState(0);
  const [hidden, setHidden] = useState(false);
  const [reason, setReason] = useState('');
  const poolRef = useRef(null);

  // V5: prefill Hunger from the sheet each time the dialog opens; a roll request fills the rest.
  useEffect(() => {
    if (!open) return;
    if (edition === V5) {
      const fromSheet = character?.wod_meta?.hunger != null;
      setHunger(fromSheet || !prefill ? sheetHunger(character) : Math.max(0, Math.min(5, Number(prefill.hunger) || 0)));
    }
    if (!prefill) return;
    setPool(prefill.pool);
    setReason(prefill.reason || '');
    if (edition === V5) {
      if (prefill.v5Difficulty != null) setV5Difficulty(Math.max(0, Math.min(10, prefill.v5Difficulty)));
    } else {
      setDifficulty(Math.max(2, Math.min(10, Number(prefill.difficulty) || 6)));
      setSpecialty(!!prefill.specialty);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const busy = dice.rolling;
  const submit = async (e) => {
    e.preventDefault();
    const ok = await dice.roll({ pool, difficulty, v5Difficulty, hunger, specialty, willpower, hidden: canHide && hidden, reason });
    if (ok) {
      setWillpower(false);
      onClose();
    }
  };

  const onRouse = async () => {
    const asChar = speakAs === 'character' && character?.id;
    const before = sheetHunger(character);
    const after = await dice.rouse(hunger);
    if (after === null) return; // failed: keep the dialog open with the error
    // Follow the sheet only if the dialog still showed the sheet's value (a typed-in Hunger stays).
    if (after !== undefined && (!asChar || Number(hunger) === before)) setHunger(after);
    onClose(); // the Rouse line is in the chat and the toast shows the result
  };

  return (
    <Modal
      open={open}
      onClose={busy ? undefined : onClose}
      title={t('dice:dialog.title', 'Roll dice')}
      icon="d10"
      description={`${editionLabel(campaign, { long: true })} · ${location?.name || ''}`}
      initialFocusRef={poolRef}
      size="md"
    >
      <form onSubmit={submit} className="sr-form sr-roll">
        <RollHelp edition={edition} />
        <Input
          ref={poolRef}
          label={t('dice:field.pool', 'Dice pool')}
          hint={t('dice:field.poolHint', 'e.g. 5, 4+3 or 7-1')}
          value={pool}
          onChange={(e) => setPool(e.target.value)}
          inputMode="text"
          autoComplete="off"
          disabled={busy}
        />
        <div className="sr-roll__legacy">
          <RollEditionFields
            edition={edition}
            disabled={busy}
            classicDifficulty={difficulty}
            setClassicDifficulty={setDifficulty}
            specialty={specialty}
            setSpecialty={setSpecialty}
            willpower={willpower}
            setWillpower={setWillpower}
            v5Difficulty={v5Difficulty}
            setV5Difficulty={setV5Difficulty}
            hunger={hunger}
            setHunger={setHunger}
            hungerSource={
              character?.wod_meta?.hunger != null && character?.name
                ? t('dice:hungerSource', "{{name}}'s sheet: {{hunger}}", { name: character.name, hunger: character.wod_meta.hunger })
                : null
            }
            onRouse={onRouse}
            rousing={dice.rousing}
          />
        </div>
        {canHide ? (
          <Checkbox
            label={t('dice:field.hidden', 'Hide this roll from players (Storyteller / staff only)')}
            checked={hidden}
            onChange={(e) => setHidden(e.target.checked)}
            disabled={busy}
          />
        ) : null}
        <Textarea
          label={t('dice:field.reason', 'What are you rolling for? (optional)')}
          placeholder={t('dice:field.reasonPlaceholder', 'e.g. Brawl attack, Perception + Alertness…')}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          disabled={busy}
        />
        <div className="sr-form__actions">
          {isAdmin ? (
            <Button variant="ghost" onClick={onOpenHistory} disabled={busy} icon="scroll" className="sr-roll__history">
              {t('dice:history.open', 'Roll history')}
            </Button>
          ) : null}
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            {t('common:cancel', 'Cancel')}
          </Button>
          <Button type="submit" variant="primary" icon="d10" loading={busy}>
            {t('dice:dialog.submit', 'Roll & post')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const V5_OFF = { no_bestial: false, no_messy: false, min_successes: 0 };

/**
 * Admin: per-room dice leniency (PUT …/dice-leniency), per edition.
 * Classic: a floor 2-10 (no 1s, one die at least the floor). V5: switches for Hunger dice
 * (no bestial failure / no messy critical) and a minimum number of 6+ dice (0-3).
 */
export function DiceRulesDialog({ open, onClose, api, campaign, location, onSaved, toast }) {
  const isV5 = editionOf(campaign) === V5;
  const [floor, setFloor] = useState('');
  const [v5, setV5] = useState(V5_OFF);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) {
      const f = location?.dice_leniency_floor;
      setFloor(f !== undefined && f !== null && f !== '' ? String(f) : '');
      setV5({ ...V5_OFF, ...(location?.dice_leniency_v5 || {}) });
    }
  }, [open, location]);

  const save = async (restore) => {
    let body;
    if (isV5) body = { dice_leniency_v5: restore ? null : v5 };
    else if (restore) body = { dice_leniency_floor: null };
    else {
      const n = parseInt(String(floor).trim(), 10);
      if (!(n >= 2 && n <= 10)) {
        toast({ tone: 'danger', title: t('dice:rules.range', 'Enter a floor from 2 to 10, or restore normal dice.') });
        return;
      }
      body = { dice_leniency_floor: n };
    }
    setSaving(true);
    const r = await api(`/campaigns/${campaign.id}/locations/${location.id}/dice-leniency`, { method: 'PUT', body });
    setSaving(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: r.data.error || t('dice:rules.failed', 'Could not update the dice rules.') });
      return;
    }
    let title = t('dice:rules.off', 'Leniency off: normal d10 randomness for this room.');
    if (isV5 && r.data.dice_leniency_v5) title = t('dice:rules.savedV5', 'V5 dice rules saved for this room.');
    else if (!isV5 && r.data.dice_leniency_floor != null) {
      title = t('dice:rules.saved', 'Leniency floor {{n}} saved for this room.', { n: r.data.dice_leniency_floor });
    }
    toast({ tone: 'ok', title });
    onSaved();
    onClose();
  };

  const room = location?.name || '';
  return (
    <Modal
      open={open}
      onClose={saving ? undefined : onClose}
      title={t('dice:rules.title', 'Room dice rules')}
      icon="d10-crit"
      size="sm"
      description={
        isV5
          ? t('dice:rules.bodyV5', 'Only for {{room}} (V5). The first two switches only change Hunger dice; normal dice keep their 1s. Willpower rerolls and Rouse checks stay random. Same as /ai dice-diff.', { room })
          : t('dice:rules.body', 'Only for {{room}} (Classic). Floor 2-10: no 1s; with 2+ dice, one die is always at least the floor. Same as /ai dice-diff <2-10>.', { room })
      }
      footer={
        <>
          <Button variant="ghost" onClick={() => save(true)} disabled={saving}>
            {t('dice:rules.restore', 'Restore normal')}
          </Button>
          <Button variant="arcane" onClick={() => save(false)} loading={saving}>
            {t('common:save', 'Save')}
          </Button>
        </>
      }
    >
      {isV5 ? (
        <div className="sr-stack">
          <Checkbox
            label={t('dice:rules.noBestial', 'No bestial failure (Hunger dice never show 1)')}
            checked={v5.no_bestial}
            onChange={(e) => setV5({ ...v5, no_bestial: e.target.checked })}
            disabled={saving}
          />
          <Checkbox
            label={t('dice:rules.noMessy', 'No messy critical (Hunger dice never show 10)')}
            checked={v5.no_messy}
            onChange={(e) => setV5({ ...v5, no_messy: e.target.checked })}
            disabled={saving}
          />
          <Select
            label={t('dice:rules.minSuccesses', 'At least this many dice show 6+')}
            hint={t('dice:rules.minSuccessesHint', 'Never more than the pool. Missing successes come from normal dice first, then Hunger dice.')}
            value={String(v5.min_successes)}
            onChange={(e) => setV5({ ...v5, min_successes: Number(e.target.value) })}
            disabled={saving}
          >
            <option value="0">{t('dice:rules.minNone', 'No minimum')}</option>
            <option value="1">1</option>
            <option value="2">2</option>
            <option value="3">3</option>
          </Select>
        </div>
      ) : (
        <Input
          type="number"
          min={2}
          max={10}
          label={t('dice:rules.floor', 'Leniency floor (2-10)')}
          value={floor}
          onChange={(e) => setFloor(e.target.value)}
          disabled={saving}
        />
      )}
    </Modal>
  );
}

/** Admin: stored rolls of this room (GET /campaigns/<c>/rolls?location_id=). */
export function DiceHistoryDialog({ open, onClose, api, campaign, location, timeZone }) {
  const [rows, setRows] = useState([]);
  const [state, setState] = useState('idle');
  useEffect(() => {
    if (!open || !campaign?.id || !location?.id) return undefined;
    let cancelled = false;
    setState('loading');
    api(`/campaigns/${campaign.id}/rolls?location_id=${location.id}&limit=100`).then((r) => {
      if (cancelled) return;
      if (!r.ok) {
        setState(r.data.error || t('dice:history.failed', 'Could not load the roll history.'));
        return;
      }
      setRows(Array.isArray(r.data) ? r.data : []);
      setState('ready');
    });
    return () => {
      cancelled = true;
    };
  }, [open, api, campaign, location]);

  return (
    <Modal open={open} onClose={onClose} title={t('dice:history.title', 'Roll history: {{room}}', { room: location?.name || '' })} icon="scroll" size="lg">
      {state === 'loading' ? <Spinner label={t('common:loading', 'Loading')} /> : null}
      {state !== 'loading' && state !== 'ready' && state !== 'idle' ? <p className="sr-error">{state}</p> : null}
      {state === 'ready' && rows.length === 0 ? <p className="sr-muted">{t('dice:history.empty', 'No rolls recorded in this room yet.')}</p> : null}
      {state === 'ready' && rows.length > 0 ? (
        <ul className="sr-dicehist">
          {rows.map((r) => (
            <li key={r.id}>
              <div className="sr-muted sr-small">{formatDateTimeInZone(r.rolled_at, timeZone)}</div>
              <div>
                <strong>{[r.username, r.character_name].filter(Boolean).join(' · ') || `#${r.user_id}`}</strong>
                {r.action_description ? ` · ${r.action_description}` : ''}
              </div>
              <div className="sr-mono sr-small">{describeRollRow(r)}</div>
            </li>
          ))}
        </ul>
      ) : null}
    </Modal>
  );
}

import React, { useEffect, useRef, useState } from 'react';
import { Button, Checkbox, Input, Modal, Spinner, Textarea } from '../../design';
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
 */
export function RollDialog({ open, onClose, campaign, location, character, speakAs, canHide, isAdmin, dice, onOpenHistory }) {
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

  // V5: prefill Hunger from the sheet each time the dialog opens.
  useEffect(() => {
    if (open && edition === V5) setHunger(sheetHunger(character));
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
    if (after == null) return;
    // Follow the sheet only if the dialog still showed the sheet's value (a typed-in Hunger stays).
    if (!asChar || Number(hunger) === before) setHunger(after);
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

/** Admin: per-room dice leniency floor (PUT …/dice-leniency). */
export function DiceRulesDialog({ open, onClose, api, campaign, location, onSaved, toast }) {
  const [floor, setFloor] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) {
      const f = location?.dice_leniency_floor;
      setFloor(f !== undefined && f !== null && f !== '' ? String(f) : '');
    }
  }, [open, location]);

  const save = async (restore) => {
    let body;
    if (restore) body = { dice_leniency_floor: null };
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
    toast({
      tone: 'ok',
      title:
        r.data.dice_leniency_floor != null
          ? t('dice:rules.saved', 'Leniency floor {{n}} saved for this room.', { n: r.data.dice_leniency_floor })
          : t('dice:rules.off', 'Leniency off: normal d10 randomness for this room.'),
    });
    onSaved();
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={saving ? undefined : onClose}
      title={t('dice:rules.title', 'Room dice rules')}
      icon="d10-crit"
      size="sm"
      description={t('dice:rules.body', 'Only for {{room}}. Floor 2-10: no 1s; with 2+ dice, one die is always at least the floor. Same as /ai dice-diff.', { room: location?.name || '' })}
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
      <Input
        type="number"
        min={2}
        max={10}
        label={t('dice:rules.floor', 'Leniency floor (2-10)')}
        value={floor}
        onChange={(e) => setFloor(e.target.value)}
        disabled={saving}
      />
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

import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Input, Select } from '../design';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import { apiFetch, errorText, getCurrentToken } from '../app/http';
import { V5_SKILL_KEYS, V5_SKILL_LABELS } from '../characterSheet/v5/constants';
import {
  ADVANTAGE_KINDS,
  SPEND_DOTS_MAX,
  ownAdvantages,
  savedBalance,
  spendApproverText,
  spendProblemText,
  spendStatusLabel,
  spendStatusTone,
  spendSummary,
  validateSpend,
} from '../characterSheet/v5/savedPoints';
import { t } from '../i18n';

const ACCENT = 'var(--sr-blood-500)';
const ITEMS_MAX = 10;
const obj = (v) => (v && typeof v === 'object' ? v : {});
const emptyItem = () => ({ name: '', kind: 'background', dots: 1 });

/** The live rule check of a spend, as the player fills it in. */
function SpendCheck({ check, ai }) {
  if (!check) {
    return <p className="sr-muted sr-small">{t('sheet:spend.fillIn', 'Fill in the spend to see the rule check.')}</p>;
  }
  if (check.ok) {
    return (
      <p className="sr-small sr-spend__ok">
        {t('sheet:spend.ok', 'Follows the rules.')}{' '}
        {ai
          ? t('sheet:spend.okAi', 'The AI Storyteller applies it at once; your Storyteller can reverse it.')
          : t('sheet:spend.okHuman', 'Your Storyteller approves it.')}
      </p>
    );
  }
  return (
    <div className="sr-small sr-spend__warn">
      <p style={{ margin: '0 0 4px' }}>{t('sheet:spend.houseRule', 'House rule: only your Storyteller can approve this.')}</p>
      <ul style={{ margin: 0, paddingLeft: '1.2rem' }}>
        {check.problems.map((p, i) => (
          <li key={i}>{spendProblemText(p)}</li>
        ))}
      </ul>
    </div>
  );
}

/** Spend saved Advantage dots or the saved specialty (owner only). */
function SpendForm({ character, info, onSent, onCancel }) {
  const wm = obj(character.wod_meta);
  const saved = info.saved;
  const ai = info.settings?.st_mode === 'ai';
  const [kind, setKind] = useState(saved.advantage_dots > 0 ? 'saved_advantage' : 'saved_specialty');
  const [items, setItems] = useState([emptyItem()]);
  const [skill, setSkill] = useState('');
  const [specName, setSpecName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const skills = obj(character.skills);

  const named = items.filter((it) => it.name.trim());
  const payload =
    kind === 'saved_advantage'
      ? { kind, items: named.map((it) => ({ name: it.name.trim(), kind: it.kind, dots: Number(it.dots) })) }
      : { kind, skill, name: specName.trim() };
  const complete = kind === 'saved_advantage' ? named.length > 0 && named.length === items.length : Boolean(skill && payload.name);
  const check = complete ? validateSpend(wm, payload, info.settings, skills) : null;
  const setItem = (i, patch) => setItems((prev) => prev.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const listId = `sr-spend-adv-${character.id}`;

  const submit = async (e) => {
    e.preventDefault();
    if (!complete) return;
    setBusy(true);
    setError('');
    const r = await apiFetch(getCurrentToken(), `/characters/${character.id}/spend-requests`, { method: 'POST', body: payload });
    setBusy(false);
    if (!r.ok) {
      setError(errorText(r.data, t('sheet:spend.failed', 'Could not send the spend.')));
      return;
    }
    onSent(r.data);
  };

  return (
    <form className="sr-spend" role="group" aria-label={t('sheet:spend.title', 'Spend saved points')} onSubmit={submit}>
      <Select
        label={t('sheet:spend.what', 'What to spend')}
        value={kind}
        onChange={(e) => setKind(e.target.value)}
        options={[
          { value: 'saved_advantage', label: t('sheet:spend.kindAdvantage', 'Advantage dots (Merits, Backgrounds, Loresheets)') },
          { value: 'saved_specialty', label: t('sheet:spend.kindSpecialty', 'The saved specialty') },
        ]}
      />
      {kind === 'saved_advantage' ? (
        <>
          <datalist id={listId}>
            {ownAdvantages(wm).map((r, i) => (
              <option key={i} value={r.name} />
            ))}
          </datalist>
          <p className="sr-muted sr-small">
            {t('sheet:spend.advHelp', 'A name you already have raises that Advantage; a new name adds one. Write the name as in the book.')}
          </p>
          {items.map((it, i) => (
            <div key={i} className="sr-spend__row">
              <Input
                label={t('sheet:spend.advName', 'Advantage {{n}}', { n: i + 1 })}
                value={it.name}
                list={listId}
                lang="en"
                autoComplete="off"
                onChange={(e) => setItem(i, { name: e.target.value })}
                fieldClassName="sr-spend__grow"
              />
              <Select
                label={t('sheet:spend.advKind', 'Kind')}
                value={it.kind}
                onChange={(e) => setItem(i, { kind: e.target.value })}
                options={ADVANTAGE_KINDS.map((k) => ({ value: k, label: k === 'merit' ? 'Merit' : k === 'background' ? 'Background' : 'Loresheet' }))}
              />
              <Select
                label={t('sheet:spend.advDots', 'Dots')}
                value={String(it.dots)}
                onChange={(e) => setItem(i, { dots: Number(e.target.value) })}
                options={Array.from({ length: SPEND_DOTS_MAX }, (_, d) => ({ value: String(d + 1), label: `+${d + 1}` }))}
              />
              {items.length > 1 ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setItems((prev) => prev.filter((_, j) => j !== i))}
                  aria-label={t('sheet:spend.removeItem', 'Remove Advantage {{n}}', { n: i + 1 })}
                >
                  ×
                </Button>
              ) : null}
            </div>
          ))}
          {items.length < ITEMS_MAX ? (
            <div>
              <Button size="sm" variant="ghost" icon="plus" onClick={() => setItems((prev) => [...prev, emptyItem()])}>
                {t('sheet:spend.addItem', 'Another Advantage')}
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="sr-spend__row">
          <Select
            label={t('sheet:spend.skill', 'Skill')}
            value={skill}
            placeholder={t('sheet:spend.pickSkill', 'Choose a skill')}
            onChange={(e) => setSkill(e.target.value)}
            options={V5_SKILL_KEYS.map((k) => ({ value: k, label: V5_SKILL_LABELS[k] }))}
          />
          <Input
            label={t('sheet:spend.specialty', 'Specialty')}
            value={specName}
            autoComplete="off"
            onChange={(e) => setSpecName(e.target.value)}
            fieldClassName="sr-spend__grow"
          />
        </div>
      )}
      <div role="status" aria-live="polite">
        <SpendCheck check={check} ai={ai} />
      </div>
      {error ? <p className="sr-small sr-spend__err">{error}</p> : null}
      <div className="sr-spend__actions">
        <Button variant="ghost" onClick={onCancel}>
          {t('common:cancel', 'Cancel')}
        </Button>
        <Button type="submit" variant="primary" loading={busy} disabled={!complete}>
          {ai && check?.ok ? t('sheet:spend.submitAi', 'Spend') : t('sheet:spend.submit', 'Ask the Storyteller')}
        </Button>
      </div>
    </form>
  );
}

/** One spend in the player's list. */
function SpendRow({ req }) {
  const pending = req.status === 'pending';
  return (
    <li>
      <div className="sr-spend__row">
        <Badge tone={spendStatusTone(req.status)}>{spendStatusLabel(req.status)}</Badge>
        {pending && req.rule_check?.house_rule ? <Badge tone="warn" icon="warning">{t('sheet:spend.houseRuleBadge', 'House rule')}</Badge> : null}
        <span lang="en">{spendSummary(req)}</span>
        {req.status !== 'pending' ? <span className="sr-muted sr-small">{spendApproverText(req)}</span> : null}
      </div>
      {req.reason ? <p className="sr-small sr-muted" style={{ margin: '2px 0 0' }}>{t('sheet:spend.reason', 'Storyteller: {{reason}}', { reason: req.reason })}</p> : null}
      {req.reverse_reason ? (
        <p className="sr-small sr-muted" style={{ margin: '2px 0 0' }}>
          {t('sheet:spend.reverseReason', 'Reversed by the Storyteller: {{reason}}', { reason: req.reverse_reason })}
        </p>
      ) : null}
    </li>
  );
}

/**
 * "Saved points" on a V5 sheet: the Advantage dots and specialty kept from creation
 * (wod_meta.saved), a Spend form for the owner, and the character's spends with their status.
 */
export default function SavedPointsBlock({ character, onChanged }) {
  const wm = obj(character?.wod_meta);
  const id = character?.id;
  const canFetch = id != null && character?.campaign_id != null;
  const [info, setInfo] = useState(null);
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    const r = await apiFetch(getCurrentToken(), `/characters/${id}/spend-requests`);
    if (r.ok && r.data && Array.isArray(r.data.requests)) setInfo(r.data);
  }, [id]);

  useEffect(() => {
    if (canFetch) load();
  }, [canFetch, load]);

  const saved = info?.saved || savedBalance(wm);
  const requests = info?.requests || [];
  if (!wm.saved && !requests.length) return null;
  const canSpend = Boolean(info?.can_spend) && (saved.advantage_dots > 0 || saved.specialty > 0);
  const parts = [];
  if (saved.advantage_dots) parts.push(t('sheet:saved.dots', { one: '{{count}} Advantage dot', other: '{{count}} Advantage dots' }, { count: saved.advantage_dots }));
  if (saved.specialty) parts.push(t('sheet:saved.specialty', { one: '{{count}} specialty', other: '{{count}} specialties' }, { count: saved.specialty }));

  const sent = (data) => {
    setOpen(false);
    setNotice(
      data.applied
        ? t('sheet:spend.applied', 'Done: the AI Storyteller approved it (rule check). Your Storyteller can still reverse it.')
        : t('sheet:spend.sent', 'Sent to your Storyteller.')
    );
    load();
    if (data.applied) onChanged?.();
  };

  return (
    <ResponsiveSheetBlock sectionId="v5-view-saved" title={t('sheet:saved.title', 'Saved points')} accent={ACCENT}>
      <p style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
        {parts.length ? parts.join(' · ') : t('sheet:saved.none', 'Nothing saved.')}
      </p>
      <p className="sr-muted sr-small" style={{ marginTop: 0 }}>
        {t('sheet:saved.help', 'Points left unspent at creation. Spend them later; the Storyteller approves.')}
      </p>
      {notice ? (
        <p role="status" className="sr-small sr-spend__ok">
          {notice}
        </p>
      ) : null}
      {canSpend && !open ? (
        <Button size="sm" variant="secondary" icon="plus" onClick={() => setOpen(true)}>
          {t('sheet:saved.spend', 'Spend…')}
        </Button>
      ) : null}
      {open && info ? <SpendForm character={character} info={info} onSent={sent} onCancel={() => setOpen(false)} /> : null}
      {requests.length ? (
        <>
          <h4 style={{ margin: '14px 0 6px', fontSize: '13px', color: 'var(--sr-arcane-300)' }}>{t('sheet:saved.requests', 'Spends')}</h4>
          <ul className="sr-spend__list">
            {requests.map((r) => (
              <SpendRow key={r.id} req={r} />
            ))}
          </ul>
        </>
      ) : null}
    </ResponsiveSheetBlock>
  );
}

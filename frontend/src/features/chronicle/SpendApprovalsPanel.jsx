import { useCallback, useEffect, useState } from 'react';
import { Badge, Button, Input, Panel, Select } from '../../design';
import { errorText } from '../../app/http';
import {
  spendApproverText,
  spendProblemText,
  spendStatusLabel,
  spendStatusTone,
  spendSummary,
} from '../../characterSheet/v5/savedPoints';
import { formatDateTimeInZone } from '../../utils/userTimeFormat';
import { t } from '../../i18n';

const ACTION_LABEL = {
  approve: () => t('chronicle:approvals.approve', 'Approve'),
  reject: () => t('chronicle:approvals.reject', 'Reject'),
  reverse: () => t('chronicle:approvals.reverse', 'Reverse'),
};

/**
 * One spend with its actions. Approving a house rule, rejecting and reversing ask to confirm
 * (with an optional reason). When the server finds that a spend breaks the rules as the sheet is
 * now (409 now_house_rule), the confirm form opens with the new problems.
 */
function SpendItem({ req, user, busy, onDecide }) {
  const [confirm, setConfirm] = useState(null);
  const [reason, setReason] = useState('');
  const [fresh, setFresh] = useState(null);
  const check = fresh || req.rule_check || {};
  const house = Boolean(check.house_rule);
  const run = async (action, why, confirmHouse) => {
    const res = await onDecide(req, action, why, confirmHouse);
    if (res && res.houseRule) {
      setFresh(res.houseRule);
      setConfirm('approve');
    } else if (res && res.ok) {
      setConfirm(null);
    }
  };
  const start = (action) => {
    if (action === 'approve' && !house) {
      run(action, '', false);
      return;
    }
    setConfirm(action);
    setReason('');
  };
  return (
    <li className="sr-approvals__item">
      <div className="sr-row">
        <strong>{req.character_name}</strong>
        <span className="sr-muted sr-small">{req.username}</span>
        {req.created_at ? <span className="sr-muted sr-small">{formatDateTimeInZone(req.created_at, user?.display_timezone || null)}</span> : null}
      </div>
      <div className="sr-row">
        <Badge tone={spendStatusTone(req.status)}>{spendStatusLabel(req.status)}</Badge>
        {house ? (
          <Badge tone="warn" icon="warning">
            {t('chronicle:approvals.houseRule', 'House rule')}
          </Badge>
        ) : null}
        <span lang="en">{spendSummary(req)}</span>
        {req.status !== 'pending' ? <span className="sr-muted sr-small">{spendApproverText(req)}</span> : null}
      </div>
      {fresh ? <p className="sr-small sr-approvals__problems-intro">{t('chronicle:approvals.nowHouseRule', 'The sheet changed since the player asked: this spend breaks the rules now.')}</p> : null}
      {house ? (
        <ul className="sr-small sr-approvals__problems">
          {(check.problems || []).map((p, i) => (
            <li key={i}>{spendProblemText(p)}</li>
          ))}
        </ul>
      ) : null}
      {req.reason ? <p className="sr-small sr-muted">{t('chronicle:approvals.reasonShown', 'Reason: {{reason}}', { reason: req.reason })}</p> : null}
      {req.reverse_reason ? (
        <p className="sr-small sr-muted">{t('chronicle:approvals.reverseReasonShown', 'Why reversed: {{reason}}', { reason: req.reverse_reason })}</p>
      ) : null}
      {confirm ? (
        <form
          className="sr-row sr-row--end"
          onSubmit={(e) => {
            e.preventDefault();
            run(confirm, reason, confirm === 'approve');
          }}
        >
          <Input
            label={confirm === 'approve' ? t('chronicle:approvals.reasonApprove', 'Why allow this house rule? (optional)') : t('chronicle:approvals.reason', 'Reason for the player (optional)')}
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
            fieldClassName="sr-grow"
          />
          <Button variant="ghost" onClick={() => setConfirm(null)}>
            {t('common:cancel', 'Cancel')}
          </Button>
          <Button type="submit" variant={confirm === 'approve' ? 'primary' : 'danger'} loading={busy}>
            {ACTION_LABEL[confirm]()}
          </Button>
        </form>
      ) : (
        <div className="sr-row">
          {req.status === 'pending' ? (
            <>
              <Button size="sm" variant="primary" loading={busy} onClick={() => start('approve')}>
                {ACTION_LABEL.approve()}
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => start('reject')}>
                {ACTION_LABEL.reject()}
              </Button>
            </>
          ) : null}
          {req.status === 'approved' ? (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => start('reverse')}>
              {ACTION_LABEL.reverse()}
            </Button>
          ) : null}
        </div>
      )}
    </li>
  );
}

/**
 * The Storyteller's "Approvals" card (V5 chronicles): players' spends of saved points. In AI
 * Storyteller mode the rule check has already approved the rule-following ones; they show here to
 * be reversed if needed (so the card opens on all spends, pending first). House rules always wait
 * for a person.
 */
export default function SpendApprovalsPanel({ api, campaignId, user, toast, initialStMode = 'human' }) {
  const [filter, setFilter] = useState(initialStMode === 'ai' ? 'all' : 'pending');
  const [rows, setRows] = useState(null);
  const [stMode, setStMode] = useState(initialStMode);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    const r = await api(`/campaigns/${campaignId}/spend-requests${filter === 'all' ? '' : `?status=${filter}`}`);
    setRows(r.ok && Array.isArray(r.data.requests) ? r.data.requests : []);
    if (r.ok && r.data.st_mode) setStMode(r.data.st_mode);
  }, [api, campaignId, filter]);

  useEffect(() => {
    load();
  }, [load]);

  /** PATCH one spend. Resolves to { ok } or { houseRule: rule_check } (confirm needed). */
  const decide = async (req, action, reason, confirmHouseRule) => {
    setBusyId(req.id);
    const body = { action };
    if (String(reason || '').trim()) body.reason = reason.trim();
    if (confirmHouseRule) body.confirm_house_rule = true;
    const r = await api(`/campaigns/${campaignId}/spend-requests/${req.id}`, { method: 'PATCH', body });
    setBusyId(null);
    if (!r.ok) {
      if (r.status === 409 && r.data && r.data.error_code === 'now_house_rule' && r.data.rule_check) {
        toast({ tone: 'warn', title: t('chronicle:approvals.confirmNeeded', 'This spend breaks the rules now: check the problems and confirm.') });
        return { houseRule: r.data.rule_check };
      }
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:approvals.failed', 'Could not update the spend.')) });
      load();
      return { ok: false };
    }
    const done = {
      approve: () => t('chronicle:approvals.approved', 'Approved and added to the sheet.'),
      reject: () => t('chronicle:approvals.rejected', 'Rejected.'),
      reverse: () => t('chronicle:approvals.reversed', 'Reversed: the sheet is as it was before.'),
    };
    toast({ tone: 'ok', title: done[action]() });
    load();
    return { ok: true };
  };

  return (
    <Panel title={t('chronicle:approvals.title', 'Approvals')} icon="scroll">
      <p className="sr-muted sr-small">
        {stMode === 'ai'
          ? t('chronicle:approvals.introAi', 'AI Storyteller mode: spends of saved points that follow the rules are approved at once by the rule check and listed here; you can reverse them. House rules wait for you.')
          : t('chronicle:approvals.intro', 'Players spend the points they saved at creation here; nothing changes on a sheet until you approve.')}
      </p>
      <Select
        label={t('chronicle:approvals.show', 'Show')}
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        options={[
          { value: 'pending', label: t('chronicle:approvals.showPending', 'Waiting for you') },
          { value: 'all', label: t('chronicle:approvals.showAll', 'All spends') },
        ]}
        fieldClassName="sr-field--short"
      />
      {rows == null ? null : rows.length === 0 ? (
        <p className="sr-muted">{filter === 'pending' ? t('chronicle:approvals.nonePending', 'Nothing waiting.') : t('chronicle:approvals.none', 'No spends yet.')}</p>
      ) : (
        <ul className="sr-approvals">
          {rows.map((req) => (
            <SpendItem key={req.id} req={req} user={user} busy={busyId === req.id} onDecide={decide} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

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

/** One spend with its actions. A house-rule approval, a rejection and a reversal ask to confirm. */
function SpendItem({ req, user, busy, onDecide }) {
  const [confirm, setConfirm] = useState(null);
  const [reason, setReason] = useState('');
  const house = Boolean(req.rule_check?.house_rule);
  const start = (action) => {
    if (action === 'approve' && !house) {
      onDecide(req, action, '');
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
      {house ? (
        <ul className="sr-small sr-approvals__problems">
          {(req.rule_check.problems || []).map((p, i) => (
            <li key={i}>{spendProblemText(p)}</li>
          ))}
        </ul>
      ) : null}
      {req.reason ? <p className="sr-small sr-muted">{t('chronicle:approvals.reasonShown', 'Reason: {{reason}}', { reason: req.reason })}</p> : null}
      {confirm ? (
        <form
          className="sr-row sr-row--end"
          onSubmit={(e) => {
            e.preventDefault();
            onDecide(req, confirm, reason);
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
              <Button size="sm" variant="secondary" onClick={() => start('reject')}>
                {ACTION_LABEL.reject()}
              </Button>
            </>
          ) : null}
          {req.status === 'approved' ? (
            <Button size="sm" variant="secondary" onClick={() => start('reverse')}>
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
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await api(`/campaigns/${campaignId}/spend-requests${filter === 'all' ? '' : `?status=${filter}`}`);
    setRows(r.ok && Array.isArray(r.data.requests) ? r.data.requests : []);
    if (r.ok && r.data.st_mode) setStMode(r.data.st_mode);
  }, [api, campaignId, filter]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (req, action, reason) => {
    setBusy(true);
    const body = { action };
    if (String(reason || '').trim()) body.reason = reason.trim();
    const r = await api(`/campaigns/${campaignId}/spend-requests/${req.id}`, { method: 'PATCH', body });
    setBusy(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:approvals.failed', 'Could not update the spend.')) });
      load();
      return;
    }
    const done = {
      approve: () => t('chronicle:approvals.approved', 'Approved and added to the sheet.'),
      reject: () => t('chronicle:approvals.rejected', 'Rejected.'),
      reverse: () => t('chronicle:approvals.reversed', 'Reversed: the sheet is as it was before.'),
    };
    toast({ tone: 'ok', title: done[action]() });
    load();
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
            <SpendItem key={req.id} req={req} user={user} busy={busy} onDecide={decide} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

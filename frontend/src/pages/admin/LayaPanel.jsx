import { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Kbd, Panel, Select } from '../../design';
import { t } from '../../i18n';
import { layaApi } from './layaApi';
import './laya.css';

/**
 * Admin "Laya" tab: label player chat (in character? intent?) and evaluate Laya against the labels.
 * Message text is always rendered as React text (never as HTML).
 * Keys (outside form fields): I / O = in / out of character, 1-5 = intent, Enter = save,
 * J / K (or arrow down / up) = next / previous message.
 */

export const INTENTS = ['dice', 'combat', 'rules_question', 'roleplay', 'general'];
const PER_PAGE = 25;
const POLL_MS = 1500;
const DEFAULT_STALE_SEC = 30 * 60; // the backend sends the real limit (it grows with the label count)

export const intentLabels = () => ({
  dice: t('laya:intent.dice', 'Dice'),
  combat: t('laya:intent.combat', 'Combat'),
  rules_question: t('laya:intent.rules_question', 'Rules question'),
  roleplay: t('laya:intent.roleplay', 'Roleplay'),
  general: t('laya:intent.general', 'General'),
});

const oocLabels = () => ({
  in_character: t('laya:ooc.in_character', 'In character'),
  out_of_character: t('laya:ooc.out_of_character', 'Out of character'),
});

const stateLabels = () => ({
  unlabelled: t('laya:state.unlabelled', 'Unlabelled'),
  labelled: t('laya:state.labelled', 'Labelled'),
  stale: t('laya:state.stale', 'Text changed since labelled'),
});

const languageLabels = () => ({
  en: t('laya:lang.en', 'English'),
  el: t('laya:lang.el', 'Greek'),
  unknown: t('laya:lang.unknown', 'Unknown'),
});

const num = (v) => (v == null ? '–' : Number(v).toFixed(3));

/** Shortcuts never fire while typing or while focus is on something Enter/letters already drive. */
export function isShortcutTarget(el) {
  if (!el || !el.closest) return true;
  const tag = (el.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable) return false;
  return !el.closest('a, button, [role="tab"], [role="link"], [role="button"]');
}

function draftOf(item) {
  if (item && item.label && item.state === 'labelled') return { in_character: item.label.in_character, intent: item.label.intent };
  return { in_character: null, intent: null };
}

function MetricsTable({ title, metrics, names, testId }) {
  if (!metrics) return null;
  const ci = metrics.accuracy_ci95;
  return (
    <div className="sr-admin__group" data-testid={testId}>
      <div className="sr-admin__group-title">{title}</div>
      <p className="sr-admin__muted">
        {t('laya:report.accuracy', 'Accuracy {{acc}} ({{correct}} of {{n}})', { acc: num(metrics.accuracy), correct: metrics.correct, n: metrics.n })}
        {ci ? ` · ${t('laya:report.ci', '95% interval {{lo}}–{{hi}}', { lo: num(ci[0]), hi: num(ci[1]) })}` : ''}
        {` · ${t('laya:report.macroF1', 'macro-F1 {{f1}}', { f1: num(metrics.macro_f1) })}`}
      </p>
      <div className="sr-admin__tablewrap">
        <table className="sr-admin__table sr-laya__metrics">
          <thead>
            <tr>
              <th scope="col">{t('laya:report.col.label', 'Label')}</th>
              <th scope="col">{t('laya:report.col.n', 'n (labelled)')}</th>
              <th scope="col">{t('laya:report.col.predicted', 'Predicted')}</th>
              <th scope="col">{t('laya:report.col.precision', 'Precision')}</th>
              <th scope="col">{t('laya:report.col.recall', 'Recall')}</th>
              <th scope="col">F1</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.per_label || {}).map(([lab, v]) => (
              <tr key={lab}>
                <th scope="row">{names[lab] || lab}</th>
                <td>
                  {v.n}
                  {v.n > 0 && v.too_small ? (
                    <span className="sr-laya__small"> {t('laya:report.nTooSmall', '(too few)')}</span>
                  ) : null}
                </td>
                <td>{v.predicted}</td>
                <td>{num(v.precision)}</td>
                <td>{num(v.recall)}</td>
                <td>{num(v.f1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ConfusionMatrix confusion={metrics.confusion} names={names} title={title} />
    </div>
  );
}

function ConfusionMatrix({ confusion, names, title }) {
  if (!confusion) return null;
  const { labels, matrix } = confusion;
  return (
    <div className="sr-admin__tablewrap">
      <table className="sr-admin__table sr-laya__confusion">
        <caption className="sr-laya__caption">
          {t('laya:report.confusion', 'Confusion matrix, {{title}}: rows = human label, columns = Laya', { title })}
        </caption>
        <thead>
          <tr>
            <th scope="col">{t('laya:report.goldVsPred', 'Human \\ Laya')}</th>
            {labels.map((l) => <th key={l} scope="col">{names[l] || l}</th>)}
          </tr>
        </thead>
        <tbody>
          {labels.map((g, i) => (
            <tr key={g}>
              <th scope="row">{names[g] || g}</th>
              {matrix[i].map((c, j) => (
                <td key={labels[j]} className={`${i === j ? 'is-diag' : ''} ${c && i !== j ? 'is-miss' : ''}`.trim() || undefined}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Report({ run, report }) {
  const INT = intentLabels();
  const OOC = oocLabels();
  const LANG = languageLabels();
  if (!run) return <p className="sr-admin__muted">{t('laya:report.none', 'No evaluation yet. Label some messages, then run one.')}</p>;
  if (run.status === 'running') return <p className="sr-admin__muted" role="status">{t('laya:report.running', 'Evaluation running…')}</p>;
  if (run.status === 'failed' || !report) {
    return <p className="sr-admin__error">{t('laya:report.failed', 'The last evaluation failed. See the backend logs.')}</p>;
  }
  const model = report.model || {};
  return (
    <div className="sr-admin__stack" data-testid="laya-report">
      <dl className="sr-admin__stats">
        <dt>{t('laya:report.when', 'Run at')}</dt>
        <dd>{report.created_at}</dd>
        <dt>{t('laya:report.model', 'Model')}</dt>
        <dd>
          {model.name || '?'} <span className="sr-admin__code">{model.config_sha256 || ''}</span>
        </dd>
        <dt>{t('laya:report.n', 'Messages evaluated')}</dt>
        <dd>{report.n}</dd>
        <dt>{t('laya:report.threshold', 'In-character threshold')}</dt>
        <dd>{`P(IC) ≥ ${report.ooc_threshold}`}</dd>
        {report.errors ? (
          <>
            <dt>{t('laya:report.errors', 'Laya errors')}</dt>
            <dd>{report.errors}</dd>
          </>
        ) : null}
        {report.stale_labels_skipped ? (
          <>
            <dt>{t('laya:report.stale', 'Stale labels skipped')}</dt>
            <dd>{report.stale_labels_skipped}</dd>
          </>
        ) : null}
      </dl>
      {report.sample_too_small ? (
        <p className="sr-admin__warn" role="note" data-testid="laya-too-small">
          {t('laya:report.tooSmall', 'Sample too small: fewer than {{total}} messages, or a label with fewer than {{per}}. Read these numbers as examples, not as rates.', {
            total: report.min_n_total,
            per: report.min_n_per_label,
          })}
        </p>
      ) : null}
      <MetricsTable title={t('laya:report.oocTitle', 'In character (OOC monitor)')} metrics={report.ooc} names={OOC} testId="laya-ooc" />
      <MetricsTable title={t('laya:report.intentTitle', 'Intent')} metrics={report.intent} names={INT} testId="laya-intent" />

      <div className="sr-admin__group">
        <div className="sr-admin__group-title">{t('laya:report.byLanguage', 'By language (detected)')}</div>
        <div className="sr-admin__tablewrap">
          <table className="sr-admin__table">
            <thead>
              <tr>
                <th scope="col">{t('laya:report.col.language', 'Language')}</th>
                <th scope="col">n</th>
                <th scope="col">{t('laya:report.col.oocAcc', 'In-character accuracy')}</th>
                <th scope="col">{t('laya:report.col.intentAcc', 'Intent accuracy')}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.languages || {}).map(([lang, v]) => (
                <tr key={lang}>
                  <th scope="row">{LANG[lang] || lang}</th>
                  <td>{v.n}</td>
                  <td>{num(v.ooc_accuracy)}</td>
                  <td>{num(v.intent_accuracy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="sr-admin__group">
        <div className="sr-admin__group-title">
          {t('laya:report.misclassified', 'Misclassified ({{n}})', { n: (report.misclassified || []).length })}
        </div>
        {(report.misclassified || []).length === 0 ? (
          <p className="sr-admin__muted">{t('laya:report.noMisses', 'None.')}</p>
        ) : (
          <div className="sr-admin__tablewrap">
            <table className="sr-admin__table" data-testid="laya-misses">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">{t('laya:report.col.human', 'Human')}</th>
                  <th scope="col">Laya</th>
                  <th scope="col">{t('laya:report.col.text', 'Text')}</th>
                </tr>
              </thead>
              <tbody>
                {report.misclassified.map((w) => (
                  <tr key={w.message_id}>
                    <td className="sr-admin__mono">{w.message_id}</td>
                    <td>
                      {OOC[w.gold.in_character ? 'in_character' : 'out_of_character']} · {INT[w.gold.intent] || w.gold.intent}
                    </td>
                    <td>
                      <span className={w.wrong.includes('ooc') ? 'sr-laya__wrong' : undefined}>
                        {OOC[w.pred.in_character ? 'in_character' : 'out_of_character']} ({num(w.pred.p_ic)})
                      </span>
                      {' · '}
                      <span className={w.wrong.includes('intent') ? 'sr-laya__wrong' : undefined}>
                        {INT[w.pred.intent] || w.pred.intent} ({num(w.pred.intent_score)})
                      </span>
                    </td>
                    <td className="is-note">{w.excerpt == null ? t('laya:report.deleted', '(message deleted)') : w.excerpt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function History({ history, onOpen, current }) {
  if (!history || history.length < 2) return null;
  return (
    <div className="sr-admin__group">
      <div className="sr-admin__group-title">{t('laya:history.title', 'Earlier runs')}</div>
      <div className="sr-admin__tablewrap">
        <table className="sr-admin__table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">{t('laya:history.when', 'Started')}</th>
              <th scope="col">{t('laya:history.status', 'Status')}</th>
              <th scope="col">n</th>
              <th scope="col">{t('laya:report.col.oocAcc', 'In-character accuracy')}</th>
              <th scope="col">{t('laya:report.col.intentAcc', 'Intent accuracy')}</th>
              <th scope="col"><span className="sr-visually-hidden">{t('laya:history.open', 'Open')}</span></th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td className="sr-admin__mono">{h.id}</td>
                <td className="is-small">{h.started_at}</td>
                <td>{h.status}{h.source === 'cli' ? ' (CLI)' : ''}</td>
                <td>{h.n == null ? '–' : h.n}</td>
                <td>{num(h.ooc_accuracy)}</td>
                <td>{num(h.intent_accuracy)}</td>
                <td>
                  <Button size="sm" variant="ghost" disabled={h.id === current || h.status !== 'done'} onClick={() => onOpen(h.id)}>
                    {t('laya:history.open', 'Open')}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function LayaPanel({ token, showSuccess, showError }) {
  // AdminPage passes new toast callbacks on every render; keep them out of effect deps.
  const toastRef = useRef({ showSuccess, showError });
  toastRef.current = { showSuccess, showError };
  const ok = useCallback((m) => toastRef.current.showSuccess(m), []);
  const fail = useCallback((m) => toastRef.current.showError(m), []);
  const [filters, setFilters] = useState({ status: 'unlabelled', campaignId: '', language: '' });
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(0);
  const [draft, setDraft] = useState({ in_character: null, intent: null });
  const [saving, setSaving] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [starting, setStarting] = useState(false);
  const pollRef = useRef(null);
  const pollStartRef = useRef(null);
  const listRef = useRef(null);
  const [waitExpired, setWaitExpired] = useState(false);
  const itemRefs = useRef({});

  const items = (data && data.items) || [];
  const current = items[selected] || null;

  const load = useCallback(async (keepSelection = false) => {
    try {
      const r = await layaApi.listMessages(token, { ...filters, page, perPage: PER_PAGE });
      const d = await r.json().catch(() => null);
      if (!r.ok || !d) {
        fail((d && d.error) || t('laya:error.load', 'Could not load messages'));
        return;
      }
      setData(d);
      setSelected((s) => (keepSelection ? Math.min(s, Math.max(0, (d.items || []).length - 1)) : 0));
    } catch {
      fail(t('laya:error.load', 'Could not load messages'));
    }
  }, [token, filters, page, fail]);

  const loadReport = useCallback(async (id) => {
    try {
      const r = await layaApi.getReport(token, id);
      const d = await r.json().catch(() => null);
      if (r.ok && d) setReportData(d);
      return d;
    } catch {
      return null;
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadReport(); }, [loadReport]);
  useEffect(() => () => clearTimeout(pollRef.current), []);
  useEffect(() => { setDraft(draftOf(current)); }, [current && current.id, current && current.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll while a run is 'running'. The backend marks crashed runs failed; as a backstop, stop
  // waiting here too once the run has been running longer than the backend's stale limit.
  const poll = useCallback(() => {
    clearTimeout(pollRef.current);
    if (pollStartRef.current == null) pollStartRef.current = Date.now();
    pollRef.current = setTimeout(async () => {
      const d = await loadReport();
      const stop = () => {
        pollRef.current = null;
        pollStartRef.current = null;
      };
      if (!d || !d.run || d.run.status !== 'running') {
        stop();
        return;
      }
      const limitMs = (d.stale_after_sec || DEFAULT_STALE_SEC) * 1000 + 2 * POLL_MS;
      if (Date.now() - pollStartRef.current > limitMs) {
        setWaitExpired(true);
        stop();
        return;
      }
      poll();
    }, POLL_MS);
  }, [loadReport]);

  useEffect(() => {
    if (reportData && reportData.run && reportData.run.status === 'running' && !pollRef.current && !waitExpired) poll();
  }, [reportData, poll, waitExpired]);

  const save = useCallback(async () => {
    if (!current || draft.in_character == null || !draft.intent || saving) return;
    setSaving(true);
    try {
      const r = await layaApi.setLabel(token, current.id, draft);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        fail(d.error || t('laya:error.save', 'Could not save the label'));
        return;
      }
      // In the "unlabelled" view the saved row drops out, so the same index is the next message.
      if (filters.status !== 'unlabelled') setSelected((s) => Math.min(s + 1, items.length - 1));
      await load(true);
    } catch {
      fail(t('laya:error.save', 'Could not save the label'));
    } finally {
      setSaving(false);
    }
  }, [current, draft, saving, token, filters.status, items.length, load, fail]);

  const clear = async () => {
    if (!current) return;
    try {
      const r = await layaApi.clearLabel(token, current.id);
      if (!r.ok) {
        fail(t('laya:error.clear', 'Could not clear the label'));
        return;
      }
      await load(true);
    } catch {
      fail(t('laya:error.clear', 'Could not clear the label'));
    }
  };

  const runEvaluation = async () => {
    setStarting(true);
    try {
      const r = await layaApi.runEvaluation(token);
      const d = await r.json().catch(() => ({}));
      if (r.status === 202) {
        setWaitExpired(false);
        pollStartRef.current = null;
        ok(t('laya:eval.started', 'Evaluation started.'));
        await loadReport();
        poll();
      } else if (r.status === 409) {
        fail(t('laya:eval.busy', 'An evaluation is already running.'));
        poll();
      } else {
        fail(d.error || t('laya:eval.failed', 'Could not start the evaluation'));
      }
    } catch {
      fail(t('laya:eval.failed', 'Could not start the evaluation'));
    } finally {
      setStarting(false);
    }
  };

  const move = useCallback((delta) => {
    setSelected((s) => Math.max(0, Math.min(items.length - 1, s + delta)));
  }, [items.length]);

  useEffect(() => {
    const node = current && itemRefs.current[current.id];
    if (node && node.scrollIntoView) node.scrollIntoView({ block: 'nearest' });
  }, [current]);

  const focusList = () => {
    if (listRef.current) listRef.current.focus();
  };

  // Scoped to the panel (onKeyDown on its root), and only when focus isn't on a field, link,
  // tab or button: click a message to put focus on the list.
  const onKeyDown = (e) => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || !isShortcutTarget(e.target)) return;
    if (!items.length) return;
    const k = e.key.toLowerCase();
    let handled = true;
    if (k === 'i') setDraft((d) => ({ ...d, in_character: true }));
    else if (k === 'o') setDraft((d) => ({ ...d, in_character: false }));
    else if (/^[1-5]$/.test(k)) setDraft((d) => ({ ...d, intent: INTENTS[Number(k) - 1] }));
    else if (k === 'enter') save();
    else if (k === 'j' || k === 'arrowdown') move(1);
    else if (k === 'k' || k === 'arrowup') move(-1);
    else handled = false;
    if (handled) e.preventDefault();
  };

  const setFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  const INT = intentLabels();
  const OOC = oocLabels();
  const STATE = stateLabels();
  const LANG = languageLabels();
  const counts = (data && data.counts) || null;
  const pages = data ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : 1;
  const runRaw = reportData && reportData.run;
  const running = !!(runRaw && runRaw.status === 'running' && !waitExpired);
  const shownRun = runRaw && runRaw.status === 'running' && waitExpired ? { ...runRaw, status: 'failed' } : runRaw;

  return (
    <div className="sr-admin__stack sr-laya" data-testid="laya-panel" onKeyDown={onKeyDown}>
      <Panel title={t('laya:progress.title', 'Progress')} className="sr-admin__panel">
        {counts ? (
          <dl className="sr-admin__stats" data-testid="laya-counts">
            <dt>{t('laya:progress.eligible', 'Player chat messages')}</dt>
            <dd>{counts.eligible}</dd>
            <dt>{t('laya:progress.labelled', 'Labelled')}</dt>
            <dd>{counts.labelled}</dd>
            <dt>{t('laya:progress.unlabelled', 'Not labelled')}</dt>
            <dd>{counts.unlabelled}</dd>
            {counts.stale ? (
              <>
                <dt>{t('laya:progress.stale', 'Text changed since labelled')}</dt>
                <dd>{counts.stale}</dd>
              </>
            ) : null}
            <dt>{t('laya:progress.balance', 'Labels so far')}</dt>
            <dd>
              {`${OOC.in_character} ${counts.in_character} · ${OOC.out_of_character} ${counts.out_of_character} · `}
              {INTENTS.map((i) => `${INT[i]} ${(counts.intents || {})[i] || 0}`).join(' · ')}
            </dd>
          </dl>
        ) : (
          <p className="sr-admin__muted">{t('laya:loading', 'Loading…')}</p>
        )}
        {counts && counts.scan_limit_reached ? (
          <p className="sr-admin__warn">{t('laya:progress.scanLimit', 'Only the newest 5000 messages are listed.')}</p>
        ) : null}
      </Panel>

      <Panel title={t('laya:queue.title', 'Label queue')} className="sr-admin__panel">
        <p className="sr-admin__muted">
          {t('laya:queue.help', 'Player chat only (no Storyteller replies, dice or system rows). Label what the player wrote: is it the character speaking or acting, and what is it about.')}
        </p>
        <div className="sr-admin__row">
          <Select
            label={t('laya:filter.status', 'Show')}
            value={filters.status}
            onChange={(e) => setFilter('status', e.target.value)}
            options={[
              { value: 'unlabelled', label: STATE.unlabelled },
              { value: 'labelled', label: STATE.labelled },
              { value: 'stale', label: STATE.stale },
              { value: 'all', label: t('laya:filter.all', 'All') },
            ]}
          />
          <Select
            label={t('laya:filter.campaign', 'Chronicle')}
            value={filters.campaignId}
            onChange={(e) => setFilter('campaignId', e.target.value)}
            options={[
              { value: '', label: t('laya:filter.allCampaigns', 'All chronicles') },
              ...((data && data.campaigns) || []).map((c) => ({ value: String(c.id), label: `${c.name} (${c.n})` })),
            ]}
          />
          <Select
            label={t('laya:filter.language', 'Language')}
            value={filters.language}
            onChange={(e) => setFilter('language', e.target.value)}
            options={[
              { value: '', label: t('laya:filter.allLanguages', 'All languages') },
              { value: 'en', label: LANG.en },
              { value: 'el', label: LANG.el },
              { value: 'unknown', label: LANG.unknown },
            ]}
          />
        </div>
        <p className="sr-admin__muted sr-laya__keys">
          <Kbd>I</Kbd> / <Kbd>O</Kbd> {t('laya:keys.ooc', 'in / out of character')} · <Kbd>1</Kbd>–<Kbd>5</Kbd> {t('laya:keys.intent', 'intent')} ·{' '}
          <Kbd>Enter</Kbd> {t('laya:keys.save', 'save')} · <Kbd>J</Kbd> / <Kbd>K</Kbd> {t('laya:keys.move', 'next / previous')}
          {' '}({t('laya:keys.focus', 'click a message first')})
        </p>

        {data && items.length === 0 ? (
          <EmptyState glyph="eye" title={t('laya:queue.emptyTitle', 'Nothing here')}>
            {t('laya:queue.empty', 'No messages match these filters.')}
          </EmptyState>
        ) : null}

        <ol ref={listRef} tabIndex={0} className="sr-laya__list" aria-label={t('laya:queue.listLabel', 'Messages to label')} data-testid="laya-list">
          {items.map((it, idx) => {
            const isCurrent = idx === selected;
            return (
              <li
                key={it.id}
                ref={(n) => { itemRefs.current[it.id] = n; }}
                className={`sr-laya__item${isCurrent ? ' is-current' : ''}`}
                aria-current={isCurrent ? 'true' : undefined}
                data-testid={`laya-item-${it.id}`}
              >
                <button type="button" className="sr-laya__pick" onClick={() => { setSelected(idx); focusList(); }}>
                  <span className="sr-laya__meta">
                    #{it.id} · {it.campaign_name} · {it.location_name || '—'} · {it.message_type} · {LANG[it.language] || it.language}
                  </span>
                  {/* Plain text on purpose: chat is user input and is never rendered as HTML. */}
                  <span className="sr-laya__text">{it.content}</span>
                </button>
                <div className="sr-laya__status">
                  <Badge tone={it.state === 'labelled' ? 'ok' : it.state === 'stale' ? 'warn' : 'neutral'}>{STATE[it.state]}</Badge>
                  {it.label ? (
                    <span className="sr-admin__muted">
                      {OOC[it.label.in_character ? 'in_character' : 'out_of_character']} · {INT[it.label.intent] || it.label.intent}
                      {it.label.labelled_by ? ` · ${it.label.labelled_by}` : ''}
                    </span>
                  ) : null}
                </div>
                {isCurrent ? (
                  <div className="sr-laya__controls" data-testid="laya-controls">
                    <div className="sr-admin__row" role="group" aria-label={t('laya:controls.oocGroup', 'In character?')}>
                      <Button size="sm" variant={draft.in_character === true ? 'primary' : 'secondary'} aria-pressed={draft.in_character === true}
                        onClick={() => { setDraft((d) => ({ ...d, in_character: true })); focusList(); }}>
                        {OOC.in_character} <Kbd>I</Kbd>
                      </Button>
                      <Button size="sm" variant={draft.in_character === false ? 'primary' : 'secondary'} aria-pressed={draft.in_character === false}
                        onClick={() => { setDraft((d) => ({ ...d, in_character: false })); focusList(); }}>
                        {OOC.out_of_character} <Kbd>O</Kbd>
                      </Button>
                    </div>
                    <div className="sr-admin__row" role="group" aria-label={t('laya:controls.intentGroup', 'Intent')}>
                      {INTENTS.map((i, n) => (
                        <Button key={i} size="sm" variant={draft.intent === i ? 'primary' : 'secondary'} aria-pressed={draft.intent === i}
                          onClick={() => { setDraft((d) => ({ ...d, intent: i })); focusList(); }}>
                          {INT[i]} <Kbd>{n + 1}</Kbd>
                        </Button>
                      ))}
                    </div>
                    <div className="sr-admin__row">
                      <Button size="sm" variant="primary" disabled={draft.in_character == null || !draft.intent || saving} onClick={() => { save(); focusList(); }}>
                        {t('laya:controls.save', 'Save label')}
                      </Button>
                      {it.label ? (
                        <Button size="sm" variant="ghost" onClick={() => { clear(); focusList(); }}>{t('laya:controls.clear', 'Clear label')}</Button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>

        {data && data.total > PER_PAGE ? (
          <div className="sr-admin__row">
            <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>{t('laya:page.prev', 'Previous')}</Button>
            <span className="sr-admin__muted">{t('laya:page.of', 'Page {{page}} of {{pages}}', { page, pages })}</span>
            <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>{t('laya:page.next', 'Next')}</Button>
          </div>
        ) : null}
      </Panel>

      <Panel
        title={t('laya:eval.title', 'Evaluation')}
        className="sr-admin__panel"
        actions={
          <Button size="sm" variant="primary" onClick={runEvaluation} disabled={running || starting}>
            {running ? t('laya:eval.running', 'Running…') : t('laya:eval.run', 'Run evaluation')}
          </Button>
        }
      >
        <p className="sr-admin__muted">
          {t('laya:eval.help', 'Runs Laya on every labelled message, the same way the OOC monitor does, and compares. The report keeps message numbers only; the text is looked up when you open it. The same report from a terminal: python scripts/laya_eval.py in the backend container.')}
        </p>
        <Report run={shownRun} report={reportData && reportData.report} />
        <History history={reportData && reportData.history} current={reportData && reportData.run && reportData.run.id} onOpen={(id) => loadReport(id)} />
      </Panel>
    </div>
  );
}

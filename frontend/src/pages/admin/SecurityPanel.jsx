import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Button, EmptyState, Input, Panel, Select } from '../../design';
import { api } from '../../utils/api';
import { formatNumber, t } from '../../i18n';
import formatWhen from './formatWhen';

/** Event types the backend writes to auth_events (backend/services/auth_events_query.py). */
export const AUTH_EVENT_TYPES = [
  'login',
  'login_failed',
  'login_blocked',
  'login_disabled',
  'lockout',
  'logout',
  'logout_all',
  'refresh_reuse',
  'register',
  'invite_invalid',
  'password_changed',
  'password_change_failed',
];

export const PAGE_SIZES = [25, 50, 100];

/** Labels are read at render time so a language switch picks them up. */
export const eventLabels = () => ({
  login: t('admin:security.event.login', 'Signed in'),
  login_failed: t('admin:security.event.login_failed', 'Failed sign-in'),
  login_blocked: t('admin:security.event.login_blocked', 'Sign-in blocked (locked)'),
  login_disabled: t('admin:security.event.login_disabled', 'Sign-in refused (account disabled)'),
  lockout: t('admin:security.event.lockout', 'Locked out'),
  logout: t('admin:security.event.logout', 'Signed out'),
  logout_all: t('admin:security.event.logout_all', 'Signed out everywhere'),
  refresh_reuse: t('admin:security.event.refresh_reuse', 'Reused session token (sessions revoked)'),
  register: t('admin:security.event.register', 'Registered'),
  invite_invalid: t('admin:security.event.invite_invalid', 'Invalid invite code'),
  password_changed: t('admin:security.event.password_changed', 'Password changed'),
  password_change_failed: t('admin:security.event.password_change_failed', 'Password change failed'),
});

const EVENT_TONES = {
  login: 'ok',
  login_failed: 'warn',
  login_blocked: 'danger',
  login_disabled: 'danger',
  lockout: 'danger',
  logout: 'neutral',
  logout_all: 'neutral',
  refresh_reuse: 'danger',
  register: 'arcane',
  invite_invalid: 'warn',
  password_changed: 'gold',
  password_change_failed: 'warn',
};

/** Server messages of POST /admin/auth/unlock and GET /admin/auth-events, translated. */
const serverError = (msg, fallback) => ({
  'username or ip required': t('admin:security.unlock.needOne', 'Enter a username, an IP address, or both.'),
  'ip must be an IPv4 or IPv6 address': t('admin:security.ipInvalid', 'Enter one exact IPv4 or IPv6 address (no wildcards or ranges).'),
}[msg] || fallback);

/** The non-secret detail fields the backend passes through, as short readable text. */
export function describeDetails(details) {
  if (!details || typeof details !== 'object') return '';
  const parts = [];
  if (details.known_user === true) parts.push(t('admin:security.details.knownUser', 'existing account'));
  if (details.known_user === false) parts.push(t('admin:security.details.unknownUser', 'no such account'));
  if (details.seconds != null) {
    parts.push(t('admin:security.details.lockedFor', 'locked for {{minutes}} min', { minutes: formatNumber(Math.ceil(Number(details.seconds) / 60)) }));
  }
  if (details.retry_after != null) {
    parts.push(t('admin:security.details.retryAfter', 'retry in {{seconds}} s', { seconds: formatNumber(Number(details.retry_after)) }));
  }
  if (details.role) parts.push(t('admin:security.details.role', 'role: {{role}}', { role: String(details.role) }));
  return parts.join(' · ');
}

function UnlockForm({ token, showSuccess, showError, usernameRef, initial = null }) {
  const [username, setUsername] = useState((initial && initial.username) || '');
  const [ip, setIp] = useState((initial && initial.ip) || '');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const u = username.trim();
    const a = ip.trim();
    setResult(null);
    if (!u && !a) {
      setError(t('admin:security.unlock.needOne', 'Enter a username, an IP address, or both.'));
      return;
    }
    setError('');
    setBusy(true);
    try {
      const r = await api.unlockLogin(token, { username: u, ip: a });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(serverError(d.error, t('admin:security.unlock.failed', 'Unlock failed')));
        return;
      }
      const n = Number(d.keys_cleared) || 0;
      const text = n > 0
        ? t('admin:security.unlock.cleared', { one: 'Cleared {{count}} lock or failure counter.', other: 'Cleared {{count}} locks and failure counters.' }, { count: n })
        : t('admin:security.unlock.nothing', 'Nothing was locked for that username or address.');
      setResult({ ok: n > 0, text });
      showSuccess(t('admin:security.unlock.done', 'Unlock applied.'));
    } catch (err) {
      setError(t('admin:security.unlock.failed', 'Unlock failed'));
      showError(t('admin:security.unlock.failed', 'Unlock failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={t('admin:security.unlock.title', 'Unlock sign-in')} icon="key" className="sr-admin__panel">
      <p className="sr-admin__muted">
        {t('admin:security.unlock.lead', 'After too many failed sign-ins the account and the address are locked for a while. Unlocking clears the failure counters and locks right away. It does not change the password and does not unban a banned user.')}
      </p>
      <form className="sr-admin__form" onSubmit={submit} noValidate data-testid="unlock-form">
        <div className="sr-admin__grid2">
          <Input
            ref={usernameRef}
            name="unlock_username"
            label={t('admin:security.unlock.username', 'Username')}
            autoComplete="off"
            maxLength={150}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <Input
            name="unlock_ip"
            label={t('admin:security.unlock.ip', 'IP address')}
            hint={t('admin:security.unlock.ipHint', 'One exact address, e.g. 203.0.113.7 or 2001:db8::1.')}
            autoComplete="off"
            inputMode="text"
            maxLength={64}
            value={ip}
            onChange={(e) => setIp(e.target.value)}
          />
        </div>
        {error ? <p className="sr-admin__error" role="alert">{error}</p> : null}
        {result ? (
          <p className={result.ok ? 'sr-admin__ok' : 'sr-admin__muted'} role="status" data-testid="unlock-result">{result.text}</p>
        ) : null}
        <div>
          <Button type="submit" variant="primary" icon="key" loading={busy}>
            {t('admin:security.unlock.submit', 'Unlock')}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

const EMPTY_FILTERS = { username: '', event: '', ip: '' };

function LoginAudit({ token, displayTimezone, onUnlockPrefill }) {
  const [draft, setDraft] = useState(EMPTY_FILTERS);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [limit, setLimit] = useState(PAGE_SIZES[1]);
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const r = await api.getAuthEvents(token, { ...filters, limit, offset });
      const d = await r.json().catch(() => null);
      if (!r.ok || !d || !Array.isArray(d.events)) {
        setRows([]);
        setHasMore(false);
        setError(serverError(d && d.error, t('admin:security.audit.loadFailed', 'Could not load the login audit')));
        return;
      }
      setRows(d.events);
      setHasMore(!!d.has_more);
    } catch (e) {
      setRows([]);
      setHasMore(false);
      setError(t('admin:security.audit.loadFailed', 'Could not load the login audit'));
    } finally {
      setLoading(false);
    }
  }, [token, filters, limit, offset]);

  useEffect(() => {
    load();
  }, [load]);

  const apply = (e) => {
    e.preventDefault();
    setOffset(0);
    setFilters({ username: draft.username.trim(), event: draft.event, ip: draft.ip.trim() });
  };
  const reset = () => {
    setDraft(EMPTY_FILTERS);
    setOffset(0);
    setFilters(EMPTY_FILTERS);
  };
  const labels = eventLabels();
  const from = rows.length ? offset + 1 : 0;
  const to = offset + rows.length;

  return (
    <Panel
      title={t('admin:security.audit.title', 'Login audit')}
      icon="eye"
      className="sr-admin__panel"
      actions={
        <Button size="sm" variant="ghost" icon="reroll" onClick={load} disabled={loading}>
          {t('admin:common.refresh', 'Refresh')}
        </Button>
      }
    >
      <p className="sr-admin__muted">
        {t('admin:security.audit.lead', 'Sign-ins, failures, lockouts, sign-outs and password changes, newest first. Rows are kept for 180 days. Passwords and tokens are never logged.')}
      </p>
      <form className="sr-admin__row sr-admin__row--top" onSubmit={apply} role="search" aria-label={t('admin:security.audit.filters', 'Filter the login audit')}>
        <Input
          name="audit_username"
          label={t('admin:security.audit.username', 'Username')}
          hint={t('admin:security.audit.usernameHint', 'Exact name, any case.')}
          fieldClassName="sr-admin__grow"
          autoComplete="off"
          value={draft.username}
          onChange={(e) => setDraft((f) => ({ ...f, username: e.target.value }))}
        />
        <Select
          name="audit_event"
          label={t('admin:security.audit.event', 'Event')}
          fieldClassName="sr-admin__grow"
          value={draft.event}
          onChange={(e) => setDraft((f) => ({ ...f, event: e.target.value }))}
        >
          <option value="">{t('admin:security.audit.allEvents', 'All events')}</option>
          {AUTH_EVENT_TYPES.map((id) => (
            <option key={id} value={id}>{labels[id]}</option>
          ))}
        </Select>
        <Input
          name="audit_ip"
          label={t('admin:security.audit.ip', 'IP address')}
          fieldClassName="sr-admin__grow"
          autoComplete="off"
          value={draft.ip}
          onChange={(e) => setDraft((f) => ({ ...f, ip: e.target.value }))}
        />
        <Select
          name="audit_limit"
          label={t('admin:security.audit.pageSize', 'Rows per page')}
          fieldClassName="sr-admin__select"
          value={String(limit)}
          onChange={(e) => {
            setOffset(0);
            setLimit(Number(e.target.value));
          }}
        >
          {PAGE_SIZES.map((n) => (
            <option key={n} value={n}>{formatNumber(n)}</option>
          ))}
        </Select>
        <div className="sr-admin__row sr-admin__btn-offset">
          <Button type="submit" size="sm" variant="primary" icon="search">{t('admin:common.apply', 'Apply')}</Button>
          <Button size="sm" variant="ghost" onClick={reset}>{t('admin:security.audit.reset', 'Clear filters')}</Button>
        </div>
      </form>

      {error ? <p className="sr-admin__error" role="alert">{error}</p> : null}

      {!error && !loading && rows.length === 0 ? (
        <EmptyState glyph="scroll" title={t('admin:security.audit.empty', 'No events match these filters.')} />
      ) : null}

      {rows.length > 0 ? (
        <div className="sr-admin__tablewrap">
          <table className="sr-admin__table" aria-busy={loading || undefined}>
            <caption className="sr-visually-hidden">{t('admin:security.audit.title', 'Login audit')}</caption>
            <thead>
              <tr>
                <th scope="col">{t('admin:security.audit.col.when', 'When')}</th>
                <th scope="col">{t('admin:security.audit.col.event', 'Event')}</th>
                <th scope="col">{t('admin:security.audit.col.user', 'User')}</th>
                <th scope="col">{t('admin:security.audit.col.ip', 'IP address')}</th>
                <th scope="col">{t('admin:security.audit.col.device', 'Browser / device')}</th>
                <th scope="col">{t('admin:security.audit.col.details', 'Details')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((ev) => (
                <tr key={ev.id} data-testid="auth-event-row">
                  <td className="is-small">
                    <time dateTime={ev.created_at || undefined}>{formatWhen(ev.created_at, displayTimezone)}</time>
                  </td>
                  <td>
                    <Badge tone={EVENT_TONES[ev.event] || 'neutral'}>{labels[ev.event] || ev.event}</Badge>
                  </td>
                  <td className="is-name">
                    {ev.username || '—'}
                    {ev.user_id != null ? <span className="sr-admin__muted"> #{ev.user_id}</span> : null}
                  </td>
                  <td><span className="sr-admin__code">{ev.ip || '—'}</span></td>
                  <td className="is-note" title={ev.user_agent || undefined}>
                    {ev.user_agent ? (ev.user_agent.length > 80 ? `${ev.user_agent.slice(0, 80)}…` : ev.user_agent) : '—'}
                  </td>
                  <td className="is-small">
                    {describeDetails(ev.details)}
                    {(ev.event === 'lockout' || ev.event === 'login_blocked') && (ev.username || ev.ip) ? (
                      <div>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon="key"
                          onClick={() => onUnlockPrefill({ username: ev.username || '', ip: ev.ip || '' })}
                        >
                          {t('admin:security.audit.unlockThis', 'Unlock…')}
                        </Button>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="sr-admin__row" role="navigation" aria-label={t('admin:security.audit.pages', 'Login audit pages')}>
        <Button size="sm" icon="chevron-left" disabled={loading || offset === 0} onClick={() => setOffset((o) => Math.max(0, o - limit))}>
          {t('admin:security.audit.prev', 'Newer')}
        </Button>
        <span className="sr-admin__muted" aria-live="polite">
          {loading
            ? t('admin:loading', 'Loading…')
            : t('admin:security.audit.range', 'Rows {{from}}–{{to}}', { from: formatNumber(from), to: formatNumber(to) })}
        </span>
        <Button size="sm" iconEnd="chevron-right" disabled={loading || !hasMore} onClick={() => setOffset((o) => o + limit)}>
          {t('admin:security.audit.next', 'Older')}
        </Button>
      </div>
    </Panel>
  );
}

/** Admin › Logins & lockouts: unlock form + login audit (docs/SECURITY_MODEL.md). */
export default function SecurityPanel({ token, displayTimezone = null, showSuccess, showError }) {
  const [prefill, setPrefill] = useState(null);
  const usernameRef = useRef(null);

  useEffect(() => {
    if (prefill && usernameRef.current) usernameRef.current.focus();
  }, [prefill]);

  return (
    <div className="sr-admin__section" data-testid="security-panel">
      <h2 className="sr-admin__title">{t('admin:nav.security', 'Logins & lockouts')}</h2>
      <p className="sr-admin__lead">
        {t('admin:security.lead', 'Failed sign-ins lock an account and an address for a short time. Unlock someone who is locked out below, and check the login audit when something looks wrong.')}
      </p>
      <UnlockForm
        key={prefill ? prefill.n : 0}
        token={token}
        showSuccess={showSuccess}
        showError={showError}
        usernameRef={usernameRef}
        initial={prefill}
      />
      <LoginAudit
        token={token}
        displayTimezone={displayTimezone}
        onUnlockPrefill={(p) => setPrefill((old) => ({ ...p, n: (old ? old.n : 0) + 1 }))}
      />
    </div>
  );
}

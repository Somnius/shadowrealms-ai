import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Avatar, Badge, Button, Card, EmptyState, Glyph, Input, Panel, Select, Tabs, Textarea, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi, useAuth } from '../../app/AuthContext';
import { useSheet } from '../../app/SheetContext';
import { errorText } from '../../app/http';
import { getTimezoneSelectOptions } from '../../utils/timezones';
import { formatDateTimeInZone } from '../../utils/userTimeFormat';
import { t } from '../../i18n';
import PasswordRules, { passwordProblem } from '../auth/PasswordRules';
import './profile.css';

const MAX_IMAGE = 360000;

/** Account role in the interface language. */
export function roleLabel(role) {
  if (role === 'admin') return t('profile:role.admin', 'Admin');
  if (role === 'helper') return t('profile:role.helper', 'Helper');
  if (role === 'player') return t('profile:role.player', 'Player');
  return role || '';
}

function downtimeStatusLabel(status) {
  if (status === 'approved') return t('profile:downtime.status.approved', 'Approved');
  if (status === 'rejected') return t('profile:downtime.status.rejected', 'Rejected');
  if (status === 'pending') return t('profile:downtime.status.pending', 'Pending');
  return status || '';
}

export const ownCharacters = (list, user) => (list || []).filter((c) => user && String(c.user_id) === String(user.id));

function readImage(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(file);
  });
}

function ImagePicker({ label, onPick, toast }) {
  const ref = useRef(null);
  return (
    <>
      <Button size="sm" variant="ghost" icon="quill" onClick={() => ref.current && ref.current.click()}>
        {label}
      </Button>
      <input
        ref={ref}
        type="file"
        accept="image/*"
        className="sr-visually-hidden"
        tabIndex={-1}
        aria-hidden="true"
        onChange={async (e) => {
          const f = e.target.files && e.target.files[0];
          e.target.value = '';
          if (!f) return;
          if (f.size > MAX_IMAGE) {
            toast({ tone: 'danger', title: t('profile:imageTooBig', 'Image is too large (max ~350 KB).') });
            return;
          }
          const url = await readImage(f);
          if (typeof url === 'string') onPick(url);
        }}
      />
    </>
  );
}

/** Change password: the server ends every other session and keeps this one signed in. */
function ChangePasswordPanel() {
  const { user, changePassword } = useAuth();
  const { toast } = useToast();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!current) errs.current = t('auth:pw.currentRequired', 'Enter your current password.');
    const problem = passwordProblem(next, { username: user?.username, email: user?.email });
    if (problem) errs.next = problem;
    else if (next === current) errs.next = t('auth:pw.unchanged', 'The new password must differ from the current one.');
    if (!errs.next && again !== next) errs.again = t('auth:pw.mismatch', 'The two new passwords do not match.');
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    const r = await changePassword(current, next);
    setBusy(false);
    if (!r.ok) {
      if (r.code === 'INVALID_CREDENTIALS') setErrors({ current: r.error });
      else if (r.code && String(r.code).startsWith('PASSWORD_')) setErrors({ next: r.error });
      else toast({ tone: 'danger', title: r.error });
      return;
    }
    setCurrent('');
    setNext('');
    setAgain('');
    setErrors({});
    toast({
      tone: 'ok',
      title: t('profile:password.changed', 'Password changed.'),
      body: t('profile:password.changedBody', 'You stay signed in here; every other device has been signed out.'),
    });
  };

  return (
    <Panel title={t('profile:password.title', 'Change password')} icon="key">
      <form className="sr-form" onSubmit={submit} noValidate>
        <p className="sr-muted">
          {t('profile:password.body', 'After the change you stay signed in on this device; every other device and browser is signed out and needs the new password.')}
        </p>
        {/* Lets password managers tie the new password to this account. */}
        <input type="text" name="username" autoComplete="username" value={user?.username || ''} readOnly hidden />
        <Input
          type="password"
          name="current_password"
          label={t('profile:password.current', 'Current password')}
          autoComplete="current-password"
          required
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          error={errors.current}
        />
        <Input
          type="password"
          name="new_password"
          label={t('profile:password.new', 'New password')}
          autoComplete="new-password"
          required
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={errors.next}
          hint={<PasswordRules password={next} username={user?.username} email={user?.email} />}
        />
        <Input
          type="password"
          name="new_password_again"
          label={t('profile:password.again', 'New password again')}
          autoComplete="new-password"
          required
          value={again}
          onChange={(e) => setAgain(e.target.value)}
          error={errors.again}
        />
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={busy} loadingLabel={t('profile:password.busy', 'Changing password')}>
            {t('profile:password.submit', 'Change password')}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

/** Sign out everywhere (POST /auth/logout-all). */
function SessionsPanel() {
  const { logout } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  return (
    <Panel title={t('profile:sessions.title', 'Sessions')} icon="lock-chain">
      <p className="sr-muted">
        {t('profile:sessions.body', 'Lost a device or signed in on a shared computer? Sign out everywhere ends every session of your account, this one included.')}
      </p>
      <div className="sr-form__actions">
        <Button
          variant="danger"
          icon="logout"
          loading={busy}
          onClick={async () => {
            setBusy(true);
            const r = await logout({ everywhere: true });
            setBusy(false);
            if (r && r.ok === false) {
              toast({ tone: 'danger', title: t('shell:menu.logoutAllFailed', 'Could not sign out the other devices. Try again in a moment.') });
              return;
            }
            navigate('/login');
          }}
        >
          {t('shell:menu.logoutAll', 'Sign out everywhere')}
        </Button>
      </div>
    </Panel>
  );
}

function AccountSection() {
  const api = useApi();
  const { user, setUser } = useAuth();
  const { toast } = useToast();
  const [tz, setTz] = useState(user?.display_timezone || '');
  const [saving, setSaving] = useState(false);
  useEffect(() => setTz(user?.display_timezone || ''), [user?.display_timezone]);

  const saveMe = async (body, okText) => {
    setSaving(true);
    const r = await api('/users/me', { method: 'PUT', body });
    setSaving(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('profile:saveFailed', 'Could not save')) });
      return;
    }
    setUser(r.data);
    toast({ tone: 'ok', title: okText });
  };

  return (
    <div className="sr-stack">
      <Panel title={t('profile:account.title', 'Account')} icon="user">
        <dl className="sr-kv">
          <dt>{t('auth:username', 'Username')}</dt>
          <dd>{user?.username}</dd>
          <dt>{t('auth:email', 'Email')}</dt>
          <dd>{user?.email}</dd>
          <dt>{t('profile:account.role', 'Role')}</dt>
          <dd>
            <Badge tone={user?.role === 'admin' ? 'gold' : 'neutral'}>{roleLabel(user?.role)}</Badge>
          </dd>
        </dl>
      </Panel>
      <Panel title={t('profile:tz.title', 'Time zone')} icon="hourglass">
        <form
          className="sr-form"
          onSubmit={(e) => {
            e.preventDefault();
            saveMe({ display_timezone: tz.trim() ? tz.trim() : null }, t('profile:tz.saved', 'Display time zone saved.'));
          }}
        >
          <Select
            label={t('profile:tz.label', 'Display time zone')}
            hint={t('profile:tz.hint', 'Message times, dice history and admin timestamps use this zone.')}
            value={tz}
            onChange={(e) => setTz(e.target.value)}
          >
            <option value="">{t('profile:tz.browser', 'Browser default (device time)')}</option>
            {getTimezoneSelectOptions().map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          <div className="sr-form__actions">
            <Button type="submit" variant="primary" loading={saving}>
              {t('common:save', 'Save')}
            </Button>
          </div>
        </form>
      </Panel>
      <Panel title={t('profile:ooc.title', 'Out-of-character portrait')} icon="hood">
        <div className="sr-row">
          <Avatar src={user?.player_avatar_url} name={user?.username} size={64} alt="" sigil="hood" />
          <p className="sr-muted sr-grow">
            {t('profile:ooc.body', 'Shown when you speak as yourself (out of character). In story rooms others see your character’s portrait.')}
          </p>
          <ImagePicker
            label={t('profile:ooc.change', 'Change portrait')}
            toast={toast}
            onPick={(url) => saveMe({ player_avatar_url: url }, t('profile:ooc.saved', 'Portrait saved.'))}
          />
        </div>
      </Panel>
      <ChangePasswordPanel />
      <SessionsPanel />
    </div>
  );
}

function CharactersSection() {
  const api = useApi();
  const { toast } = useToast();
  const { openSheet } = useSheet();
  const { user } = useAuth();
  const [chars, setChars] = useState(null);
  const load = useCallback(async () => {
    const r = await api('/characters/');
    // Admins get every character from this endpoint; the profile lists your own.
    setChars(r.ok && Array.isArray(r.data.characters) ? ownCharacters(r.data.characters, user) : []);
  }, [api, user]);
  useEffect(() => {
    load();
  }, [load]);

  const setPortrait = async (ch, url) => {
    const r = await api(`/characters/${ch.id}`, { method: 'PUT', body: { portrait_url: url } });
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('play:panel.portraitFailed', 'Could not save the portrait.')) });
      return;
    }
    toast({ tone: 'ok', title: t('play:panel.portraitSaved', 'Portrait updated.') });
    load();
  };

  return (
    <div className="sr-stack">
      <div className="sr-row sr-row--between">
        <p className="sr-muted sr-grow">
          {t('profile:characters.body', 'Inside a chronicle you always play that chronicle’s character. Sheets lock after creation; ask for changes through downtime.')}
        </p>
        <ButtonLink to="/profile/characters/new" variant="primary" icon="plus">
          {t('profile:characters.new', 'New character')}
        </ButtonLink>
      </div>
      {chars && chars.length === 0 ? (
        <EmptyState glyph="mask" title={t('profile:characters.empty', 'No characters yet')}>
          {t('profile:characters.emptyBody', 'Join or create a chronicle, then forge a character for it.')}
        </EmptyState>
      ) : null}
      <ul className="sr-chars">
        {(chars || []).map((ch) => (
          <li key={ch.id}>
            <Card className="sr-char">
              <div className="sr-row">
                <Avatar src={ch.portrait_url} name={ch.name} size={56} alt="" sigil="mask" />
                <div className="sr-char__text">
                  <strong className="sr-char__name">{ch.name}</strong>
                  <Link to={`/c/${ch.campaign_id}`} className="sr-small">
                    {ch.campaign_name}
                  </Link>
                </div>
              </div>
              {ch.play_suspended ? (
                <p className="sr-error sr-small">
                  <Glyph name="lock-chain" size={14} />
                  {t('profile:characters.suspended', 'Unavailable for play')}
                  {ch.play_suspension_message ? `: ${ch.play_suspension_message}` : ''}
                </p>
              ) : null}
              <div className="sr-row">
                <Button size="sm" variant="secondary" icon="scroll" onClick={() => openSheet(ch.id, ch.system_type)}>
                  {t('play:panel.sheet', 'Character sheet')}
                </Button>
                <ImagePicker label={t('play:panel.portrait', 'Portrait')} toast={toast} onPick={(url) => setPortrait(ch, url)} />
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DowntimeSection() {
  const api = useApi();
  const { user } = useAuth();
  const { toast } = useToast();
  const [chars, setChars] = useState([]);
  const [mine, setMine] = useState([]);
  const [charId, setCharId] = useState('');
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    const [c, d] = await Promise.all([api('/characters/'), api('/characters/downtime-requests/mine')]);
    const list = c.ok && Array.isArray(c.data.characters) ? ownCharacters(c.data.characters, user) : [];
    setChars(list);
    setCharId((cur) => cur || (list[0] ? String(list[0].id) : ''));
    setMine(d.ok && Array.isArray(d.data.requests) ? d.data.requests : []);
  }, [api, user]);
  useEffect(() => {
    load();
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    if (!charId || !text.trim()) return;
    setBusy(true);
    const r = await api(`/characters/${charId}/downtime-requests`, { method: 'POST', body: { request_text: text.trim() } });
    setBusy(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('profile:downtime.failed', 'Could not submit the request')) });
      return;
    }
    setText('');
    toast({ tone: 'ok', title: t('profile:downtime.sent', 'Request sent to the Storyteller and staff.') });
    load();
  };

  return (
    <div className="sr-stack">
      <Panel title={t('profile:downtime.new', 'New downtime request')} icon="hourglass">
        <p className="sr-muted">{t('profile:downtime.body', 'Sheets are locked after creation. Ask the Storyteller or staff to change stats, merits or story flags; they approve or reject with a reason.')}</p>
        {chars.length ? (
          <form className="sr-form" onSubmit={submit}>
            <Select
              label={t('profile:downtime.character', 'Character')}
              value={charId}
              onChange={(e) => setCharId(e.target.value)}
              options={chars.map((c) => ({ value: String(c.id), label: `${c.name} · ${c.campaign_name || ''}` }))}
            />
            <Textarea label={t('profile:downtime.what', 'What should change?')} rows={4} value={text} onChange={(e) => setText(e.target.value)} />
            <div className="sr-form__actions">
              <Button type="submit" variant="primary" loading={busy} disabled={!text.trim()}>
                {t('profile:downtime.submit', 'Submit request')}
              </Button>
            </div>
          </form>
        ) : (
          <p className="sr-muted">{t('profile:downtime.noChars', 'You need a character first.')}</p>
        )}
      </Panel>
      <Panel title={t('profile:downtime.mine', 'Your requests')} icon="scroll">
        {mine.length === 0 ? (
          <p className="sr-muted">{t('profile:downtime.none', 'None yet.')}</p>
        ) : (
          <ul className="sr-downtime">
            {mine.map((r) => (
              <li key={r.id}>
                <div className="sr-row">
                  <Badge tone={r.status === 'approved' ? 'ok' : r.status === 'rejected' ? 'danger' : 'warn'}>{downtimeStatusLabel(r.status)}</Badge>
                  <strong>{r.character_name}</strong>
                  <span className="sr-muted sr-small">{r.campaign_name}</span>
                  {r.created_at ? <span className="sr-muted sr-small">{formatDateTimeInZone(r.created_at, user?.display_timezone || null)}</span> : null}
                </div>
                <p className="sr-downtime__text">{r.request_text}</p>
                {r.admin_reason ? <p className="sr-small sr-downtime__reply">{t('profile:downtime.staff', 'Staff: {{reason}}', { reason: r.admin_reason })}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

const SECTIONS = ['account', 'characters', 'downtime'];

export default function ProfilePage() {
  const { section } = useParams();
  const navigate = useNavigate();
  const current = SECTIONS.includes(section) ? section : 'characters';
  return (
    <>
      <TopBar title={t('profile:title', 'Profile & characters')} icon="user" />
      <PageBody narrow>
        <Tabs
          label={t('profile:sections', 'Profile sections')}
          value={current}
          onChange={(id) => navigate(`/profile/${id}`, { replace: true })}
          tabs={[
            { id: 'characters', label: t('profile:tab.characters', 'Characters'), icon: 'mask', content: <CharactersSection /> },
            { id: 'account', label: t('profile:tab.account', 'Account'), icon: 'user', content: <AccountSection /> },
            { id: 'downtime', label: t('profile:tab.downtime', 'Downtime'), icon: 'hourglass', content: <DowntimeSection /> },
          ]}
        />
      </PageBody>
    </>
  );
}

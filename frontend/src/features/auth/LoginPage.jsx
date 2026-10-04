import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, CandleGlow, FogLayer, Glyph, Grain, Input, SigilReveal, Tabs, Vignette, useToast } from '../../design';
import { useAuth } from '../../app/AuthContext';
import { afterLoginPath } from '../../app/guards';
import Footer from '../../components/Footer';
import PasswordRules, { brokenRule, passwordProblem } from './PasswordRules';
import LanguageSwitch from '../../app/LanguageSwitch';
import { t } from '../../i18n';
import './auth.css';

const SESSION_NOTICE = {
  expired: () => t('auth:session.expired', 'Your session has expired. Sign in again to continue where you were.'),
  revoked: () => t('auth:session.revoked', 'You were signed out, for example because the password changed or someone chose “Sign out everywhere”. Sign in again.'),
  invalid: () => t('auth:session.invalid', 'Your sign-in is no longer valid. Sign in again.'),
  elsewhere: () => t('auth:session.elsewhere', 'You signed out in another tab.'),
  signedOutAll: () => t('auth:session.signedOutAll', 'You were signed out on all devices.'),
};

function LoginForm({ onDone }) {
  const { login, sessionNotice } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError('');
    const r = await login(String(fd.get('username') || '').trim(), String(fd.get('password') || ''));
    setBusy(false);
    if (r.ok) onDone();
    else setError(r.error);
  };
  return (
    <form onSubmit={submit} className="sr-auth__form" noValidate={false}>
      {sessionNotice && SESSION_NOTICE[sessionNotice] ? (
        <p className="sr-auth__notice" role="status">
          <Glyph name="hourglass" size={16} /> {SESSION_NOTICE[sessionNotice]()}
        </p>
      ) : null}
      <Input name="username" label={t('auth:username', 'Username')} autoComplete="username" required autoFocus />
      <Input name="password" type="password" label={t('auth:password', 'Password')} autoComplete="current-password" required />
      {error ? (
        <p className="sr-auth__error" role="alert">
          <Glyph name="warning" size={16} /> {error}
        </p>
      ) : null}
      <Button type="submit" variant="primary" size="lg" block loading={busy} loadingLabel={t('auth:login.busy', 'Signing in')}>
        {t('auth:login.submit', 'Enter')}
      </Button>
    </form>
  );
}

function RegisterForm({ onDone }) {
  const { register } = useAuth();
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pwError, setPwError] = useState('');
  const [pw, setPw] = useState('');
  const [names, setNames] = useState({ username: '', email: '' });
  const [pwRule, setPwRule] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const local = passwordProblem(String(fd.get('password') || ''), {
      username: String(fd.get('username') || ''),
      email: String(fd.get('email') || ''),
    });
    setError('');
    if (local) {
      setPwError(local);
      setPwRule(brokenRule(String(fd.get('password') || ''), { username: String(fd.get('username') || ''), email: String(fd.get('email') || '') }));
      return;
    }
    setPwError('');
    setPwRule(null);
    setBusy(true);
    const r = await register({
      username: String(fd.get('username') || '').trim(),
      email: String(fd.get('email') || '').trim(),
      password: String(fd.get('password') || ''),
      invite_code: String(fd.get('invite_code') || '').trim(),
    });
    setBusy(false);
    if (r.ok) {
      toast({ tone: 'ok', title: t('auth:register.done', 'Account created. Welcome to the shadows.') });
      onDone();
    } else if (r.code && String(r.code).startsWith('PASSWORD_')) {
      setPwError(r.error);
      setPwRule(brokenRule('', null, r.code));
    } else setError(r.error);
  };
  const onNames = (e) => {
    const { name, value } = e.target;
    if (name === 'username' || name === 'email') setNames((n) => ({ ...n, [name]: value }));
  };
  return (
    <form onSubmit={submit} className="sr-auth__form" onChange={onNames}>
      <Input name="username" label={t('auth:username', 'Username')} autoComplete="username" required />
      <Input name="email" type="email" label={t('auth:email', 'Email')} autoComplete="email" required />
      <Input
        name="password"
        type="password"
        label={t('auth:password', 'Password')}
        autoComplete="new-password"
        required
        value={pw}
        onChange={(e) => {
          setPw(e.target.value);
          if (pwError) setPwError('');
          if (pwRule) setPwRule(null);
        }}
        error={pwError || undefined}
        hint={<PasswordRules password={pw} username={names.username} email={names.email} broken={pwRule} />}
      />
      <Input
        name="invite_code"
        label={t('auth:invite', 'Invite code')}
        hint={t('auth:inviteHint', 'Registration is invite-only. Ask an admin for a code.')}
        autoComplete="off"
        required
      />
      {error ? (
        <p className="sr-auth__error" role="alert">
          <Glyph name="warning" size={16} /> {error}
        </p>
      ) : null}
      <Button type="submit" variant="arcane" size="lg" block loading={busy} loadingLabel={t('auth:register.busy', 'Creating account')}>
        {t('auth:register.submit', 'Create account')}
      </Button>
    </form>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const onDone = () => navigate(afterLoginPath(location.state), { replace: true });
  return (
    <div className="sr-authpage">
    <main className="sr-auth" id="main">
      <div className="sr-auth__atmos" aria-hidden="true">
        <FogLayer intensity={0.13} speed={0.8} className="sr-auth__fog" />
        <FogLayer intensity={0.1} tint="blood" speed={0.55} className="sr-auth__fog sr-auth__fog--low" />
        <CandleGlow x="50%" y="20%" size={460} />
        <Vignette strength={0.75} />
        <Grain opacity={0.05} />
      </div>
      <div className="sr-auth__inner">
        <div className="sr-auth__hero">
          <SigilReveal size={136} title={null} className="sr-auth__sigil" duration={1.4} />
          <h1 className="sr-auth__wordmark" lang="en">
            <span className="sr-auth__wordmark-main">{t('auth:wordmark', 'ShadowRealms')}</span>
            <span className="sr-auth__wordmark-ai">AI</span>
          </h1>
        </div>
        <p className="sr-auth__tagline sr-prose">
          {t('auth:tagline', 'Step through the veil: chronicles, dice and an AI Storyteller await.')}
        </p>
        <Card ornate className="sr-auth__card">
          <Tabs
            label={t('auth:tabs', 'Sign in or register')}
            tabs={[
              { id: 'login', label: t('auth:tab.login', 'Sign in'), content: <LoginForm onDone={onDone} /> },
              { id: 'register', label: t('auth:tab.register', 'Register'), content: <RegisterForm onDone={onDone} /> },
            ]}
          />
        </Card>
        <div className="sr-auth__links">
          <LanguageSwitch />
          <Link to="/showcase">{t('auth:showcase', 'Theme preview')}</Link>
        </div>
      </div>
    </main>
    <Footer />
    </div>
  );
}

import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, FogLayer, Glyph, Input, Tabs, useToast } from '../../design';
import { useAuth } from '../../app/AuthContext';
import { afterLoginPath } from '../../app/guards';
import Footer from '../../components/Footer';
import LanguageSwitch from '../../app/LanguageSwitch';
import { t } from '../../i18n';
import './auth.css';

function LoginForm({ onDone }) {
  const { login } = useAuth();
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
  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError('');
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
    } else setError(r.error);
  };
  return (
    <form onSubmit={submit} className="sr-auth__form">
      <Input name="username" label={t('auth:username', 'Username')} autoComplete="username" required />
      <Input name="email" type="email" label={t('auth:email', 'Email')} autoComplete="email" required />
      <Input name="password" type="password" label={t('auth:password', 'Password')} autoComplete="new-password" required />
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
      <FogLayer intensity={0.08} className="sr-auth__fog" />
      <div className="sr-auth__inner">
        <h1 className="sr-visually-hidden">{t('auth:title', 'ShadowRealms AI')}</h1>
        <img className="sr-auth__logo" src="/logo-login.png" alt={t('auth:logoAlt', 'ShadowRealms AI')} />
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

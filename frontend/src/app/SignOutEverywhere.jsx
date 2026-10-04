import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Modal, useOptionalToast } from '../design';
import { useAuth } from './AuthContext';
import { t } from '../i18n';

/**
 * "Sign out everywhere" with a confirmation step. useSignOutEverywhere() returns
 * { ask, dialog }: call ask() to open the dialog, render {dialog} once.
 */
export function useSignOutEverywhere() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const toasts = useOptionalToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    const r = await logout({ everywhere: true });
    setBusy(false);
    if (r && r.ok === false) {
      if (toasts) toasts.toast({ tone: 'danger', title: t('shell:menu.logoutAllFailed', 'Could not sign out the other devices. Try again in a moment.') });
      return;
    }
    setOpen(false);
    navigate('/login');
  };

  const dialog = (
    <Modal
      open={open}
      onClose={busy ? undefined : () => setOpen(false)}
      title={t('shell:logoutAll.title', 'Sign out everywhere?')}
      icon="logout"
      size="sm"
    >
      <p className="sr-muted">
        {t('shell:logoutAll.body', 'This ends every session of your account, on every device and browser, this one included. You will need your password to sign in again.')}
      </p>
      <div className="sr-form__actions">
        <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
          {t('common:cancel', 'Cancel')}
        </Button>
        <Button variant="danger" icon="logout" loading={busy} onClick={confirm}>
          {t('shell:menu.logoutAll', 'Sign out everywhere')}
        </Button>
      </div>
    </Modal>
  );

  return { ask: () => setOpen(true), dialog };
}

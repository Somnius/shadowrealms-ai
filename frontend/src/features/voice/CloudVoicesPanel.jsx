/**
 * Admin → AI system → Cloud voices (Gemini): off / free tier / paid tier and the model
 * (GET/PUT /api/voice/cloud-settings, site admins only). Keys stay in the environment; only
 * whether each is set is shown.
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Panel, Select, useToast } from '../../design';
import { apiFetch, errorText, getCurrentToken } from '../../app/http';
import { t } from '../../i18n';

const yesNo = (v) => (v == null ? '—' : v ? t('voice:yes', 'Yes') : t('voice:no', 'No'));

export default function CloudVoicesPanel() {
  const { toast } = useToast();
  const [s, setS] = useState(null);
  const [tier, setTier] = useState('off');
  const [model, setModel] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const take = (d) => {
    setS(d);
    setTier(d.tier);
    setModel(d.model);
  };
  const load = useCallback(() => {
    apiFetch(getCurrentToken(), '/voice/cloud-settings').then((r) => {
      if (r.ok && r.data && r.data.tier) { take(r.data); setFailed(false); } else setFailed(true);
    });
  }, []);
  useEffect(() => { load(); }, [load]);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await apiFetch(getCurrentToken(), '/voice/cloud-settings', { method: 'PUT', body: { tier, model } });
    setBusy(false);
    if (r.ok && r.data && r.data.tier) {
      take(r.data);
      toast({ tone: 'ok', title: t('voice:saved', 'Voice settings saved.') });
    } else toast({ tone: 'danger', title: errorText(r.data, t('voice:saveFailed', 'Could not save the voice settings')) });
  };
  const keys = (s && s.keys) || {};
  const missing = s && tier !== 'off' && s.keys && !s.keys[tier];
  return (
    <Panel title={t('voice:cloud.adminTitle', 'Cloud voices (Gemini)')} className="sr-admin__panel" data-testid="cloud-voices-admin">
      {failed ? <p className="sr-admin__warn">{t('voice:cloud.loadFailed', 'Could not read the cloud voice settings.')}</p> : null}
      {s ? (
        <form className="sr-form" onSubmit={save}>
          <Select
            label={t('voice:cloud.tier', 'Cloud voices')}
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            options={[
              { value: 'off', label: t('voice:cloud.off', 'Off') },
              { value: 'free', label: t('voice:cloud.free', 'Free tier') },
              { value: 'paid', label: t('voice:cloud.paid', 'Paid tier') },
            ]}
          />
          <Select
            label={t('voice:cloud.model', 'Model')}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            options={(s.models || []).map((m) => ({ value: m, label: m }))}
          />
          <div className="sr-admin__kv">
            <div><strong>{t('voice:cloud.keyFree', 'Free key (GEMINI_API_KEY) set:')}</strong> {yesNo(keys.free)}</div>
            <div><strong>{t('voice:cloud.keyPaid', 'Paid key (GEMINI_API_KEY_PAID) set:')}</strong> {yesNo(keys.paid)}</div>
          </div>
          {s.keys == null ? <p className="sr-admin__warn">{t('voice:cloud.noSpeech', 'The speech service is not reachable, so the keys cannot be checked.')}</p> : null}
          {missing ? <p className="sr-admin__warn">{t('voice:cloud.missingKey', 'There is no key for this tier: lines will use the local voices.')}</p> : null}
          <p className="sr-muted sr-small">{t('voice:cloud.freeExplain', 'Free tier: no cost, but Google may use the text sent to it to improve its products.')}</p>
          <p className="sr-muted sr-small">{t('voice:cloud.paidExplain', 'Paid tier: Google does not use the text to improve its products; use is billed to the key’s Google project. Which tier applies depends on that project’s billing, not on this setting.')}</p>
          <p className="sr-muted sr-small">{t('voice:cloud.optIn', 'Each chronicle must also turn on “Use cloud voices” in Chronicle settings → Voice. If Gemini fails, times out or is rate-limited, that line is spoken by the local voices.')}</p>
          <div className="sr-form__actions">
            <Button type="submit" variant="primary" loading={busy}>{t('common:save', 'Save')}</Button>
          </div>
        </form>
      ) : null}
    </Panel>
  );
}

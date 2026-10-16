/** Voice settings: the player's own (Profile → Voice) and the chronicle's read-out defaults. */
import { useEffect, useState } from 'react';
import { Button, Checkbox, Panel, Select, useToast } from '../../design';
import { useApi } from '../../app/AuthContext';
import { errorText } from '../../app/http';
import { t } from '../../i18n';

export const READOUT_KINDS = ['storyteller', 'ic', 'ooc', 'dice'];

export function readoutLabel(kind) {
  if (kind === 'storyteller') return t('voice:kind.storyteller', 'Storyteller');
  if (kind === 'ic') return t('voice:kind.ic', 'In character');
  if (kind === 'ooc') return t('voice:kind.ooc', 'Out of character');
  if (kind === 'dice') return t('voice:kind.dice', 'Dice results');
  return t('voice:kind.actions', 'Actions');
}

/** Four checkboxes: which messages a chronicle reads out by default. value: {storyteller, ic, ooc, dice}. */
export function ReadoutDefaults({ value, onChange }) {
  return (
    <fieldset className="sr-radio-group" data-testid="voice-defaults">
      <legend>{t('voice:defaults.legend', 'Read aloud by default')}</legend>
      {READOUT_KINDS.map((k) => (
        <Checkbox
          key={k}
          label={readoutLabel(k)}
          checked={value[k] !== false}
          onChange={(e) => onChange({ ...value, [k]: e.target.checked })}
        />
      ))}
      <p className="sr-muted sr-small">{t('voice:defaults.hint', 'Each player can still turn any of these off for themselves in Profile → Voice.')}</p>
    </fieldset>
  );
}

export const DEFAULT_READOUT = { storyteller: true, ic: true, ooc: true, dice: true };

/** Chronicle settings panel: loads and saves /campaigns/<id>/voice-settings. */
export function ChronicleVoicePanel({ campaignId }) {
  const api = useApi();
  const { toast } = useToast();
  const [defaults, setDefaults] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api(`/campaigns/${campaignId}/voice-settings`).then((r) => {
      if (live && r.ok && r.data && r.data.settings) setDefaults(r.data.settings.defaults);
    });
    return () => {
      live = false;
    };
  }, [api, campaignId]);
  if (!defaults) return null;
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await api(`/campaigns/${campaignId}/voice-settings`, { method: 'PUT', body: { defaults } });
    setBusy(false);
    if (!r.ok) toast({ tone: 'danger', title: errorText(r.data, t('voice:saveFailed', 'Could not save the voice settings')) });
    else toast({ tone: 'ok', title: t('voice:saved', 'Voice settings saved.') });
  };
  return (
    <Panel title={t('voice:chronicle.title', 'Voice')} icon="ear">
      <form className="sr-form" onSubmit={save}>
        <ReadoutDefaults value={defaults} onChange={setDefaults} />
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={busy}>{t('common:save', 'Save')}</Button>
        </div>
      </form>
    </Panel>
  );
}

const OVERRIDE_KINDS = [...READOUT_KINDS, 'actions'];
const ovValue = (v) => (v === true ? 'on' : v === false ? 'off' : 'default');
const ovParse = (v) => (v === 'on' ? true : v === 'off' ? false : null);

/** Profile → Voice: /voice/settings. */
export function VoiceSettingsPanel() {
  const api = useApi();
  const { toast } = useToast();
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api('/voice/settings').then((r) => {
      if (live && r.ok) setS(r.data);
    });
    return () => {
      live = false;
    };
  }, [api]);
  if (!s) return null;
  const set = (patch) => setS({ ...s, ...patch });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = { tts_source: s.tts_source, en_accent: s.en_accent, rate: Number(s.rate), volume: Number(s.volume), overrides: s.overrides };
    const r = await api('/voice/settings', { method: 'PUT', body });
    setBusy(false);
    if (!r.ok) toast({ tone: 'danger', title: errorText(r.data, t('voice:saveFailed', 'Could not save the voice settings')) });
    else {
      setS(r.data);
      toast({ tone: 'ok', title: t('voice:saved', 'Voice settings saved.') });
    }
  };
  return (
    <Panel title={t('voice:profile.title', 'Voice')} icon="ear">
      <form className="sr-form" onSubmit={save}>
        <Select
          label={t('voice:source.label', 'Read messages aloud with')}
          hint={t('voice:source.hint', 'Phone voices are your phone’s or browser’s own; nothing leaves your device. Turn on Listen (the ear) in a room.')}
          value={s.tts_source === 'server' ? 'phone' : s.tts_source}
          onChange={(e) => set({ tts_source: e.target.value })}
          options={[
            { value: 'phone', label: t('voice:source.phone', 'Phone voices') },
            { value: 'off', label: t('voice:source.off', 'Off') },
          ]}
        />
        <Select
          label={t('voice:accent.label', 'English accent')}
          value={s.en_accent}
          onChange={(e) => set({ en_accent: e.target.value })}
          options={[
            { value: 'us', label: t('voice:accent.us', 'American') },
            { value: 'gb', label: t('voice:accent.gb', 'British') },
          ]}
        />
        <label className="sr-field">
          <span className="sr-field__label">{t('voice:rate', 'Speed: {{value}}×', { value: Number(s.rate).toFixed(2) })}</span>
          <input type="range" min="0.75" max="2" step="0.25" value={s.rate} onChange={(e) => set({ rate: Number(e.target.value) })} />
        </label>
        <label className="sr-field">
          <span className="sr-field__label">{t('voice:volume', 'Volume: {{value}}%', { value: Math.round(Number(s.volume) * 100) })}</span>
          <input type="range" min="0" max="1" step="0.05" value={s.volume} onChange={(e) => set({ volume: Number(e.target.value) })} />
        </label>
        {OVERRIDE_KINDS.map((k) => (
          <Select
            key={k}
            label={readoutLabel(k)}
            value={ovValue(s.overrides[k])}
            onChange={(e) => set({ overrides: { ...s.overrides, [k]: ovParse(e.target.value) } })}
            options={[
              { value: 'default', label: t('voice:override.default', 'As the chronicle sets it') },
              { value: 'on', label: t('voice:override.on', 'Always read') },
              { value: 'off', label: t('voice:override.off', 'Never read') },
            ]}
          />
        ))}
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={busy}>{t('common:save', 'Save')}</Button>
        </div>
      </form>
    </Panel>
  );
}

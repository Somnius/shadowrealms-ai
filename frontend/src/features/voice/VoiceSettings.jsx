/** Voice settings: the player's own (Profile → Voice) and the chronicle's read-out defaults. */
import { useEffect, useState } from 'react';
import { Button, Checkbox, Panel, Select, useToast } from '../../design';
import { useApi } from '../../app/AuthContext';
import { errorText } from '../../app/http';
import { t } from '../../i18n';
import { previewVoice } from './serverVoice';
import './voice.css';

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

/** The three narrator slots: English with a US accent, English with a British one, Greek. */
export const NARRATOR_SLOTS = [
  { key: 'narrator_voice_en', lang: 'en', accent: 'us' },
  { key: 'narrator_voice_en_gb', lang: 'en', accent: 'gb' },
  { key: 'narrator_voice_el', lang: 'el', accent: 'gr' },
];

export function narratorSlotLabel(slot) {
  if (slot.lang === 'el') return t('voice:narrator.el', 'Greek');
  return slot.accent === 'gb' ? t('voice:narrator.enGb', 'English (British)') : t('voice:narrator.enUs', 'English (American)');
}

const voiceLabel = (v) => {
  const name = String(v.id).replace(/^(en_US|en_GB|el_GR|el)-/, '').replace(/-(medium|high|low)$/, '').replace(/_/g, ' ');
  const gender = v.gender === 'female' ? t('voice:gender.female', 'Female') : v.gender === 'male' ? t('voice:gender.male', 'Male') : '';
  return gender ? `${name} (${gender})` : name;
};

/** The voice catalog from the server: { available, voices }, null while loading. */
export function useVoiceCatalog() {
  const api = useApi();
  const [catalog, setCatalog] = useState(null);
  useEffect(() => {
    let live = true;
    api('/voice/voices').then((r) => {
      if (live) setCatalog(r.ok ? r.data : { available: false, voices: [] });
    });
    return () => {
      live = false;
    };
  }, [api]);
  return catalog;
}

/** Narrator voice per language, with "Hear it". value: {narrator_voice_en, narrator_voice_en_gb, narrator_voice_el}. */
export function NarratorVoices({ value, onChange }) {
  const api = useApi();
  const { toast } = useToast();
  const catalog = useVoiceCatalog();
  const [hearing, setHearing] = useState('');
  if (!catalog) return null;
  if (!catalog.available) {
    return <p className="sr-muted sr-small" data-testid="narrator-off">{t('voice:narrator.off', 'Server voices are not running on this site, so the narrator voice cannot be chosen now. The default is used.')}</p>;
  }
  const hear = async (slot, id) => {
    setHearing(slot.key);
    try {
      await previewVoice(api, id, slot.lang);
    } catch {
      toast({ tone: 'warn', title: t('voice:previewFailed', 'Could not play the sample. Try again in a moment.') });
    }
    setHearing('');
  };
  return (
    <fieldset className="sr-radio-group" data-testid="narrator-voices">
      <legend>{t('voice:narrator.legend', 'Narrator voice (server voices)')}</legend>
      {NARRATOR_SLOTS.map((slot) => {
        const list = catalog.voices.filter((v) => v.lang === slot.lang && (slot.lang === 'el' || v.accent === slot.accent) && v.available !== false);
        const def = list.find((v) => (v.default_for || []).includes('narrator'));
        const current = value[slot.key] || '';
        return (
          <div key={slot.key} className="sr-voice-narrator">
            <Select
              label={narratorSlotLabel(slot)}
              value={current}
              onChange={(e) => onChange({ ...value, [slot.key]: e.target.value || null })}
              options={[
                { value: '', label: def ? t('voice:narrator.default', 'Default: {{name}}', { name: voiceLabel(def) }) : t('voice:narrator.defaultPlain', 'Default') },
                ...list.map((v) => ({ value: v.id, label: voiceLabel(v) })),
              ]}
            />
            <Button
              type="button"
              size="sm"
              variant="secondary"
              loading={hearing === slot.key}
              disabled={!current && !def}
              onClick={() => hear(slot, current || def.id)}
            >
              {t('voice:narrator.hear', 'Hear it')}
            </Button>
          </div>
        );
      })}
      <p className="sr-muted sr-small">{t('voice:narrator.hint', 'Used for the Storyteller, actions and dice results for players who listen with server voices.')}</p>
    </fieldset>
  );
}

export const narratorOf = (settings) => ({
  narrator_voice_en: (settings && settings.narrator_voice_en) || null,
  narrator_voice_en_gb: (settings && settings.narrator_voice_en_gb) || null,
  narrator_voice_el: (settings && settings.narrator_voice_el) || null,
});

/** Chronicle settings panel: loads and saves /campaigns/<id>/voice-settings. */
export function ChronicleVoicePanel({ campaignId }) {
  const api = useApi();
  const { toast } = useToast();
  const [defaults, setDefaults] = useState(null);
  const [narrator, setNarrator] = useState(narratorOf(null));
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    api(`/campaigns/${campaignId}/voice-settings`).then((r) => {
      if (live && r.ok && r.data && r.data.settings) {
        setDefaults(r.data.settings.defaults);
        setNarrator(narratorOf(r.data.settings));
      }
    });
    return () => {
      live = false;
    };
  }, [api, campaignId]);
  if (!defaults) return null;
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const r = await api(`/campaigns/${campaignId}/voice-settings`, { method: 'PUT', body: { defaults, ...narrator } });
    setBusy(false);
    if (!r.ok) toast({ tone: 'danger', title: errorText(r.data, t('voice:saveFailed', 'Could not save the voice settings')) });
    else toast({ tone: 'ok', title: t('voice:saved', 'Voice settings saved.') });
  };
  return (
    <Panel title={t('voice:chronicle.title', 'Voice')} icon="ear">
      <form className="sr-form" onSubmit={save}>
        <ReadoutDefaults value={defaults} onChange={setDefaults} />
        <NarratorVoices value={narrator} onChange={setNarrator} />
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
          hint={t('voice:source.hint2', 'Phone voices are your phone’s or browser’s own; nothing leaves your device. Server voices are made on this site’s server: one voice per character by gender, the chronicle’s narrator for the Storyteller. Turn on Listen (the ear) in a room.')}
          value={s.tts_source}
          onChange={(e) => set({ tts_source: e.target.value })}
          options={[
            { value: 'phone', label: t('voice:source.phone', 'Phone voices') },
            { value: 'server', label: t('voice:source.server', 'Server voices') },
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

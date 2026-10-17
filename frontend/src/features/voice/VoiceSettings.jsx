/** Voice settings: the player's own (Profile → Voice) and the chronicle's read-out defaults. */
import { useEffect, useState } from 'react';
import { Button, Checkbox, Modal, Panel, Select, useToast } from '../../design';
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
  if (v.engine === 'gemini') {
    const name = String(v.id).replace(/^gemini-/, '');
    return t('voice:cloud.voiceLabel', '{{name}} · {{style}} (Gemini)', { name, style: v.style || '' });
  }
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

/** Narrator voice per language, with "Hear it". value: {narrator_voice_en, narrator_voice_en_gb, narrator_voice_el}.
 * cloud: the chronicle uses cloud voices, so the Gemini voices (any language) are listed too. */
export function NarratorVoices({ value, onChange, cloud = false }) {
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
        const local = catalog.voices.filter((v) => v.lang === slot.lang && (slot.lang === 'el' || v.accent === slot.accent) && v.available !== false);
        const list = cloud ? [...local, ...(catalog.cloud_voices || [])] : local;
        const def = local.find((v) => (v.default_for || []).includes('narrator'));
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
  const [speaking, setSpeaking] = useState({ max_clip_seconds: 180, allow_phone_stt: true });
  const [busy, setBusy] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [cloudAvailable, setCloudAvailable] = useState(false);
  const [cloud, setCloud] = useState(false);
  useEffect(() => {
    let live = true;
    api(`/campaigns/${campaignId}/voice-settings`).then((r) => {
      if (live && r.ok && r.data && r.data.settings) {
        setCanEdit(!!r.data.can_edit);
        setDefaults(r.data.settings.defaults);
        setNarrator(narratorOf(r.data.settings));
        setCloudAvailable(!!r.data.cloud_available);
        setCloud(!!r.data.settings.cloud_voices);
        setSpeaking({
          max_clip_seconds: r.data.settings.max_clip_seconds || 180,
          allow_phone_stt: r.data.settings.allow_phone_stt !== false,
        });
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
    const r = await api(`/campaigns/${campaignId}/voice-settings`, { method: 'PUT', body: { defaults, ...narrator, ...speaking, ...(cloudAvailable ? { cloud_voices: cloud } : {}) } });
    setBusy(false);
    if (!r.ok) toast({ tone: 'danger', title: errorText(r.data, t('voice:saveFailed', 'Could not save the voice settings')) });
    else toast({ tone: 'ok', title: t('voice:saved', 'Voice settings saved.') });
  };
  return (
    <Panel title={t('voice:chronicle.title', 'Voice')} icon="ear">
      <form className="sr-form" onSubmit={save}>
        <ReadoutDefaults value={defaults} onChange={setDefaults} />
        {cloudAvailable ? <CloudVoicesChoice checked={cloud} onChange={setCloud} /> : null}
        <NarratorVoices value={narrator} onChange={setNarrator} cloud={cloudAvailable && cloud} />
        <SpeakingRules value={speaking} onChange={setSpeaking} />
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={busy}>{t('common:save', 'Save')}</Button>
        </div>
      </form>
      {canEdit ? <DeleteRecordings campaignId={campaignId} /> : null}
    </Panel>
  );
}

/** Chronicle: use cloud voices (Gemini), shown only when the site admin turned them on. */
export function CloudVoicesChoice({ checked, onChange }) {
  return (
    <fieldset className="sr-radio-group" data-testid="cloud-voices-choice">
      <legend>{t('voice:cloud.legend', 'Cloud voices')}</legend>
      <Checkbox
        label={t('voice:cloud.use', 'Use cloud voices (Google Gemini)')}
        checked={!!checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <p className="sr-muted sr-small">{t('voice:cloud.hint', 'Lines are spoken by Google’s Gemini voices: the text of each line is sent to Google. If Gemini fails or is busy, the local voices speak that line.')}</p>
    </fieldset>
  );
}

/** Chronicle settings → Voice: the Storyteller deletes every recording (messages keep their text). */
export function DeleteRecordings({ campaignId }) {
  const api = useApi();
  const { toast } = useToast();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    const r = await api(`/campaigns/${campaignId}/voice-clips`, { method: 'DELETE' });
    setBusy(false);
    setAsking(false);
    if (!r.ok) toast({ tone: 'danger', title: errorText(r.data, t('voice:chronicle.recordings.failed', 'Could not delete the recordings.')) });
    else toast({ tone: 'ok', title: t('voice:chronicle.recordings.done', 'Deleted {{count}} recordings.', { count: (r.data && r.data.deleted) || 0 }) });
  };
  return (
    <div className="sr-voice-recordings">
      <h3 className="sr-voice-recordings__title">{t('voice:chronicle.recordings.title', 'Voice recordings')}</h3>
      <p className="sr-field__hint">{t('voice:chronicle.recordings.hint', 'Delete every voice recording in this chronicle. The messages keep their text; only the replay goes.')}</p>
      <Button variant="danger" icon="trash" onClick={() => setAsking(true)}>
        {t('voice:chronicle.recordings.button', 'Delete all recordings')}
      </Button>
      <Modal
        open={asking}
        onClose={() => setAsking(false)}
        title={t('voice:chronicle.recordings.confirmTitle', 'Delete all voice recordings?')}
        icon="trash"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAsking(false)}>{t('voice:chronicle.recordings.cancel', 'Keep them')}</Button>
            <Button variant="danger" icon="trash" loading={busy} onClick={run}>{t('voice:chronicle.recordings.confirm', 'Delete recordings')}</Button>
          </>
        }
      >
        <p>{t('voice:chronicle.recordings.confirmBody', 'Every recorded voice message in this chronicle is deleted for everyone. The messages keep their text. This can’t be undone.')}</p>
      </Modal>
    </div>
  );
}

/** Chronicle: longest voice message, and whether players may use their phone's dictation. */
export function SpeakingRules({ value, onChange }) {
  const minutes = Math.round((Number(value.max_clip_seconds) || 180) / 6) / 10;
  return (
    <fieldset className="sr-radio-group" data-testid="speaking-rules">
      <legend>{t('voice:rules.legend', 'Voice messages')}</legend>
      <label className="sr-field">
        <span className="sr-field__label">{t('voice:rules.max', 'Longest recording: {{value}} min', { value: minutes })}</span>
        <input type="range" min="30" max="180" step="30" value={value.max_clip_seconds} onChange={(e) => onChange({ ...value, max_clip_seconds: Number(e.target.value) })} />
      </label>
      <Checkbox
        label={t('voice:rules.phone', 'Players may use their phone’s dictation (audio goes to Apple or Google)')}
        checked={value.allow_phone_stt !== false}
        onChange={(e) => onChange({ ...value, allow_phone_stt: e.target.checked })}
      />
    </fieldset>
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
    const body = { tts_source: s.tts_source, stt_source: s.stt_source, speak_lang: s.speak_lang, hear_lang: s.hear_lang, write_lang: s.write_lang, en_accent: s.en_accent, rate: Number(s.rate), volume: Number(s.volume), overrides: s.overrides };
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
          hint={t('voice:source.hint2')}
          value={s.tts_source}
          onChange={(e) => set({ tts_source: e.target.value })}
          options={[
            { value: 'server', label: t('voice:source.server', 'Server voices (recommended)') },
            { value: 'phone', label: t('voice:source.phone', 'My device’s voices') },
            { value: 'off', label: t('voice:source.off', 'Off') },
          ]}
        />
        <Select
          label={t('voice:stt.label', 'Voice messages are written by')}
          hint={t('voice:stt.hint', 'The server keeps your recording so the table can replay it. Phone dictation sends your audio to Apple or Google and keeps no recording.')}
          value={s.stt_source}
          onChange={(e) => set({ stt_source: e.target.value })}
          options={[
            { value: 'server', label: t('voice:stt.server', 'This site’s server') },
            { value: 'phone', label: t('voice:stt.phone', 'My phone’s dictation') },
          ]}
        />
        <Select
          label={t('voice:speak.label', 'I speak')}
          value={s.speak_lang}
          onChange={(e) => set({ speak_lang: e.target.value })}
          options={[
            { value: 'auto', label: t('voice:speak.auto', 'The app’s language') },
            { value: 'en', label: t('voice:langName.en', 'English') },
            { value: 'el', label: t('voice:langName.el', 'Greek') },
          ]}
        />
        <Select
          label={t('voice:hear.label', 'Read and hear messages in')}
          hint={t('voice:hear.hint', 'Lines in the other language are translated on the server ahead of time and shown in your language, with the original a tap away.')}
          value={s.hear_lang}
          onChange={(e) => set({ hear_lang: e.target.value })}
          options={[
            { value: 'written', label: t('voice:hear.written', 'As written') },
            { value: 'en', label: t('voice:langName.en', 'English') },
            { value: 'el', label: t('voice:langName.el', 'Greek') },
          ]}
        />
        <Select
          label={t('voice:write.label', 'Voice messages are sent in')}
          hint={t('voice:write.hint', 'Speak in one language and send the other: you see both before you send, and your original words stay under the message.')}
          value={s.write_lang}
          onChange={(e) => set({ write_lang: e.target.value })}
          options={[
            { value: 'same', label: t('voice:write.same', 'The language I speak') },
            { value: 'en', label: t('voice:langName.en', 'English') },
            { value: 'el', label: t('voice:langName.el', 'Greek') },
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

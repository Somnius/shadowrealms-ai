/**
 * Chronicle settings → The chronicle so far → Settings (the Storyteller and site admins only):
 * the night gap, table talk in exports, the nightly run and the writer model
 * (GET/PUT /api/campaigns/<id>/chronicle/settings, docs/CHRONICLE.md).
 */
import { useEffect, useState } from 'react';
import { Button, Input, Select, Switch } from '../../design';
import { errorText } from '../../app/http';
import { t } from '../../i18n';

const modelValue = (m) => (m ? `${m.provider}|${m.model}` : '');

export default function ChronicleSoFarSettings({ api, id, toast, onSaved }) {
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState(null);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    api(`/campaigns/${id}/chronicle/settings`).then((r) => {
      if (!alive) return;
      if (!r.ok || !r.data || !r.data.settings) {
        setFailed(true);
        return;
      }
      setInfo(r.data);
      setForm({ ...r.data.settings, gap_hours: String(r.data.settings.gap_hours) });
    });
    return () => {
      alive = false;
    };
  }, [api, id]);

  if (failed) return <p className="sr-sofar__error">{t('chronicle:soFar.settings.loadFailed', 'Could not load the settings.')}</p>;
  if (!form) return null;

  const [low, high] = info.gap_range || [2, 24];
  const gap = parseInt(form.gap_hours, 10);
  const gapBad = !(gap >= low && gap <= high) || String(gap) !== String(form.gap_hours).trim();
  const models = info.models || [];
  const chosen = models.find((m) => modelValue(m) === modelValue(form.model));

  const save = async (e) => {
    e.preventDefault();
    if (gapBad) return;
    setSaving(true);
    const body = { gap_hours: gap, table_talk: !!form.table_talk, nightly: !!form.nightly, model: form.model || null };
    const r = await api(`/campaigns/${id}/chronicle/settings`, { method: 'PUT', body });
    setSaving(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:soFar.settings.saveFailed', 'Could not save the settings.')) });
      return;
    }
    const changedGap = info.settings.gap_hours !== r.data.settings.gap_hours;
    setInfo(r.data);
    setForm({ ...r.data.settings, gap_hours: String(r.data.settings.gap_hours) });
    toast({
      tone: 'ok',
      title: changedGap
        ? t('chronicle:soFar.settings.savedGap', 'Saved. The nights the new gap cuts differently are written again on the next Update.')
        : t('chronicle:soFar.settings.saved', 'Settings saved.'),
    });
    if (onSaved) onSaved(r.data.settings);
  };

  return (
    <details className="sr-sofar__settings" data-testid="sofar-settings">
      <summary>{t('chronicle:soFar.settings.title', 'Settings')}</summary>
      <form className="sr-form" onSubmit={save}>
        <Input
          type="number"
          inputMode="numeric"
          min={low}
          max={high}
          label={t('chronicle:soFar.settings.gap', 'Night gap (hours)')}
          hint={t('chronicle:soFar.settings.gapHint', 'A night ends after this many hours with no message ({{low}}–{{high}}). Changing it cuts the nights again.', { low, high })}
          error={gapBad ? t('chronicle:soFar.settings.gapBad', 'A whole number from {{low}} to {{high}}.', { low, high }) : undefined}
          value={form.gap_hours}
          onChange={(e) => setForm({ ...form, gap_hours: e.target.value })}
          fieldClassName="sr-field--short"
        />
        <Switch
          checked={!!form.table_talk}
          onChange={(v) => setForm({ ...form, table_talk: v })}
          label={t('chronicle:soFar.settings.tableTalk', 'Table talk in exports by default')}
        />
        <Switch
          checked={!!form.nightly}
          onChange={(v) => setForm({ ...form, nightly: v })}
          label={t('chronicle:soFar.settings.nightly', 'Nightly run')}
        />
        <p className="sr-sofar__hint">
          {t('chronicle:soFar.settings.nightlyHint', 'At {{time}} (server time), when there are new messages, the chronicle is updated by itself, with the same rules as Update.', { time: info.nightly_at || '05:00' })}
        </p>
        <Select
          label={t('chronicle:soFar.settings.model', 'Writer model')}
          value={modelValue(form.model)}
          onChange={(e) => {
            const m = models.find((o) => modelValue(o) === e.target.value);
            setForm({ ...form, model: m ? { provider: m.provider, model: m.model } : null });
          }}
          options={[
            { value: '', label: t('chronicle:soFar.settings.modelDefault', 'Default (the chronicler roles)') },
            ...models.map((m) => ({ value: modelValue(m), label: `${m.model} · ${m.provider}` })),
          ]}
        />
        {chosen && chosen.cloud ? (
          <p className="sr-sofar__notice" role="alert">
            {t('chronicle:soFar.settings.cloudWarn', 'A cloud writer sends the whole chat of this chronicle, hidden rolls included, to an outside service.')}
          </p>
        ) : null}
        <p className="sr-sofar__hint">
          {t('chronicle:soFar.settings.caps', 'Each update writes at most {{nights}} nights and stops after about {{minutes}} minutes; Update carries on.', {
            nights: (info.caps && info.caps.nights_per_job) || 40,
            minutes: Math.round(((info.caps && info.caps.seconds_per_job) || 3600) / 60),
          })}
        </p>
        <div className="sr-form__actions">
          <Button type="submit" variant="primary" loading={saving} disabled={gapBad}>
            {t('chronicle:soFar.settings.save', 'Save settings')}
          </Button>
        </div>
      </form>
    </details>
  );
}

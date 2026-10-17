import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button, Card, Glyph, Input, Select, Textarea, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { errorText } from '../../app/http';
import { isV5Allowed } from '../../rules/rulesEdition';
import { getLanguage, t } from '../../i18n';
import './hall.css';
import { CloudVoicesChoice, DEFAULT_READOUT, NarratorVoices, ReadoutDefaults, narratorOf, useVoiceCatalog } from '../voice/VoiceSettings';

// Game lines per edition: Classic covers the Revised-era lines (and a custom system with Classic
// dice); V5 currently means Vampire: The Masquerade 5th Edition only (that's what the backend allows).
export const GAME_LINES = {
  classic: [
    { value: 'vampire', label: () => t('glossary:line.vampireRevised', 'Vampire: The Masquerade (Revised)') },
    { value: 'werewolf', label: () => t('glossary:line.werewolfRevised', 'Werewolf: The Apocalypse (Revised)') },
    { value: 'mage', label: () => t('glossary:line.mageRevised', 'Mage: The Ascension (Revised)') },
    { value: 'custom', label: () => t('glossary:line.custom', 'Custom system') },
  ],
  v5: [
    { value: 'vampire', label: () => t('glossary:line.vampireV5', 'Vampire: The Masquerade (5th Edition)') },
  ],
};

/** Every game line the app knows (any edition), for code that only needs the names. */
export const GAME_SYSTEMS = GAME_LINES.classic;

export default function CreateChroniclePage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { reload } = useChronicles();
  const [edition, setEdition] = useState('classic');
  const [system, setSystem] = useState('vampire');
  const lines = GAME_LINES[edition] || GAME_LINES.classic;

  const chooseEdition = (next) => {
    setEdition(next);
    // keep the game line if the new edition has it, otherwise take its first one
    if (!(GAME_LINES[next] || []).some((g) => g.value === system)) setSystem(GAME_LINES[next][0].value);
  };
  const [busy, setBusy] = useState(false);
  // the chronicle's language: what "The chronicle so far" is written in (default: the creator's app language)
  const [chronLang, setChronLang] = useState(getLanguage() === 'el' ? 'el' : 'en');
  const [readout, setReadout] = useState(DEFAULT_READOUT);
  const [narrator, setNarrator] = useState(narratorOf(null));
  const [cloud, setCloud] = useState(false);
  const catalog = useVoiceCatalog();
  // the catalog lists Gemini voices only when the site admin turned cloud voices on
  const cloudAvailable = !!(catalog && (catalog.cloud_voices || []).length);
  const [error, setError] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setBusy(true);
    setError('');
    const r = await api('/campaigns', {
      method: 'POST',
      body: {
        name: String(fd.get('name') || '').trim(),
        description: String(fd.get('description') || '').trim(),
        game_system: system,
        rules_edition: edition === 'v5' && isV5Allowed(system) ? 'v5' : 'classic',
        language: chronLang,
      },
    });
    setBusy(false);
    if (!r.ok) {
      setError(errorText(r.data, t('chronicle:create.failed', 'Could not create the chronicle')));
      return;
    }
    // voice read-out defaults: best effort, they can be changed later in Chronicle settings
    await api(`/campaigns/${r.data.campaign_id}/voice-settings`, { method: 'PUT', body: { defaults: readout, ...narrator, ...(cloudAvailable ? { cloud_voices: cloud } : {}) } });
    toast({ tone: 'ok', title: t('chronicle:create.done', 'Chronicle created.') });
    await reload();
    navigate(`/chronicles/${r.data.campaign_id}`);
  };

  return (
    <>
      <TopBar title={t('chronicle:create.title', 'New chronicle')} icon="quill" />
      <PageBody narrow>
        <Card className="sr-pad">
          <form className="sr-form" onSubmit={submit}>
            <Input name="name" label={t('chronicle:field.name', 'Name')} required autoFocus />
            <Textarea
              name="description"
              label={t('chronicle:field.description', 'World and setting')}
              hint={t('chronicle:field.descriptionHint', 'The Storyteller AI reads this as the chronicle’s world. You can edit it later.')}
              rows={6}
              required
            />
            <fieldset className="sr-radio-group" data-testid="rules-edition-choice">
              <legend>{t('chronicle:field.edition', 'Edition')}</legend>
              {[
                ['classic', t('chronicle:edition.classic', 'Classic (Revised)'), t('chronicle:edition.classicHint', 'd10 vs target number, 1s cancel, botches')],
                ['v5', t('chronicle:edition.v5', 'V5 (5th Edition)'), t('chronicle:edition.v5Hint', 'successes needed, Hunger dice, criticals')],
              ].map(([value, label, hint]) => (
                <label key={value} className="sr-radio">
                  <input type="radio" name="rules_edition" value={value} checked={edition === value} onChange={() => chooseEdition(value)} />
                  <span>
                    {label} <span className="sr-muted">· {hint}</span>
                  </span>
                </label>
              ))}
              <p className="sr-muted sr-small">{t('chronicle:edition.locked', 'The edition is locked once the chronicle is created.')}</p>
            </fieldset>
            <Select
              label={t('chronicle:field.system', 'Game line')}
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              options={lines.map((g) => ({ value: g.value, label: g.label() }))}
              hint={edition === 'v5' ? t('chronicle:field.systemV5Hint', 'V5 currently supports Vampire: The Masquerade.') : undefined}
            />
            <Select
              label={t('chronicle:field.language', 'Chronicle language')}
              value={chronLang}
              onChange={(e) => setChronLang(e.target.value)}
              options={[
                { value: 'el', label: 'Ελληνικά' },
                { value: 'en', label: 'English' },
              ]}
              hint={t('chronicle:field.languageHint', 'The chronicle so far is written in this language. You can change it later in Chronicle settings.')}
              data-testid="chronicle-language"
            />
            <ReadoutDefaults value={readout} onChange={setReadout} />
            {cloudAvailable ? <CloudVoicesChoice checked={cloud} onChange={setCloud} /> : null}
            <NarratorVoices value={narrator} onChange={setNarrator} cloud={cloudAvailable && cloud} />
            {error ? (
              <p className="sr-error" role="alert">
                <Glyph name="warning" size={16} /> {error}
              </p>
            ) : null}
            <div className="sr-form__actions">
              <ButtonLink to="/chronicles" variant="ghost">
                {t('common:cancel', 'Cancel')}
              </ButtonLink>
              <Button type="submit" variant="primary" loading={busy}>
                {t('chronicle:create.submit', 'Create chronicle')}
              </Button>
            </div>
          </form>
        </Card>
      </PageBody>
    </>
  );
}

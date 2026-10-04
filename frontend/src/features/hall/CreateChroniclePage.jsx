import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Glyph, Input, Select, Textarea, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { errorText } from '../../app/http';
import { isV5Allowed } from '../../rules/rulesEdition';
import { t } from '../../i18n';
import './hall.css';

export const GAME_SYSTEMS = [
  { value: 'vampire', label: () => t('glossary:line.vampire', 'Vampire: The Masquerade') },
  { value: 'werewolf', label: () => t('glossary:line.werewolf', 'Werewolf: The Apocalypse') },
  { value: 'mage', label: () => t('glossary:line.mage', 'Mage: The Ascension') },
  { value: 'custom', label: () => t('glossary:line.custom', 'Custom system') },
];

export default function CreateChroniclePage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { reload } = useChronicles();
  const [system, setSystem] = useState('vampire');
  const [edition, setEdition] = useState('classic');
  const [busy, setBusy] = useState(false);
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
        rules_edition: isV5Allowed(system) ? edition : 'classic',
      },
    });
    setBusy(false);
    if (!r.ok) {
      setError(errorText(r.data, t('chronicle:create.failed', 'Could not create the chronicle')));
      return;
    }
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
            <Select
              label={t('chronicle:field.system', 'Game line')}
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              options={GAME_SYSTEMS.map((g) => ({ value: g.value, label: g.label() }))}
            />
            {isV5Allowed(system) ? (
              <fieldset className="sr-radio-group" data-testid="rules-edition-choice">
                <legend>{t('chronicle:field.edition', 'Edition')}</legend>
                {[
                  ['classic', t('chronicle:edition.classic', 'Classic (Revised)'), t('chronicle:edition.classicHint', 'd10 vs target number, 1s cancel, botches')],
                  ['v5', t('chronicle:edition.v5', 'V5 (5th Edition)'), t('chronicle:edition.v5Hint', 'successes needed, Hunger dice, criticals')],
                ].map(([value, label, hint]) => (
                  <label key={value} className="sr-radio">
                    <input type="radio" name="rules_edition" value={value} checked={edition === value} onChange={() => setEdition(value)} />
                    <span>
                      {label} <span className="sr-muted">· {hint}</span>
                    </span>
                  </label>
                ))}
                <p className="sr-muted sr-small">{t('chronicle:edition.locked', 'The edition is locked once the chronicle is created.')}</p>
              </fieldset>
            ) : null}
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

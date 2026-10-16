/**
 * Voice gender of a character (docs/VOICE.md): which server voice says its lines.
 * Female / Male / Neutral; not set is spoken with the neutral voice, and the sheet reminds the owner.
 */
import { useState } from 'react';
import { Select } from '../../design';
import { apiFetch, errorText, getCurrentToken } from '../../app/http';
import { t } from '../../i18n';

export const GENDERS = ['female', 'male', 'neutral'];

export function genderLabel(g) {
  if (g === 'female') return t('voice:gender.female', 'Female');
  if (g === 'male') return t('voice:gender.male', 'Male');
  if (g === 'neutral') return t('voice:gender.neutral', 'Neutral');
  return t('voice:gender.unset', 'Not set');
}

const options = () => [
  { value: '', label: genderLabel('') },
  ...GENDERS.map((g) => ({ value: g, label: genderLabel(g) })),
];

/** The Forge's field. value: '' | 'female' | 'male' | 'neutral'. */
export function GenderField({ id = 'field-voice-gender', value, onChange }) {
  return (
    <Select
      id={id}
      label={t('voice:gender.label', 'Voice')}
      hint={t('voice:gender.hint', 'Which voice reads this character’s lines aloud. Not set uses a neutral voice.')}
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      options={options()}
    />
  );
}

/**
 * The line on the character sheet: read-only for others; the owner can set it (also on a locked
 * sheet: it is not a rule). Unset shows the reminder.
 */
export function VoiceGenderLine({ character, owner }) {
  const [value, setValue] = useState(character && character.gender ? character.gender : '');
  const [error, setError] = useState('');
  if (!character) return null;
  const save = async (next) => {
    const before = value;
    setValue(next);
    setError('');
    const r = await apiFetch(getCurrentToken(), `/characters/${character.id}`, { method: 'PUT', body: { gender: next || null } });
    if (!r.ok) {
      setValue(before);
      setError(errorText(r.data, t('voice:gender.saveFailed', 'Could not save the voice.')));
    }
  };
  return (
    <div className="sr-voice-gender" data-testid="voice-gender">
      {owner ? (
        <Select
          id={`voice-gender-${character.id}`}
          label={t('voice:gender.label', 'Voice')}
          value={value}
          onChange={(e) => save(e.target.value)}
          options={options()}
        />
      ) : (
        <p className="sr-voice-gender__value">
          <strong>{t('voice:gender.label', 'Voice')}:</strong> {genderLabel(value)}
        </p>
      )}
      {!value && owner ? (
        <p className="sr-muted sr-small">{t('voice:gender.reminder', 'Set a voice so this character is read aloud with a matching voice. Until then a neutral voice is used.')}</p>
      ) : null}
      {error ? <p className="sr-field__error" role="alert">{error}</p> : null}
    </div>
  );
}

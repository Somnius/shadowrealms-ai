import { Glyph } from '../design';
import { t } from '../i18n';
import './fallenNote.css';

/** A fallen character's death (character.death from GET /api/characters), on the profile card and the sheet. */
export default function FallenNote({ character, compact = false }) {
  const death = character && character.death;
  if (!death) return null;
  return (
    <div className={`sr-fallen${compact ? ' sr-fallen--compact' : ''}`} role="note" data-testid="fallen-note">
      <p className="sr-fallen__title">
        <Glyph name="skull" size={16} />
        {t('sheet:fallen.title', 'Fallen')}
      </p>
      {death.death_description ? <p className="sr-fallen__text">{death.death_description}</p> : null}
    </div>
  );
}

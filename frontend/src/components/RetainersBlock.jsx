import { Button } from '../design';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import { ghoulTemplateName } from '../characterSheet/i18nErrors';
import { KIND_LABELS } from '../characterSheet/classicGhoul';
import { t } from '../i18n';

const n = (v) => {
  const x = parseInt(v, 10);
  return Number.isFinite(x) ? x : 0;
};

/** 'Vassal' / 'Independent' / 'Revenant' in the active language (a Classic ghoul's kind). */
export const kindName = (kind) => (KIND_LABELS[kind] ? t(`sheet:classicGhoul.kind.${kind}`, KIND_LABELS[kind]) : String(kind || ''));

/** What a retainer row says under its name: a V5 ghoul's template and Retainers dots, a Classic one's kind. */
function retainerDetail(r) {
  if (String(r.rules_edition || '').toLowerCase() !== 'v5' && r.kind) return kindName(r.kind);
  return [r.template ? ghoulTemplateName(r.template) : '', n(r.retainer_dots) ? `Retainers ${'•'.repeat(n(r.retainer_dots))}` : '']
    .filter(Boolean)
    .join(' · ');
}

/**
 * A vampire's ghouls (GET /api/characters/<id> `retainers`), V5 or Classic: each opens its sheet;
 * the owner may add one (the ghoul forge, /profile/characters/new?ghoul_of=<id>).
 */
export default function RetainersBlock({ character, onOpenSheet, onAddGhoul, accent = 'var(--sr-blood-500)', sectionId = 'v5-view-retainers' }) {
  const list = Array.isArray(character?.retainers) ? character.retainers : [];
  if (!list.length && !onAddGhoul) return null;
  return (
    <ResponsiveSheetBlock sectionId={sectionId} title={t('sheet:ghoul.retainersTitle', 'Retainers (ghouls)')} accent={accent}>
      {list.length ? (
        list.map((r) => (
          <div key={r.id} data-retainer={r.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', color: 'var(--sr-bone-100)' }}>
            {r.portrait_url ? (
              <img src={r.portrait_url} alt="" style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }} />
            ) : null}
            <span style={{ flex: 1 }}>
              <strong>{r.name}</strong>
              <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}> {retainerDetail(r)}</span>
            </span>
            {onOpenSheet ? (
              <Button size="sm" variant="secondary" icon="scroll" onClick={() => onOpenSheet(r.id)}>
                {t('sheet:ghoul.openSheet', 'Open sheet')}
              </Button>
            ) : null}
          </div>
        ))
      ) : (
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '13px', margin: '0 0 8px' }}>{t('sheet:ghoul.noRetainers', 'No ghouls yet.')}</p>
      )}
      {onAddGhoul ? (
        <Button size="sm" variant="primary" icon="plus" onClick={() => onAddGhoul(character.id)}>
          {t('sheet:ghoul.addRetainer', 'Add a ghoul retainer')}
        </Button>
      ) : null}
    </ResponsiveSheetBlock>
  );
}

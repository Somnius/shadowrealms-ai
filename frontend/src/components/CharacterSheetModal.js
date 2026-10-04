import { Badge, Modal } from '../design';
import './sheet.css';
import DotTrack from './characterCreation/DotTrack';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import V5CharacterSheetView from './V5CharacterSheetView';
import { editionLabel, editionOf, V5 } from '../rules/rulesEdition';
import {
  KNOWLEDGES,
  PHYSICAL,
  MENTAL,
  SKILLS,
  SOCIAL,
  TALENTS,
} from '../characterSheet/constants';
import { t } from '../i18n';
import { Term } from '../i18n/glossary';

function StaticDots({ value, maxRank = 5, accent = 'var(--sr-arcane-300)' }) {
  const rank = Math.max(0, Math.min(maxRank, parseInt(value, 10) || 0));
  return (
    <DotTrack value={String(rank)} maxRank={maxRank} accent={accent} disabled onChange={() => {}} />
  );
}

function attrPoolLabel(attrs, keys) {
  return keys.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
}

/**
 * Read-only oWoD-style sheet (dots + sections) for viewing a sealed character — similar layout to the forge.
 */
export default function CharacterSheetModal({ character, gameSystem, onClose }) {
  if (!character) return null;

  const gs = String(gameSystem || character.system_type || '').toLowerCase();
  const isV5Sheet = editionOf(character) === V5;
  const wm = character.wod_meta && typeof character.wod_meta === 'object' ? character.wod_meta : {};
  const attrs = character.attributes && typeof character.attributes === 'object' ? character.attributes : {};
  const skillsRoot = character.skills && typeof character.skills === 'object' ? character.skills : {};
  const talents = skillsRoot.talents || {};
  const skills = skillsRoot.skills || {};
  const knowledges = skillsRoot.knowledges || {};
  const mf = character.merits_flaws && typeof character.merits_flaws === 'object' ? character.merits_flaws : {};
  const meritEntries = Array.isArray(mf.entries) ? mf.entries : [];

  const accent = gs === 'werewolf' ? 'var(--sr-ok-400)' : gs === 'mage' ? 'var(--sr-info-400)' : 'var(--sr-blood-500)';
  const theme = gs === 'werewolf' ? 'werewolf' : gs === 'mage' ? 'mage' : 'vampire';

  const physPool = attrPoolLabel(attrs, PHYSICAL);
  const socPool = attrPoolLabel(attrs, SOCIAL);
  const menPool = attrPoolLabel(attrs, MENTAL);

  const col = (title, keys, pool) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'var(--sr-font-display)',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: 'var(--sr-bone-500)', fontFamily: 'var(--sr-font-ui)', marginLeft: '6px' }}>{t('sheet:pts', '({{n}} pts)', { n: pool })}</span>
      </div>
      {keys.map((k) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '10px',
            marginBottom: '10px',
            padding: '6px 8px',
            background: 'rgba(0,0,0,0.2)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: 'var(--sr-bone-100)', fontSize: '13px', textTransform: 'capitalize', flex: '1 1 auto' }}>
            {k}
          </span>
          <StaticDots value={attrs[k]} maxRank={5} accent={accent} />
        </div>
      ))}
    </div>
  );

  const abilityCol = (title, list, map) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'var(--sr-font-display)',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
        }}
      >
        {title}
      </div>
      {list.map(([k, label]) => (
        <div
          key={k}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
            marginBottom: '8px',
            padding: '4px 6px',
            background: 'rgba(0,0,0,0.15)',
            borderRadius: '6px',
          }}
        >
          <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px', flex: 1 }}>{label}</span>
          <StaticDots value={map[k]} maxRank={5} accent={accent} />
        </div>
      ))}
    </div>
  );

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      className={`sr-sheet sr-sheet--${theme}`}
      icon={theme === 'werewolf' ? 'line-werewolf' : theme === 'mage' ? 'line-mage' : 'line-vampire'}
      title={character.name || t('sheet:untitled', 'Character')}
      closeLabel={t('sheet:close', 'Close')}
      description={
        character.campaign_name || gs === 'vampire' || isV5Sheet ? (
          <span className="sr-sheet__sub">
            {character.campaign_name ? <span>{character.campaign_name}</span> : null}
            {gs === 'vampire' || isV5Sheet ? <Badge edition={editionLabel(character)} tone={isV5Sheet ? 'blood' : 'neutral'} /> : null}
          </span>
        ) : null
      }
    >
          <div className="sr-sheet__body" data-line={theme}>
            {isV5Sheet ? (
              <V5CharacterSheetView character={character} />
            ) : (
            <>
            <p style={{ color: 'var(--sr-bone-500)', fontSize: '13px', marginTop: 0, lineHeight: 1.5 }}>
              {t('sheet:classicIntro', 'Classic WoD–style sheet (read-only). Numbers match your sealed chronicle record.')}
            </p>

            <ResponsiveSheetBlock sectionId="view-identity" title={t('sheet:identity', 'Identity')} subtitle={t('sheet:identitySub', 'Concept & nature')} accent={accent}>
              {wm.concept != null && String(wm.concept).trim() ? (
                <p style={{ color: 'var(--sr-bone-100)', margin: '0 0 10px' }}>
                  <strong style={{ color: 'var(--sr-arcane-300)' }}>{t('sheet:concept', 'Concept:')}</strong> {String(wm.concept)}
                </p>
              ) : null}
              {wm.nature != null && String(wm.nature).trim() ? (
                <p style={{ color: 'var(--sr-bone-100)', margin: '0 0 10px' }}>
                  <strong style={{ color: 'var(--sr-arcane-300)' }}>Nature:</strong> {String(wm.nature)}
                </p>
              ) : null}
              {wm.demeanor != null && String(wm.demeanor).trim() ? (
                <p style={{ color: 'var(--sr-bone-100)', margin: '0 0 10px' }}>
                  <strong style={{ color: 'var(--sr-arcane-300)' }}>Demeanor:</strong> {String(wm.demeanor)}
                </p>
              ) : null}
            </ResponsiveSheetBlock>

            <ResponsiveSheetBlock sectionId="view-template" title={t('sheet:template', 'Template')} accent={accent}>
              {gs === 'vampire' && (
                <div style={{ color: 'var(--sr-bone-100)', display: 'grid', gap: '8px', fontSize: '14px' }}>
                  {wm.clan ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="clan" />:</strong> {wm.clan}
                    </p>
                  ) : null}
                  {wm.generation != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="generation" />:</strong> {String(wm.generation)}
                    </p>
                  ) : null}
                  {wm.humanity != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="humanity" />:</strong> {String(wm.humanity)}
                    </p>
                  ) : null}
                  {wm.willpower != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="willpower" />:</strong> {String(wm.willpower)}
                    </p>
                  ) : null}
                  {wm.virtues && typeof wm.virtues === 'object' ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="virtues" />:</strong>{' '}
                      {/* Virtue names are game terms and stay English (see i18n/glossary). */}
                      <span lang="en">
                        {[['conscience', 'Conscience'], ['self_control', 'Self-Control'], ['courage', 'Courage']]
                          .map(([k, label]) => `${label}: ${wm.virtues[k] ?? '—'}`)
                          .join(' · ')}
                      </span>
                    </p>
                  ) : null}
                  {Array.isArray(wm.disciplines) && wm.disciplines.length ? (
                    <div style={{ marginTop: 8 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="discipline">Disciplines</Term></strong>
                      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem', color: 'var(--sr-bone-100)' }}>
                        {wm.disciplines.map((d, i) => (
                          <li key={i}>
                            {d.name} <StaticDots value={d.dots} maxRank={5} accent={accent} />
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {Array.isArray(wm.backgrounds) && wm.backgrounds.length ? (
                    <div style={{ marginTop: 8 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}><Term id="backgrounds" /></strong>
                      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem', color: 'var(--sr-bone-100)' }}>
                        {wm.backgrounds.map((b, i) => (
                          <li key={i}>
                            {b.name} <StaticDots value={b.dots} maxRank={5} accent={accent} />
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}
              {gs === 'werewolf' && (
                <div style={{ color: 'var(--sr-bone-100)', fontSize: '14px', display: 'grid', gap: 6 }}>
                  {wm.breed ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Breed:</strong> {wm.breed}
                    </p>
                  ) : null}
                  {wm.auspice ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Auspice:</strong> {wm.auspice}
                    </p>
                  ) : null}
                  {wm.tribe ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Tribe:</strong> {wm.tribe}
                    </p>
                  ) : null}
                  {wm.rage != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Rage:</strong> {String(wm.rage)}
                    </p>
                  ) : null}
                  {wm.gnosis != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Gnosis:</strong> {String(wm.gnosis)}
                    </p>
                  ) : null}
                  {wm.gifts_notes ? (
                    <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>{t('sheet:giftsNotes', 'Gifts / notes:')}</strong> {wm.gifts_notes}
                    </p>
                  ) : null}
                </div>
              )}
              {gs === 'mage' && (
                <div style={{ color: 'var(--sr-bone-100)', fontSize: '14px' }}>
                  {wm.tradition ? (
                    <p style={{ margin: '0 0 8px' }}>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Tradition:</strong> {wm.tradition}
                    </p>
                  ) : null}
                  {wm.spheres && typeof wm.spheres === 'object' ? (
                    <div>
                      <strong style={{ color: 'var(--sr-arcane-300)' }}>Spheres</strong>
                      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem' }}>
                        {Object.entries(wm.spheres).map(([k, v]) => (
                          <li key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ minWidth: 100 }}>{k}</span>
                            <StaticDots value={v} maxRank={5} accent={accent} />
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}
            </ResponsiveSheetBlock>

            <ResponsiveSheetBlock sectionId="view-attr" title={<Term id="attributes" />} accent={accent}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                {col('Physical', PHYSICAL, physPool)}
                {col('Social', SOCIAL, socPool)}
                {col('Mental', MENTAL, menPool)}
              </div>
            </ResponsiveSheetBlock>

            <ResponsiveSheetBlock sectionId="view-abilities" title={<Term id="abilities" />} accent={accent}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                {abilityCol('Talents', TALENTS, talents)}
                {abilityCol('Skills', SKILLS, skills)}
                {abilityCol('Knowledges', KNOWLEDGES, knowledges)}
              </div>
            </ResponsiveSheetBlock>

            {character.background != null && String(character.background).trim() ? (
              <ResponsiveSheetBlock sectionId="view-story" title={t('sheet:backgroundNotes', 'Background & notes')} accent={accent}>
                <p style={{ color: 'var(--sr-bone-100)', whiteSpace: 'pre-wrap', lineHeight: 1.55, margin: 0 }}>
                  {String(character.background)}
                </p>
              </ResponsiveSheetBlock>
            ) : null}

            {meritEntries.length > 0 || (mf.notes && String(mf.notes).trim()) ? (
              <ResponsiveSheetBlock sectionId="view-merits" title={<Term id="merits" />} accent={accent}>
                {meritEntries.map((e, i) => (
                  <div
                    key={i}
                    style={{
                      marginBottom: 10,
                      padding: 8,
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: 6,
                      color: 'var(--sr-bone-100)',
                    }}
                  >
                    <strong>{e.name}</strong> ({e.points > 0 ? '+' : ''}
                    {e.points}){e.note ? ` — ${e.note}` : ''}
                  </div>
                ))}
                {mf.notes && String(mf.notes).trim() ? (
                  <p style={{ color: 'var(--sr-bone-300)', whiteSpace: 'pre-wrap', marginTop: 8 }}>{mf.notes}</p>
                ) : null}
              </ResponsiveSheetBlock>
            ) : null}
            </>
            )}
          </div>
    </Modal>
  );
}

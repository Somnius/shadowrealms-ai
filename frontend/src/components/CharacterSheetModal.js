import React from 'react';
import { GothicBox } from './GothicDecorations';
import DotTrack from './characterCreation/DotTrack';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import {
  KNOWLEDGES,
  PHYSICAL,
  MENTAL,
  SKILLS,
  SOCIAL,
  TALENTS,
} from '../characterSheet/constants';

function StaticDots({ value, maxRank = 5, accent = '#c4b5fd' }) {
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
  const wm = character.wod_meta && typeof character.wod_meta === 'object' ? character.wod_meta : {};
  const attrs = character.attributes && typeof character.attributes === 'object' ? character.attributes : {};
  const skillsRoot = character.skills && typeof character.skills === 'object' ? character.skills : {};
  const talents = skillsRoot.talents || {};
  const skills = skillsRoot.skills || {};
  const knowledges = skillsRoot.knowledges || {};
  const mf = character.merits_flaws && typeof character.merits_flaws === 'object' ? character.merits_flaws : {};
  const meritEntries = Array.isArray(mf.entries) ? mf.entries : [];

  const accent = gs === 'werewolf' ? '#4ade80' : gs === 'mage' ? '#38bdf8' : '#e94560';
  const theme = gs === 'werewolf' ? 'werewolf' : gs === 'mage' ? 'mage' : 'vampire';

  const physPool = attrPoolLabel(attrs, PHYSICAL);
  const socPool = attrPoolLabel(attrs, SOCIAL);
  const menPool = attrPoolLabel(attrs, MENTAL);

  const col = (title, keys, pool) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div
        style={{
          textAlign: 'center',
          fontFamily: 'Cinzel, serif',
          fontSize: '12px',
          color: accent,
          marginBottom: '12px',
          letterSpacing: '0.08em',
        }}
      >
        {title}
        <span style={{ color: '#6b7280', fontFamily: 'system-ui', marginLeft: '6px' }}>({pool} pts)</span>
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
          <span style={{ color: '#d1d5db', fontSize: '13px', textTransform: 'capitalize', flex: '1 1 auto' }}>
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
          fontFamily: 'Cinzel, serif',
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
          <span style={{ color: '#cbd5e1', fontSize: '12px', flex: 1 }}>{label}</span>
          <StaticDots value={map[k]} maxRank={5} accent={accent} />
        </div>
      ))}
    </div>
  );

  return (
    <div
      role="presentation"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.82)',
        zIndex: 12000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="character-sheet-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 'min(1040px, 100vw)',
          maxHeight: 'min(92vh, 100%)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <GothicBox theme={theme} style={{ display: 'flex', flexDirection: 'column', maxHeight: '100%' }}>
          <div
            style={{
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '14px 16px',
              borderBottom: '1px solid #2a2a4e',
            }}
          >
            <h2
              id="character-sheet-title"
              style={{
                margin: 0,
                fontFamily: 'Cinzel, serif',
                color: accent,
                fontSize: '1.25rem',
              }}
            >
              {character.name || 'Character'}
              {character.campaign_name ? (
                <span style={{ color: '#94a3b8', fontWeight: 'normal', fontSize: '0.9rem' }}>
                  {' '}
                  · {character.campaign_name}
                </span>
              ) : null}
            </h2>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                background: '#0f1729',
                color: '#e0e0e0',
                border: '1px solid #475569',
                borderRadius: '8px',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif',
              }}
            >
              Close
            </button>
          </div>

          <div style={{ overflow: 'auto', padding: '12px 16px 24px', flex: 1 }}>
            <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: 0, lineHeight: 1.5 }}>
              Classic WoD–style sheet (read-only). Numbers match your sealed chronicle record.
            </p>

            <ResponsiveSheetBlock sectionId="view-identity" title="Identity" subtitle="Concept & nature" accent={accent}>
              {wm.concept != null && String(wm.concept).trim() ? (
                <p style={{ color: '#e0e0e0', margin: '0 0 10px' }}>
                  <strong style={{ color: '#c4b5fd' }}>Concept:</strong> {String(wm.concept)}
                </p>
              ) : null}
              {wm.nature != null && String(wm.nature).trim() ? (
                <p style={{ color: '#e0e0e0', margin: '0 0 10px' }}>
                  <strong style={{ color: '#c4b5fd' }}>Nature:</strong> {String(wm.nature)}
                </p>
              ) : null}
              {wm.demeanor != null && String(wm.demeanor).trim() ? (
                <p style={{ color: '#e0e0e0', margin: '0 0 10px' }}>
                  <strong style={{ color: '#c4b5fd' }}>Demeanor:</strong> {String(wm.demeanor)}
                </p>
              ) : null}
            </ResponsiveSheetBlock>

            <ResponsiveSheetBlock sectionId="view-template" title="Template" accent={accent}>
              {gs === 'vampire' && (
                <div style={{ color: '#e0e0e0', display: 'grid', gap: '8px', fontSize: '14px' }}>
                  {wm.clan ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Clan:</strong> {wm.clan}
                    </p>
                  ) : null}
                  {wm.generation != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Generation:</strong> {String(wm.generation)}
                    </p>
                  ) : null}
                  {wm.humanity != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Humanity:</strong> {String(wm.humanity)}
                    </p>
                  ) : null}
                  {wm.willpower != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Willpower:</strong> {String(wm.willpower)}
                    </p>
                  ) : null}
                  {wm.virtues && typeof wm.virtues === 'object' ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Virtues:</strong>{' '}
                      {['conscience', 'self_control', 'courage']
                        .map((k) => `${k}: ${wm.virtues[k] ?? '—'}`)
                        .join(' · ')}
                    </p>
                  ) : null}
                  {Array.isArray(wm.disciplines) && wm.disciplines.length ? (
                    <div style={{ marginTop: 8 }}>
                      <strong style={{ color: '#c4b5fd' }}>Disciplines</strong>
                      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem', color: '#d1d5db' }}>
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
                      <strong style={{ color: '#c4b5fd' }}>Backgrounds</strong>
                      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem', color: '#d1d5db' }}>
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
                <div style={{ color: '#e0e0e0', fontSize: '14px', display: 'grid', gap: 6 }}>
                  {wm.breed ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Breed:</strong> {wm.breed}
                    </p>
                  ) : null}
                  {wm.auspice ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Auspice:</strong> {wm.auspice}
                    </p>
                  ) : null}
                  {wm.tribe ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Tribe:</strong> {wm.tribe}
                    </p>
                  ) : null}
                  {wm.rage != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Rage:</strong> {String(wm.rage)}
                    </p>
                  ) : null}
                  {wm.gnosis != null ? (
                    <p style={{ margin: 0 }}>
                      <strong style={{ color: '#c4b5fd' }}>Gnosis:</strong> {String(wm.gnosis)}
                    </p>
                  ) : null}
                  {wm.gifts_notes ? (
                    <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                      <strong style={{ color: '#c4b5fd' }}>Gifts / notes:</strong> {wm.gifts_notes}
                    </p>
                  ) : null}
                </div>
              )}
              {gs === 'mage' && (
                <div style={{ color: '#e0e0e0', fontSize: '14px' }}>
                  {wm.tradition ? (
                    <p style={{ margin: '0 0 8px' }}>
                      <strong style={{ color: '#c4b5fd' }}>Tradition:</strong> {wm.tradition}
                    </p>
                  ) : null}
                  {wm.spheres && typeof wm.spheres === 'object' ? (
                    <div>
                      <strong style={{ color: '#c4b5fd' }}>Spheres</strong>
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

            <ResponsiveSheetBlock sectionId="view-attr" title="Attributes" accent={accent}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                {col('Physical', PHYSICAL, physPool)}
                {col('Social', SOCIAL, socPool)}
                {col('Mental', MENTAL, menPool)}
              </div>
            </ResponsiveSheetBlock>

            <ResponsiveSheetBlock sectionId="view-abilities" title="Abilities" accent={accent}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
                {abilityCol('Talents', TALENTS, talents)}
                {abilityCol('Skills', SKILLS, skills)}
                {abilityCol('Knowledges', KNOWLEDGES, knowledges)}
              </div>
            </ResponsiveSheetBlock>

            {character.background != null && String(character.background).trim() ? (
              <ResponsiveSheetBlock sectionId="view-story" title="Background & notes" accent={accent}>
                <p style={{ color: '#d1d5db', whiteSpace: 'pre-wrap', lineHeight: 1.55, margin: 0 }}>
                  {String(character.background)}
                </p>
              </ResponsiveSheetBlock>
            ) : null}

            {meritEntries.length > 0 || (mf.notes && String(mf.notes).trim()) ? (
              <ResponsiveSheetBlock sectionId="view-merits" title="Merits & flaws" accent={accent}>
                {meritEntries.map((e, i) => (
                  <div
                    key={i}
                    style={{
                      marginBottom: 10,
                      padding: 8,
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: 6,
                      color: '#e0e0e0',
                    }}
                  >
                    <strong>{e.name}</strong> ({e.points > 0 ? '+' : ''}
                    {e.points}){e.note ? ` — ${e.note}` : ''}
                  </div>
                ))}
                {mf.notes && String(mf.notes).trim() ? (
                  <p style={{ color: '#94a3b8', whiteSpace: 'pre-wrap', marginTop: 8 }}>{mf.notes}</p>
                ) : null}
              </ResponsiveSheetBlock>
            ) : null}
          </div>
        </GothicBox>
      </div>
    </div>
  );
}

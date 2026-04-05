import React, { useState } from 'react';
import { GothicBox } from './GothicDecorations';

/** Client-side WoD-style pool roll for showcase / readme — no API. */
function rollStorytellerPool(poolSize, difficulty, specialty) {
  const results = [];
  for (let i = 0; i < poolSize; i += 1) {
    results.push(Math.floor(Math.random() * 10) + 1);
  }
  let successes = 0;
  for (const d of results) {
    if (d === 1) continue;
    if (d >= difficulty) successes += 1;
    if (specialty && d === 10) successes += 1;
  }
  const ones = results.filter((d) => d === 1).length;
  const isBotch = successes === 0 && ones > 0;
  const isCritical = successes >= 5;
  let message = `${successes} success${successes === 1 ? '' : 'es'}`;
  if (isBotch) message = 'Botch — no successes and at least one 1!';
  else if (isCritical) message = `${message} — exceptional!`;
  return {
    results,
    successes,
    message,
    is_botch: isBotch,
    is_critical: isCritical,
  };
}

export default function DemoDiceRollerModal({ onClose }) {
  const [poolSize, setPoolSize] = useState(5);
  const [difficulty, setDifficulty] = useState(6);
  const [specialty, setSpecialty] = useState(false);
  const [actionDesc, setActionDesc] = useState('Perception + Alertness');
  const [rolling, setRolling] = useState(false);
  const [lastRoll, setLastRoll] = useState(null);

  const handleRoll = () => {
    if (poolSize < 1) return;
    setRolling(true);
    window.setTimeout(() => {
      const r = rollStorytellerPool(poolSize, difficulty, specialty);
      setLastRoll({ ...r, difficulty, poolSize });
      setRolling(false);
    }, 380);
  };

  return (
    <div
      className="sr-demo-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sr-demo-dice-title"
      onClick={onClose}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div onClick={(e) => e.stopPropagation()} role="presentation">
      <GothicBox
        theme="vampire"
        style={{
          background: 'linear-gradient(165deg, rgba(22, 33, 62, 0.98) 0%, rgba(15, 23, 41, 0.99) 100%)',
          padding: '28px',
          borderRadius: '14px',
          maxWidth: '440px',
          width: '100%',
          border: '1px solid rgba(233, 69, 96, 0.45)',
          boxShadow: '0 24px 60px rgba(0,0,0,0.65), 0 0 40px rgba(157, 78, 221, 0.12)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '18px' }}>
          <h3
            id="sr-demo-dice-title"
            style={{ color: '#e94560', fontFamily: 'Cinzel, serif', margin: 0, fontSize: '1.35rem' }}
          >
            Dice roller <span style={{ color: '#64748b', fontSize: '12px', fontWeight: 400 }}>(demo)</span>
          </h3>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '6px 12px',
              background: 'rgba(15, 23, 41, 0.9)',
              border: '1px solid #2a2a4e',
              borderRadius: '8px',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '13px',
            }}
          >
            Close
          </button>
        </div>
        <p style={{ color: '#94a3b8', fontSize: '14px', marginTop: 0, marginBottom: '18px', lineHeight: 1.5 }}>
          Same pool / difficulty / specialty flow as in play. Rolls run in your browser only — no chronicle API call.
        </p>

        <div style={{ marginBottom: '14px' }}>
          <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '6px', fontSize: '14px' }}>Pool (d10s)</label>
          <input
            type="number"
            min="1"
            max="20"
            value={poolSize}
            onChange={(e) => setPoolSize(parseInt(e.target.value, 10) || 1)}
            style={{
              width: '100%',
              padding: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '16px',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <div style={{ marginBottom: '14px' }}>
          <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '6px', fontSize: '14px' }}>Difficulty</label>
          <input
            type="number"
            min="2"
            max="10"
            value={difficulty}
            onChange={(e) => setDifficulty(parseInt(e.target.value, 10) || 6)}
            style={{
              width: '100%',
              padding: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '16px',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <label style={{ color: '#b5b5c3', display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={specialty}
            onChange={(e) => setSpecialty(e.target.checked)}
          />
          Specialty (10s add an extra success)
        </label>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '6px', fontSize: '14px' }}>Action</label>
          <input
            type="text"
            value={actionDesc}
            onChange={(e) => setActionDesc(e.target.value)}
            style={{
              width: '100%',
              padding: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '8px',
              color: '#e2e8f0',
              fontSize: '14px',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <button
          type="button"
          onClick={handleRoll}
          disabled={rolling}
          style={{
            width: '100%',
            padding: '14px',
            background: rolling ? '#4a4a5e' : 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '10px',
            cursor: rolling ? 'not-allowed' : 'pointer',
            fontWeight: 'bold',
            fontSize: '16px',
            fontFamily: 'Cinzel, serif',
            boxShadow: rolling ? 'none' : '0 4px 20px rgba(233, 69, 96, 0.35)',
          }}
        >
          {rolling ? 'Rolling…' : 'Roll dice'}
        </button>

        {lastRoll && (
          <div
            style={{
              marginTop: '20px',
              padding: '16px',
              background: '#0f1729',
              border: lastRoll.is_botch
                ? '2px solid #991b1b'
                : lastRoll.is_critical
                  ? '2px solid #ca8a04'
                  : '2px solid #2a2a4e',
              borderRadius: '10px',
            }}
          >
            <div style={{ color: '#94a3b8', marginBottom: '10px', fontSize: '13px' }}>{actionDesc || 'Roll'}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
              {lastRoll.results.map((die, idx) => (
                <span
                  key={idx}
                  style={{
                    padding: '6px 12px',
                    background:
                      die === 1 ? '#7f1d1d' : die === 10 ? '#a16207' : die >= lastRoll.difficulty ? '#14532d' : '#475569',
                    color: 'white',
                    borderRadius: '6px',
                    fontWeight: 'bold',
                    fontSize: '15px',
                  }}
                >
                  {die}
                </span>
              ))}
            </div>
            <div
              style={{
                color: lastRoll.is_botch ? '#fca5a5' : lastRoll.is_critical ? '#fde047' : '#4ade80',
                fontWeight: 'bold',
                fontSize: '16px',
                fontFamily: 'Crimson Text, serif',
              }}
            >
              {lastRoll.message}
            </div>
          </div>
        )}
      </GothicBox>
      </div>
    </div>
  );
}

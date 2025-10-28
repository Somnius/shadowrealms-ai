import React, { useState } from 'react';

function DiceRoller({ campaignId, characterId, locationId, onRollComplete }) {
  const [poolSize, setPoolSize] = useState(5);
  const [difficulty, setDifficulty] = useState(6);
  const [specialty, setSpecialty] = useState(false);
  const [actionDesc, setActionDesc] = useState('');
  const [rolling, setRolling] = useState(false);
  const [lastRoll, setLastRoll] = useState(null);

  const handleRoll = async () => {
    if (poolSize < 1) return;
    
    setRolling(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/campaigns/${campaignId}/roll`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          pool_size: poolSize,
          difficulty: difficulty,
          specialty: specialty,
          character_id: characterId,
          action_description: actionDesc || 'Manual roll',
          location_id: locationId
        })
      });
      
      const data = await response.json();
      setLastRoll(data.roll_result);
      
      if (onRollComplete) {
        onRollComplete(data);
      }
    } catch (error) {
      console.error('Roll error:', error);
    } finally {
      setRolling(false);
    }
  };

  return (
    <div style={{
      background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
      border: '2px solid #2a2a4e',
      borderRadius: '10px',
      padding: '20px',
      marginBottom: '20px'
    }}>
      <h3 style={{ color: '#e94560', fontFamily: 'Cinzel, serif', marginBottom: '15px' }}>
        🎲 Dice Roller
      </h3>
      
      <div style={{ marginBottom: '15px' }}>
        <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '5px' }}>
          Dice Pool (d10s):
        </label>
        <input
          type="number"
          min="1"
          max="20"
          value={poolSize}
          onChange={(e) => setPoolSize(parseInt(e.target.value))}
          style={{
            width: '100%',
            padding: '8px',
            background: '#0f1729',
            border: '1px solid #2a2a4e',
            borderRadius: '5px',
            color: '#d0d0e0',
            fontSize: '16px'
          }}
        />
      </div>

      <div style={{ marginBottom: '15px' }}>
        <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '5px' }}>
          Difficulty (target number):
        </label>
        <input
          type="number"
          min="2"
          max="10"
          value={difficulty}
          onChange={(e) => setDifficulty(parseInt(e.target.value))}
          style={{
            width: '100%',
            padding: '8px',
            background: '#0f1729',
            border: '1px solid #2a2a4e',
            borderRadius: '5px',
            color: '#d0d0e0',
            fontSize: '16px'
          }}
        />
      </div>

      <div style={{ marginBottom: '15px' }}>
        <label style={{ color: '#b5b5c3', display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={specialty}
            onChange={(e) => setSpecialty(e.target.checked)}
            style={{ marginRight: '8px' }}
          />
          Specialty (10s count as 2 successes)
        </label>
      </div>

      <div style={{ marginBottom: '15px' }}>
        <label style={{ color: '#b5b5c3', display: 'block', marginBottom: '5px' }}>
          Action Description:
        </label>
        <input
          type="text"
          value={actionDesc}
          onChange={(e) => setActionDesc(e.target.value)}
          placeholder="e.g., Perception + Alertness"
          style={{
            width: '100%',
            padding: '8px',
            background: '#0f1729',
            border: '1px solid #2a2a4e',
            borderRadius: '5px',
            color: '#d0d0e0',
            fontSize: '14px'
          }}
        />
      </div>

      <button
        onClick={handleRoll}
        disabled={rolling}
        style={{
          width: '100%',
          padding: '12px',
          background: rolling ? '#555' : 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          cursor: rolling ? 'not-allowed' : 'pointer',
          fontWeight: 'bold',
          fontSize: '16px',
          fontFamily: 'Cinzel, serif'
        }}
      >
        {rolling ? 'Rolling...' : '🎲 Roll Dice'}
      </button>

      {lastRoll && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          background: '#0f1729',
          border: lastRoll.is_botch ? '2px solid #8b0000' : lastRoll.is_critical ? '2px solid #ffd700' : '2px solid #2a2a4e',
          borderRadius: '8px'
        }}>
          <div style={{ color: '#b5b5c3', marginBottom: '10px' }}>
            <strong>Results:</strong>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '10px' }}>
            {lastRoll.results.map((die, idx) => (
              <span key={idx} style={{
                padding: '5px 10px',
                background: die === 1 ? '#8b0000' : die === 10 ? '#ffd700' : die >= difficulty ? '#2d7a3e' : '#555',
                color: 'white',
                borderRadius: '5px',
                fontWeight: 'bold',
                fontSize: '16px'
              }}>
                {die}
              </span>
            ))}
          </div>
          <div style={{ color: lastRoll.is_botch ? '#ff4444' : lastRoll.is_critical ? '#ffd700' : '#4ade80', fontWeight: 'bold', fontSize: '16px' }}>
            {lastRoll.message}
          </div>
        </div>
      )}
    </div>
  );
}

export default DiceRoller;


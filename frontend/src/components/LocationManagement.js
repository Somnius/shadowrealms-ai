import React, { useState, useEffect } from 'react';

function LocationManagement({ campaignId, isAdmin }) {
  const [locations, setLocations] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newLocation, setNewLocation] = useState({ name: '', type: 'custom', description: '' });

  useEffect(() => {
    fetchLocations();
  }, [campaignId]);

  const fetchLocations = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/campaigns/${campaignId}/locations`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setLocations(data);
    } catch (error) {
      console.error('Error fetching locations:', error);
    }
  };

  const handleCreate = async () => {
    try {
      const token = localStorage.getItem('token');
      await fetch(`/api/campaigns/${campaignId}/locations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newLocation)
      });
      setNewLocation({ name: '', type: 'custom', description: '' });
      setShowCreate(false);
      fetchLocations();
    } catch (error) {
      console.error('Error creating location:', error);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ color: '#e94560', fontFamily: 'Cinzel, serif' }}>📍 Locations</h2>
        {isAdmin && (
          <button onClick={() => setShowCreate(!showCreate)} style={{
            padding: '10px 20px',
            background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontFamily: 'Cinzel, serif'
          }}>
            + New Location
          </button>
        )}
      </div>

      {showCreate && (
        <div style={{
          background: '#16213e',
          border: '2px solid #2a2a4e',
          borderRadius: '10px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <h3 style={{ color: '#e94560', marginBottom: '15px' }}>Create Location</h3>
          <input
            placeholder="Location Name"
            value={newLocation.name}
            onChange={(e) => setNewLocation({...newLocation, name: e.target.value})}
            style={{
              width: '100%',
              padding: '10px',
              marginBottom: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '5px',
              color: '#d0d0e0'
            }}
          />
          <select
            value={newLocation.type}
            onChange={(e) => setNewLocation({...newLocation, type: e.target.value})}
            style={{
              width: '100%',
              padding: '10px',
              marginBottom: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '5px',
              color: '#d0d0e0'
            }}
          >
            <option value="custom">Custom</option>
            <option value="tavern">Tavern</option>
            <option value="dungeon">Dungeon</option>
            <option value="city">City</option>
            <option value="temple">Temple</option>
          </select>
          <textarea
            placeholder="Description"
            value={newLocation.description}
            onChange={(e) => setNewLocation({...newLocation, description: e.target.value})}
            style={{
              width: '100%',
              padding: '10px',
              marginBottom: '10px',
              background: '#0f1729',
              border: '1px solid #2a2a4e',
              borderRadius: '5px',
              color: '#d0d0e0',
              minHeight: '80px'
            }}
          />
          <button onClick={handleCreate} style={{
            padding: '10px 20px',
            background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            marginRight: '10px'
          }}>
            Create
          </button>
          <button onClick={() => setShowCreate(false)} style={{
            padding: '10px 20px',
            background: '#555',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer'
          }}>
            Cancel
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
        {locations.map(loc => (
          <div key={loc.id} style={{
            background: '#16213e',
            border: loc.type === 'ooc' ? '2px solid #9d4edd' : '2px solid #2a2a4e',
            borderRadius: '10px',
            padding: '20px'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '10px' }}>
              {loc.type === 'ooc' ? '💬' : '📍'} {loc.name}
            </h3>
            <p style={{ color: '#b5b5c3', fontSize: '14px', marginBottom: '10px' }}>
              {loc.description || 'No description'}
            </p>
            <div style={{ color: '#8b8b9f', fontSize: '12px' }}>
              Type: {loc.type} | Characters: {loc.character_count || 0}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default LocationManagement;


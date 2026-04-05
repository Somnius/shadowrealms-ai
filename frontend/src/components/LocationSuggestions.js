import React, { useState, useEffect } from 'react';

function LocationSuggestions({ campaignId, settingDescription, onComplete, onSkip }) {
  const [suggestions, setSuggestions] = useState([]);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(true); // Start as true since we fetch immediately
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;

    const run = async () => {
      if (!campaignId) {
        console.error('❌ Cannot fetch suggestions: campaignId is undefined');
        setError('⚠️ Campaign ID is missing. Please try creating the campaign again.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem('token');
        console.log(`🎲 Requesting AI location suggestions for campaign ${campaignId}...`);

        const response = await fetch(`/api/campaigns/${campaignId}/locations/suggest`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ setting_description: settingDescription }),
        });

        const data = await response.json();
        if (!alive) return;

        if (!response.ok) {
          setError(data.error || `Server error: ${response.status}`);
          setSuggestions([]);
          setSelected({});
          return;
        }

        console.log(`✅ Received ${data.suggestions?.length || 0} location suggestions`);
        setError(null);

        const locationSuggestions = data.suggestions || [];
        setSuggestions(locationSuggestions);

        if (locationSuggestions.length === 0) {
          setError('AI returned no suggestions. You can add locations manually later.');
        }

        const preSelected = {};
        locationSuggestions.forEach((_, idx) => {
          preSelected[idx] = true;
        });
        setSelected(preSelected);
      } catch (err) {
        if (!alive) return;
        console.error('❌ Error fetching suggestions:', err);
        setError(
          '⚠️ AI service unavailable. Check the backend can reach LM Studio (same host as the API — use host.docker.internal or your LAN IP, not localhost:1234 from inside Docker unless port-forwarded).'
        );
        setSuggestions([]);
        setSelected({});
      } finally {
        if (alive) setLoading(false);
      }
    };

    run();
    return () => {
      alive = false;
    };
  }, [campaignId, settingDescription]);

  const handleToggle = (index) => {
    setSelected(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleCreate = async () => {
    if (!campaignId) {
      console.error('❌ Cannot create locations: campaignId is undefined');
      setError('⚠️ Campaign ID is missing. Please try creating the campaign again.');
      return;
    }
    
    const selectedLocations = suggestions.filter((_, idx) => selected[idx]);
    
    if (selectedLocations.length === 0) {
      setError('⚠️ Please select at least one location');
      return;
    }
    
    setError(null); // Clear any previous errors
    
    setCreating(true);
    try {
      const token = localStorage.getItem('token');
      console.log(`🎲 Creating ${selectedLocations.length} locations for campaign ${campaignId}...`);
      
      const response = await fetch(`/api/campaigns/${campaignId}/locations/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ locations: selectedLocations })
      });
      
      if (response.ok) {
        const data = await response.json();
        const n = (data.location_ids && data.location_ids.length) || data.created?.length || 0;
        console.log(`✅ Successfully created ${n} locations:`, data);
        if (onComplete) onComplete();
      } else {
        const errorData = await response.json();
        console.error('❌ Failed to create locations:', errorData);
        setError(`❌ Failed to create locations: ${errorData.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('❌ Error creating locations:', error);
      setError('❌ Failed to create locations. Please try again.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{
      position: 'relative',
      background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
      border: '2px solid #2a2a4e',
      borderRadius: '15px',
      padding: '30px',
      marginTop: '20px',
      minHeight: loading ? 'min(72vh, 620px)' : undefined,
    }}>
      {loading && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 20,
            borderRadius: '13px',
            background: '#0a0e18',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '48px 36px 56px',
            textAlign: 'center',
            boxShadow: 'inset 0 0 80px rgba(157, 78, 221, 0.08)',
          }}
        >
          <div style={{
            fontSize: '64px',
            marginBottom: '25px',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          }}
          >
            🎲
          </div>
          <h3 style={{
            color: '#e94560',
            fontFamily: 'Cinzel, serif',
            marginBottom: '15px',
            fontSize: '26px',
          }}
          >
            Generating location ideas…
          </h3>
          <p style={{
            color: '#b5b5c3',
            fontFamily: 'Crimson Text, serif',
            fontSize: '16px',
            marginBottom: '20px',
            lineHeight: '1.6',
            maxWidth: '420px',
          }}
          >
            The AI is reading your setting and drafting atmospheric locations.
            This can take from a few seconds up to a couple of minutes depending on your model.
          </p>
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '8px',
            marginTop: '12px',
          }}
          >
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  background: '#9d4edd',
                  animation: `bounce 1.4s ease-in-out ${i * 0.16}s infinite`,
                  boxShadow: '0 0 10px rgba(157, 78, 221, 0.5)',
                }}
              />
            ))}
          </div>
          <p style={{
            color: '#8b8b9f',
            fontFamily: 'Crimson Text, serif',
            fontSize: '13px',
            marginTop: '28px',
            marginBottom: 0,
            fontStyle: 'italic',
            lineHeight: 1.5,
          }}
          >
            Please wait — the list will appear below when ready.
          </p>
        </div>
      )}
      <div style={{ filter: loading ? 'blur(6px)' : 'none', opacity: loading ? 0.25 : 1, pointerEvents: loading ? 'none' : 'auto', userSelect: loading ? 'none' : 'auto' }}>
      <h2 style={{
        color: '#e94560',
        fontFamily: 'Cinzel, serif',
        marginBottom: '10px',
        fontSize: '24px'
      }}>
        🏰 Suggested locations
      </h2>

      {error && (
        <div
          style={{
            background: 'rgba(255, 152, 0, 0.1)',
            border: '2px solid #ff9800',
            borderRadius: '8px',
            padding: '15px',
            marginBottom: '20px',
          }}
        >
          <p
            style={{
              color: '#ffb74d',
              fontFamily: 'Crimson Text, serif',
              fontSize: '15px',
              margin: 0,
            }}
          >
            ⚠️ {error}
          </p>
        </div>
      )}
      
      <p style={{
        color: '#b5b5c3',
        fontFamily: 'Crimson Text, serif',
        marginBottom: '25px',
        fontSize: '16px'
      }}>
        Select the locations you want to create for your campaign. You can add more later.
      </p>

      <div style={{
        display: 'grid',
        gap: '15px',
        marginBottom: '25px'
      }}>
        {suggestions.map((loc, idx) => (
          <div
            key={idx}
            onClick={() => handleToggle(idx)}
            style={{
              background: selected[idx] ? 'rgba(233, 69, 96, 0.15)' : '#0f1729',
              border: selected[idx] ? '2px solid #e94560' : '2px solid #2a2a4e',
              borderRadius: '10px',
              padding: '20px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'start',
              gap: '15px'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = 'translateX(5px)';
              e.currentTarget.style.boxShadow = selected[idx] 
                ? '0 4px 20px rgba(233, 69, 96, 0.4)'
                : '0 4px 20px rgba(42, 42, 78, 0.4)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = 'translateX(0)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <div style={{
              width: '24px',
              height: '24px',
              border: '2px solid ' + (selected[idx] ? '#e94560' : '#555'),
              borderRadius: '5px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              background: selected[idx] ? '#e94560' : 'transparent',
              marginTop: '2px'
            }}>
              {selected[idx] && <span style={{ color: 'white', fontSize: '16px' }}>✓</span>}
            </div>
            
            <div style={{ flex: 1 }}>
              <h3 style={{
                color: selected[idx] ? '#e94560' : '#d0d0e0',
                fontFamily: 'Cinzel, serif',
                fontSize: '18px',
                marginBottom: '8px'
              }}>
                📍 {loc.name}
              </h3>
              <div style={{
                display: 'inline-block',
                padding: '4px 12px',
                background: 'rgba(157, 78, 221, 0.2)',
                border: '1px solid #9d4edd',
                borderRadius: '12px',
                fontSize: '12px',
                color: '#9d4edd',
                fontFamily: 'Cinzel, serif',
                marginBottom: '10px',
                textTransform: 'capitalize'
              }}>
                {loc.type}
              </div>
              <p style={{
                color: '#b5b5c3',
                fontFamily: 'Crimson Text, serif',
                fontSize: '15px',
                lineHeight: '1.6',
                margin: 0
              }}>
                {loc.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div style={{
        display: 'flex',
        gap: '15px',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ color: '#8b8b9f', fontSize: '14px' }}>
          {Object.values(selected).filter(Boolean).length} of {suggestions.length} selected
        </div>
        
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={onSkip}
            disabled={creating}
            style={{
              padding: '12px 24px',
              background: '#40444b',
              color: '#dcddde',
              border: '2px solid #6c757d',
              borderRadius: '8px',
              cursor: creating ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              fontSize: '14px',
              fontFamily: 'Cinzel, serif',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => !creating && (e.target.style.background = '#6c757d')}
            onMouseOut={(e) => !creating && (e.target.style.background = '#40444b')}
          >
            Skip for Now
          </button>
          
          <button
            onClick={handleCreate}
            disabled={creating || Object.values(selected).filter(Boolean).length === 0}
            style={{
              padding: '12px 30px',
              background: creating ? '#555' : 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: creating ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              fontSize: '14px',
              fontFamily: 'Cinzel, serif',
              boxShadow: creating ? 'none' : '0 4px 15px rgba(233, 69, 96, 0.4)',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => !creating && (e.target.style.transform = 'translateY(-2px)')}
            onMouseOut={(e) => !creating && (e.target.style.transform = 'translateY(0)')}
          >
            {creating ? 'Creating...' : `Create ${Object.values(selected).filter(Boolean).length} Locations`}
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}

export default LocationSuggestions;


import React, { useState, useEffect } from 'react';
import { t } from '../i18n';
import { AiSigil, Glyph } from '../design';

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
        setError(t('locations:error.noCampaign', 'The chronicle ID is missing. Please try creating the chronicle again.'));
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
          setError(data.error || t('locations:error.server', 'Server error: {{status}}', { status: response.status }));
          setSuggestions([]);
          setSelected({});
          return;
        }

        console.log(`✅ Received ${data.suggestions?.length || 0} location suggestions`);
        setError(null);

        const locationSuggestions = data.suggestions || [];
        setSuggestions(locationSuggestions);

        if (locationSuggestions.length === 0) {
          setError(t('locations:error.empty', 'The AI returned no suggestions. You can add locations manually later.'));
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
      setError(t('locations:error.noCampaign', 'The chronicle ID is missing. Please try creating the chronicle again.'));
      return;
    }
    
    const selectedLocations = suggestions.filter((_, idx) => selected[idx]);
    
    if (selectedLocations.length === 0) {
      setError(t('locations:error.noneSelected', 'Please select at least one location.'));
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
        setError(t('locations:error.createFailedWith', 'Failed to create locations: {{error}}', { error: errorData.error || t('locations:error.unknown', 'Unknown error') }));
      }
    } catch (error) {
      console.error('❌ Error creating locations:', error);
      setError(t('locations:error.createFailed', 'Failed to create locations. Please try again.'));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{
      position: 'relative',
      background: 'linear-gradient(135deg, var(--sr-night-800) 0%, var(--sr-night-850) 100%)',
      border: '2px solid var(--sr-night-700)',
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
            background: 'var(--sr-night-950)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '48px 36px 56px',
            textAlign: 'center',
            boxShadow: 'inset 0 0 80px rgba(157, 78, 221, 0.08)',
          }}
        >
          <div style={{ marginBottom: '25px', color: 'var(--sr-arcane-300)' }}>
            <AiSigil size={64} className="sr-glyph--essential" />
          </div>
          <h3 style={{
            color: 'var(--sr-blood-500)',
            fontFamily: 'var(--sr-font-display)',
            marginBottom: '15px',
            fontSize: '26px',
          }}
          >
            {t('locations:loading.title', 'Generating location ideas…')}
          </h3>
          <p style={{
            color: 'var(--sr-bone-300)',
            fontFamily: 'var(--sr-font-body)',
            fontSize: '16px',
            marginBottom: '20px',
            lineHeight: '1.6',
            maxWidth: '420px',
          }}
          >
            {t('locations:loading.body', 'The AI is reading your setting and drafting atmospheric locations. This can take from a few seconds up to a couple of minutes depending on your model.')}
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
                  background: 'var(--sr-arcane-500)',
                  animation: `bounce 1.4s ease-in-out ${i * 0.16}s infinite`,
                  boxShadow: '0 0 10px rgba(157, 78, 221, 0.5)',
                }}
              />
            ))}
          </div>
          <p style={{
            color: 'var(--sr-bone-500)',
            fontFamily: 'var(--sr-font-body)',
            fontSize: '13px',
            marginTop: '28px',
            marginBottom: 0,
            fontStyle: 'italic',
            lineHeight: 1.5,
          }}
          >
            {t('locations:loading.wait', 'Please wait — the list will appear below when ready.')}
          </p>
        </div>
      )}
      <div style={{ filter: loading ? 'blur(6px)' : 'none', opacity: loading ? 0.25 : 1, pointerEvents: loading ? 'none' : 'auto', userSelect: loading ? 'none' : 'auto' }}>
      <h2 style={{
        color: 'var(--sr-blood-500)',
        fontFamily: 'var(--sr-font-display)',
        marginBottom: '10px',
        fontSize: '24px'
      }}>
        <Glyph name="room-elysium" size={24} style={{ verticalAlign: '-3px', marginRight: '8px' }} />
        {t('locations:title', 'Suggested locations')}
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
              fontFamily: 'var(--sr-font-body)',
              fontSize: '15px',
              margin: 0,
            }}
          >
            <Glyph name="warning" size={16} style={{ verticalAlign: '-3px', marginRight: '6px' }} />
            {error}
          </p>
        </div>
      )}
      
      <p style={{
        color: 'var(--sr-bone-300)',
        fontFamily: 'var(--sr-font-body)',
        marginBottom: '25px',
        fontSize: '16px'
      }}>
        {t('locations:intro', 'Select the locations you want to create for your chronicle. You can add more later.')}
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
              background: selected[idx] ? 'rgba(233, 69, 96, 0.15)' : 'var(--sr-night-850)',
              border: selected[idx] ? '2px solid var(--sr-blood-500)' : '2px solid var(--sr-night-700)',
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
              border: '2px solid ' + (selected[idx] ? 'var(--sr-blood-500)' : '#555'),
              borderRadius: '5px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              background: selected[idx] ? 'var(--sr-blood-500)' : 'transparent',
              marginTop: '2px'
            }}>
              {selected[idx] && <Glyph name="check" size={16} strokeWidth={2.4} style={{ color: 'white' }} />}
            </div>
            
            <div style={{ flex: 1 }}>
              <h3 style={{
                color: selected[idx] ? 'var(--sr-blood-500)' : 'var(--sr-bone-100)',
                fontFamily: 'var(--sr-font-display)',
                fontSize: '18px',
                marginBottom: '8px'
              }}>
                <Glyph name={/haven|home/i.test(String(loc.type || '')) ? 'room-haven' : /elysium/i.test(String(loc.type || '')) ? 'room-elysium' : 'room-street'} size={18} style={{ verticalAlign: '-3px', marginRight: '6px' }} />
                {loc.name}
              </h3>
              <div style={{
                display: 'inline-block',
                padding: '4px 12px',
                background: 'rgba(157, 78, 221, 0.2)',
                border: '1px solid var(--sr-arcane-500)',
                borderRadius: '12px',
                fontSize: '12px',
                color: 'var(--sr-arcane-500)',
                fontFamily: 'var(--sr-font-display)',
                marginBottom: '10px',
                textTransform: 'capitalize'
              }}>
                {loc.type}
              </div>
              <p style={{
                color: 'var(--sr-bone-300)',
                fontFamily: 'var(--sr-font-body)',
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
        <div style={{ color: 'var(--sr-bone-500)', fontSize: '14px' }}>
          {t('locations:selected', '{{n}} of {{total}} selected', { n: Object.values(selected).filter(Boolean).length, total: suggestions.length })}
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
              fontFamily: 'var(--sr-font-display)',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => !creating && (e.target.style.background = '#6c757d')}
            onMouseOut={(e) => !creating && (e.target.style.background = '#40444b')}
          >
            {t('locations:skip', 'Skip for now')}
          </button>
          
          <button
            onClick={handleCreate}
            disabled={creating || Object.values(selected).filter(Boolean).length === 0}
            style={{
              padding: '12px 30px',
              background: creating ? '#555' : 'linear-gradient(135deg, var(--sr-blood-500) 0%, var(--sr-blood-700) 100%)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: creating ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              fontSize: '14px',
              fontFamily: 'var(--sr-font-display)',
              boxShadow: creating ? 'none' : '0 4px 15px rgba(233, 69, 96, 0.4)',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => !creating && (e.target.style.transform = 'translateY(-2px)')}
            onMouseOut={(e) => !creating && (e.target.style.transform = 'translateY(0)')}
          >
            {creating
              ? t('locations:creating', 'Creating…')
              : t('locations:create', { one: 'Create {{count}} location', other: 'Create {{count}} locations' }, { count: Object.values(selected).filter(Boolean).length })}
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}

export default LocationSuggestions;


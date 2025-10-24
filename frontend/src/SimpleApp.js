import React, { useState, useEffect } from 'react';
import AdminPage from './pages/AdminPage';
import GothicShowcase from './pages/GothicShowcase';
import { GothicBox } from './components/GothicDecorations';

const API_URL = '/api'; // Use relative URL through nginx proxy

function SimpleApp() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [showGothicShowcase, setShowGothicShowcase] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [locations, setLocations] = useState([]);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [character, setCharacter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Load user data on mount
  useEffect(() => {
    if (token) {
      fetchUserData();
    }
  }, [token]);

  // Fetch user data
  const fetchUserData = async () => {
    try {
      const response = await fetch(`${API_URL}/users/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    }
  };

  // Fetch campaigns
  const fetchCampaigns = async () => {
    try {
      const response = await fetch(`${API_URL}/campaigns/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        // Backend returns array directly, not wrapped in object
        setCampaigns(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('Failed to load campaigns:', err);
      setError('Failed to load campaigns');
    }
  };

  // Load campaigns when dashboard is shown
  useEffect(() => {
    if (currentPage === 'dashboard' && token) {
      fetchCampaigns();
    }
  }, [currentPage, token]);

  // Handle login
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const formData = new FormData(e.target);
    const credentials = {
      username: formData.get('username'),
      password: formData.get('password')
    };

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.access_token);
        localStorage.setItem('token', data.access_token);
        setUser(data.user);
        setCurrentPage('dashboard');
        setError('');
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle register
  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const formData = new FormData(e.target);
    const userData = {
      username: formData.get('username'),
      email: formData.get('email'),
      password: formData.get('password'),
      invite_code: formData.get('invite_code')
    };

    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.access_token);
        localStorage.setItem('token', data.access_token);
        setUser(data.user);
        setCurrentPage('dashboard');
        setError('');
      } else {
        setError(data.error || 'Registration failed');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle logout
  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    setUser(null);
    setCurrentPage('dashboard');
    setCampaigns([]);
    setSelectedCampaign(null);
  };

  // Handle create campaign
  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const formData = new FormData(e.target);
    const campaignData = {
      name: formData.get('campaignName'),
      description: formData.get('description'),
      game_system: formData.get('game_system')
    };

    try {
      const response = await fetch(`${API_URL}/campaigns`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(campaignData)
      });

      const data = await response.json();

      if (response.ok) {
        alert('✅ Campaign created successfully!');
        await fetchCampaigns();
        setCurrentPage('dashboard');
        setError('');
        e.target.reset();
      } else {
        setError(data.error || 'Failed to create campaign');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Enter campaign (load locations and switch to chat view)
  const enterCampaign = (campaign) => {
    setSelectedCampaign(campaign);
    // For now, create default locations
    const defaultLocations = [
      { id: 'ooc', name: '💬 OOC Chat', type: 'ooc' },
      { id: 'elysium', name: '🏛️ Elysium', type: 'location' },
      { id: 'downtown', name: '🌆 Downtown', type: 'location' },
      { id: 'haven', name: '🏠 Haven', type: 'location' }
    ];
    setLocations(defaultLocations);
    setCurrentLocation(defaultLocations[0]);
    setMessages([]);
    setCurrentPage('chat');
  };

  // Handle send message
  const handleSendMessage = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const messageText = formData.get('message');
    
    if (!messageText.trim()) return;

    setLoading(true);
    setError('');

    // Add user message to UI immediately
    const userMessage = {
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
      location: currentLocation.id
    };
    setMessages(prev => [...prev, userMessage]);
    e.target.reset();

    try {
      const response = await fetch(`${API_URL}/ai/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: messageText,
          campaign_id: selectedCampaign.id,
          location: currentLocation.id
        })
      });

      const data = await response.json();

      if (response.ok) {
        // Add AI response to messages
        const aiMessage = {
          role: 'assistant',
          content: data.response || data.message || 'No response',
          timestamp: new Date().toISOString(),
          location: currentLocation.id
        };
        setMessages(prev => [...prev, aiMessage]);
      } else {
        setError(data.error || 'Failed to get AI response');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Change location
  const changeLocation = (location) => {
    setCurrentLocation(location);
    // In a real app, load messages for this location
    setMessages([]);
  };

  // Get campaign theme based on game system
  const getCampaignTheme = (campaign) => {
    if (!campaign || !campaign.game_system) return 'none';
    const gameSystem = campaign.game_system.toLowerCase();
    
    if (gameSystem.includes('vampire')) return 'vampire';
    if (gameSystem.includes('mage')) return 'mage';
    if (gameSystem.includes('werewolf')) return 'werewolf';
    
    return 'none';
  };

  // ========== RENDER FUNCTIONS ==========

  // Render login page
  const renderLogin = () => (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #0f0f1e 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
    }}>
      {/* Logo and Title */}
      <div style={{ textAlign: 'center', marginBottom: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <img 
          src="https://github.com/Somnius/shadowrealms-ai/raw/main/assets/logos/logo-3.png" 
          alt="ShadowRealms AI" 
          style={{ 
            width: '240px', 
            height: 'auto', 
            marginBottom: '20px',
            filter: 'drop-shadow(0 0 20px rgba(233, 69, 96, 0.5))'
          }}
        />
        <h1 style={{ color: '#e94560', marginBottom: '10px', fontSize: '32px', fontWeight: 'bold' }}>
          ShadowRealms AI
        </h1>
        <p style={{ color: '#8b8b9f', marginBottom: '0', fontSize: '16px' }}>
          Immersive Tabletop RPG with AI
        </p>
        
        {/* Gothic Theme Preview Button */}
        <button
          onClick={() => setShowGothicShowcase(true)}
          style={{
            marginTop: '20px',
            padding: '10px 25px',
            background: 'linear-gradient(135deg, #9d4edd 0%, #5a0099 100%)',
            border: '2px solid #9d4edd',
            color: 'white',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold',
            boxShadow: '0 0 20px rgba(157, 78, 221, 0.4)',
            transition: 'all 0.3s'
          }}
        >
          💀 Preview Gothic Horror Theme 💀
        </button>
      </div>

      {/* Login and Register Side by Side */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
        gap: '30px',
        width: '100%',
        maxWidth: '950px'
      }}>

        {/* Login Box with Blood Theme */}
        <GothicBox theme="vampire" style={{
          background: '#16213e',
          padding: '35px',
          borderRadius: '15px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          border: '1px solid #2a2a4e'
        }}>
          <h2 style={{ fontSize: '24px', color: '#e94560', marginBottom: '25px', textAlign: 'center', fontFamily: 'Cinzel, serif' }}>
            Login
          </h2>
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Username:
              </label>
              <input
                type="text"
                name="username"
                required
                placeholder="Enter your username"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Password:
              </label>
              <input
                type="password"
                name="password"
                required
                placeholder="Enter your password"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px',
                background: loading ? '#4a4a5e' : '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                marginBottom: '15px',
                boxShadow: loading ? 'none' : '0 4px 15px rgba(233, 69, 96, 0.3)'
              }}
            >
              {loading ? 'Logging in...' : 'LOGIN'}
            </button>
          </form>
        </GothicBox>

        {/* Register Box with Magic Theme */}
        <GothicBox theme="mage" style={{
          background: '#16213e',
          padding: '35px',
          borderRadius: '15px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          border: '1px solid #2a2a4e'
        }}>
          <h2 style={{ fontSize: '24px', color: '#9d4edd', marginBottom: '25px', textAlign: 'center', fontFamily: 'Cinzel, serif' }}>
            Register
          </h2>
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Username:
              </label>
              <input
                type="text"
                name="username"
                required
                placeholder="Choose a username"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Email:
              </label>
              <input
                type="email"
                name="email"
                required
                placeholder="Enter your email"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Password:
              </label>
              <input
                type="password"
                name="password"
                required
                placeholder="Choose a password"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Invite Code: <span style={{ color: '#e94560' }}>*</span>
              </label>
              <input
                type="text"
                name="invite_code"
                required
                placeholder="Enter your invite code"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
              <small style={{ color: '#8b8b9f', fontSize: '12px', marginTop: '5px', display: 'block' }}>
                Required: Get an invite code from the admin
              </small>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px',
                background: loading ? '#4a4a5e' : '#9d4edd',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: loading ? 'none' : '0 4px 15px rgba(157, 78, 221, 0.4)',
                fontFamily: 'Cinzel, serif'
              }}
            >
              {loading ? 'Creating account...' : 'REGISTER'}
            </button>
          </form>
        </GothicBox>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{
          marginTop: '30px',
          padding: '15px 25px',
          background: 'rgba(233, 69, 96, 0.1)',
          border: '2px solid #e94560',
          borderRadius: '8px',
          color: '#e94560',
          fontWeight: '500',
          maxWidth: '950px',
          width: '100%',
          textAlign: 'center'
        }}>
          ⚠️ {error}
        </div>
      )}
    </div>
  );

  // Render dashboard
  const renderDashboard = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e' }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
        padding: '20px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #2a2a4e'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <img 
            src="https://github.com/Somnius/shadowrealms-ai/raw/main/assets/logos/logo-3.png" 
            alt="ShadowRealms AI" 
            style={{ width: '50px', height: 'auto' }}
          />
          <h1 style={{ color: '#e94560', margin: 0 }}>ShadowRealms AI</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span style={{ color: '#b5b5c3', fontWeight: '500' }}>👤 {user?.username}</span>
          {user?.role === 'admin' && (
            <button
              onClick={() => setCurrentPage('admin')}
              style={{
                padding: '8px 16px',
                background: 'rgba(233, 69, 96, 0.3)',
                color: '#e94560',
                border: '2px solid #e94560',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: 'bold'
              }}
            >
              👑 Admin Panel
            </button>
          )}
          <button
            onClick={handleLogout}
            style={{
              padding: '8px 16px',
              background: 'rgba(233, 69, 96, 0.2)',
              color: '#e94560',
              border: '2px solid #e94560',
              borderRadius: '5px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            🚪 Logout
          </button>
        </div>
      </div>

      {/* Main content */}
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
          <h2 style={{ color: '#e94560', margin: 0 }}>📚 Your Campaigns</h2>
          <button
            onClick={() => setCurrentPage('createCampaign')}
            style={{
              padding: '10px 20px',
              background: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '16px',
              boxShadow: '0 4px 15px rgba(40, 167, 69, 0.3)'
            }}
          >
            ➕ New Campaign
          </button>
        </div>

        {campaigns.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '60px 20px',
            background: '#16213e',
            borderRadius: '10px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e'
          }}>
            <p style={{ fontSize: '18px', color: '#b5b5c3' }}>
              No campaigns yet. Create your first campaign to begin!
            </p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: '20px'
          }}>
            {campaigns.map(campaign => {
              // Extract first line or truncate description
              const firstLine = campaign.description.split('\n')[0];
              const shortDesc = firstLine.length > 100 
                ? firstLine.substring(0, 100) + '...' 
                : firstLine;
              
              return (
                <div
                  key={campaign.id}
                  style={{
                    background: '#16213e',
                    padding: '25px',
                    borderRadius: '10px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
                    cursor: 'pointer',
                    transition: 'transform 0.2s, border-color 0.2s',
                    border: '2px solid #2a2a4e',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '200px'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.transform = 'translateY(-5px)';
                    e.currentTarget.style.borderColor = '#e94560';
                    e.currentTarget.style.boxShadow = '0 4px 20px rgba(233, 69, 96, 0.3)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.borderColor = '#2a2a4e';
                    e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.5)';
                  }}
                >
                  <div onClick={() => enterCampaign(campaign)}>
                    <h3 style={{ color: '#e94560', marginBottom: '10px', fontSize: '20px' }}>
                      🎲 {campaign.name}
                    </h3>
                    <p style={{ color: '#b5b5c3', marginBottom: '15px', fontSize: '14px', lineHeight: '1.5' }}>
                      {shortDesc}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                    <div style={{
                      flex: 1,
                      padding: '5px 12px',
                      background: 'rgba(233, 69, 96, 0.2)',
                      color: '#e94560',
                      borderRadius: '15px',
                      fontSize: '12px',
                      fontWeight: '600',
                      textAlign: 'center',
                      border: '1px solid #e94560'
                    }}>
                      {campaign.game_system}
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCampaign(campaign);
                        setCurrentPage('campaignDetails');
                      }}
                      style={{
                        padding: '8px 16px',
                        background: 'rgba(233, 69, 96, 0.2)',
                        color: '#e94560',
                        border: '1px solid #e94560',
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600'
                      }}
                    >
                      ⚙️ Settings
                    </button>
                    <button
                      onClick={() => enterCampaign(campaign)}
                      style={{
                        padding: '8px 16px',
                        background: '#28a745',
                        color: 'white',
                        border: 'none',
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600',
                        boxShadow: '0 2px 10px rgba(40, 167, 69, 0.3)'
                      }}
                    >
                      ▶️ Enter
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  // Render campaign details/settings page
  const renderCampaignDetails = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', padding: '20px' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <button
          onClick={() => setCurrentPage('dashboard')}
          style={{
            marginBottom: '20px',
            padding: '10px 20px',
            background: '#16213e',
            border: '2px solid #e94560',
            color: '#e94560',
            borderRadius: '5px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          ← Back to Dashboard
        </button>

        <div style={{
          background: '#16213e',
          padding: '40px',
          borderRadius: '10px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
            <h1 style={{ color: '#e94560', margin: 0 }}>⚙️ Campaign Settings</h1>
            <button
              onClick={() => enterCampaign(selectedCampaign)}
              style={{
                padding: '10px 20px',
                background: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '16px'
              }}
            >
              ▶️ Enter Campaign
            </button>
          </div>

          {/* Campaign Name */}
          <div style={{ marginBottom: '30px', paddingBottom: '20px', borderBottom: '1px solid #eee' }}>
            <h2 style={{ color: '#e94560', fontSize: '24px', marginBottom: '10px' }}>
              {selectedCampaign?.name}
            </h2>
            <div style={{
              display: 'inline-block',
              padding: '5px 15px',
              background: '#e3f2fd',
              color: '#1976d2',
              borderRadius: '15px',
              fontSize: '14px',
              fontWeight: '600'
            }}>
              {selectedCampaign?.game_system}
            </div>
          </div>

          {/* Campaign Description/World Info */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px' }}>
              📖 Campaign World & Setting
            </h3>
            <div style={{
              background: '#0f1729',
              padding: '20px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              whiteSpace: 'pre-wrap',
              lineHeight: '1.6',
              fontSize: '14px',
              color: '#444',
              maxHeight: '400px',
              overflowY: 'auto'
            }}>
              {selectedCampaign?.description}
            </div>
          </div>

          {/* Admin Actions */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px' }}>
              👑 Admin Actions
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <button style={{
                padding: '12px',
                background: '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                ✏️ Edit Campaign Info
              </button>
              <button style={{
                padding: '12px',
                background: '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                👥 Manage Players
              </button>
              <button style={{
                padding: '12px',
                background: '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                🗺️ Manage Locations
              </button>
              <button style={{
                padding: '12px',
                background: '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                📚 Add Rule Books
              </button>
              <button style={{
                padding: '12px',
                background: '#ffc107',
                color: '#e94560',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                💾 Export Campaign
              </button>
              <button style={{
                padding: '12px',
                background: '#dc3545',
                color: 'white',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: '600'
              }}>
                🗑️ Delete Campaign
              </button>
            </div>
          </div>

          {/* Campaign Stats */}
          <div>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px' }}>
              📊 Campaign Statistics
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
              <div style={{ background: '#f0f4ff', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#e94560' }}>0</div>
                <div style={{ fontSize: '14px', color: '#b5b5c3', marginTop: '5px' }}>Active Players</div>
              </div>
              <div style={{ background: '#fff4e6', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ffa726' }}>0</div>
                <div style={{ fontSize: '14px', color: '#b5b5c3', marginTop: '5px' }}>Characters</div>
              </div>
              <div style={{ background: '#e8f5e9', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#66bb6a' }}>0</div>
                <div style={{ fontSize: '14px', color: '#b5b5c3', marginTop: '5px' }}>Locations</div>
              </div>
              <div style={{ background: '#fce4ec', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ec407a' }}>0</div>
                <div style={{ fontSize: '14px', color: '#b5b5c3', marginTop: '5px' }}>Messages</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render create campaign page
  const renderCreateCampaign = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', padding: '20px' }}>
      <div style={{ maxWidth: '700px', margin: '0 auto' }}>
        <button
          onClick={() => setCurrentPage('dashboard')}
          style={{
            marginBottom: '20px',
            padding: '10px 20px',
            background: '#16213e',
            border: '2px solid #e94560',
            color: '#e94560',
            borderRadius: '5px',
            cursor: 'pointer',
            fontWeight: 'bold'
          }}
        >
          ← Back to Dashboard
        </button>

        <div style={{
          background: '#16213e',
          padding: '40px',
          borderRadius: '10px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
        }}>
          <h1 style={{ color: '#e94560', marginBottom: '30px' }}>✨ Create New Campaign</h1>

          <form onSubmit={handleCreateCampaign}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Campaign Name:
              </label>
              <input
                type="text"
                name="campaignName"
                required
                placeholder="Enter campaign name..."
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Description:
              </label>
              <textarea
                name="description"
                rows="5"
                required
                placeholder="Describe your campaign..."
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                  resize: 'vertical'
                }}
              ></textarea>
            </div>

            <div style={{ marginBottom: '30px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Game System:
              </label>
              <select
                name="game_system"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  cursor: 'pointer',
                  boxSizing: 'border-box'
                }}
              >
                <option value="vampire">🧛 Vampire: The Masquerade</option>
                <option value="werewolf">🐺 Werewolf: The Apocalypse</option>
                <option value="mage">✨ Mage: The Ascension</option>
                <option value="custom">🎲 Custom System</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '15px',
                background: loading ? '#ccc' : '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
              }}
            >
              {loading ? '⏳ Creating...' : '🚀 Create Campaign'}
            </button>
          </form>

          {error && (
            <div style={{
              marginTop: '20px',
              padding: '15px',
              background: '#fee',
              border: '2px solid #fcc',
              borderRadius: '8px',
              color: '#c33',
              fontWeight: '500'
            }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  // Render Discord-like chat interface
  const renderChat = () => {
    const campaignTheme = getCampaignTheme(selectedCampaign);
    
    return (
    <div style={{ height: '100vh', display: 'flex', background: '#36393f' }}>
      {/* Left Sidebar - Locations/Channels */}
      <div style={{
        width: '240px',
        background: '#2f3136',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid #202225'
      }}>
        {/* Campaign Header */}
        <div style={{
          padding: '15px',
          borderBottom: '1px solid #202225',
          color: 'white',
          fontWeight: 'bold',
          fontSize: '16px'
        }}>
          🎲 {selectedCampaign?.name}
        </div>

        {/* Locations/Channels */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '10px 0' }}>
          <div style={{
            padding: '5px 15px',
            color: '#8e9297',
            fontSize: '12px',
            fontWeight: '600',
            textTransform: 'uppercase',
            marginTop: '10px'
          }}>
            Locations
          </div>
          {locations.map(loc => (
            <div
              key={loc.id}
              onClick={() => changeLocation(loc)}
              style={{
                padding: '8px 15px',
                margin: '2px 8px',
                borderRadius: '4px',
                cursor: 'pointer',
                color: currentLocation?.id === loc.id ? 'white' : '#8e9297',
                background: currentLocation?.id === loc.id ? '#40444b' : 'transparent',
                fontSize: '15px',
                transition: 'all 0.15s'
              }}
              onMouseOver={(e) => {
                if (currentLocation?.id !== loc.id) {
                  e.currentTarget.style.background = '#3a3c42';
                  e.currentTarget.style.color = '#dcddde';
                }
              }}
              onMouseOut={(e) => {
                if (currentLocation?.id !== loc.id) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#8e9297';
                }
              }}
            >
              {loc.name}
            </div>
          ))}
        </div>

        {/* User Info at Bottom */}
        <div style={{
          padding: '10px',
          background: '#292b2f',
          borderTop: '1px solid #202225',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ color: 'white', fontSize: '14px', fontWeight: '500' }}>
            👤 {user?.username}
          </div>
          <button
            onClick={() => {
              setCurrentPage('dashboard');
              setSelectedCampaign(null);
            }}
            style={{
              padding: '5px 10px',
              background: '#40444b',
              color: '#dcddde',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            🚪 Exit
          </button>
        </div>
      </div>

      {/* Main Chat Area with Campaign Theme */}
      <GothicBox theme={campaignTheme} style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        {/* Channel Header */}
        <div style={{
          height: '48px',
          borderBottom: '1px solid #202225',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          background: '#36393f',
          boxShadow: '0 1px 0 rgba(0,0,0,0.2)',
          fontFamily: 'Cinzel, serif'
        }}>
          <span style={{ color: 'white', fontSize: '16px', fontWeight: '600' }}>
            {currentLocation?.name || 'Select a location'}
          </span>
        </div>

        {/* Messages Area */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          background: '#36393f'
        }}>
          {messages.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: '#8e9297'
            }}>
              <div style={{ fontSize: '48px', marginBottom: '10px' }}>💭</div>
              <div style={{ fontSize: '16px', fontWeight: '600', marginBottom: '5px' }}>
                No messages yet
              </div>
              <div style={{ fontSize: '14px' }}>
                Start the conversation in {currentLocation?.name}!
              </div>
            </div>
          ) : (
            messages.filter(msg => msg.location === currentLocation?.id).map((msg, idx) => (
              <div key={idx} style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '15px' }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '50%',
                    background: msg.role === 'user' ? '#5865f2' : '#ed4245',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '20px',
                    flexShrink: 0
                  }}>
                    {msg.role === 'user' ? '👤' : '🎭'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ marginBottom: '5px' }}>
                      <span style={{ color: msg.role === 'user' ? '#5865f2' : '#ed4245', fontWeight: '600', fontSize: '15px' }}>
                        {msg.role === 'user' ? user?.username : 'AI Storyteller'}
                      </span>
                      <span style={{ color: '#72767d', fontSize: '12px', marginLeft: '8px' }}>
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ color: '#dcddde', fontSize: '15px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                      {msg.content}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
          {loading && (
            <div style={{ textAlign: 'center', color: '#72767d', padding: '20px' }}>
              <div>⏳ AI is thinking...</div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div style={{ padding: '20px', background: '#36393f' }}>
          <form onSubmit={handleSendMessage}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type="text"
                name="message"
                placeholder={`Message in ${currentLocation?.name || 'this location'}...`}
                disabled={loading}
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  background: '#40444b',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#dcddde',
                  fontSize: '15px',
                  outline: 'none',
                  fontFamily: 'Crimson Text, serif'
                }}
              />
              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '12px 24px',
                  background: loading ? '#4e5058' : '#5865f2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: '600',
                  fontSize: '15px',
                  fontFamily: 'Cinzel, serif'
                }}
              >
                {loading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </form>

          {error && (
            <div style={{
              marginTop: '10px',
              padding: '10px',
              background: '#ed4245',
              color: 'white',
              borderRadius: '5px',
              fontSize: '14px'
            }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </GothicBox>

      {/* Right Sidebar - Character Info */}
      <div style={{
        width: '280px',
        background: '#2f3136',
        borderLeft: '1px solid #202225',
        padding: '20px',
        overflowY: 'auto'
      }}>
        <h3 style={{ color: 'white', marginBottom: '15px', fontSize: '16px', fontWeight: '600' }}>
          📋 Character Info
        </h3>
        
        {character ? (
          <div>
            {/* Character details would go here */}
            <div style={{ color: '#b9bbbe', fontSize: '14px' }}>
              {character.name}
            </div>
          </div>
        ) : (
          <div style={{ color: '#72767d', fontSize: '14px', lineHeight: '1.5' }}>
            <p>No character selected.</p>
            <p style={{ marginTop: '10px' }}>
              Create a character to see their stats and information here.
            </p>
          </div>
        )}

        <div style={{ marginTop: '30px', paddingTop: '20px', borderTop: '1px solid #202225' }}>
          <h4 style={{ color: 'white', marginBottom: '10px', fontSize: '14px', fontWeight: '600' }}>
            ⚡ Quick Actions
          </h4>
          <button style={{
            width: '100%',
            padding: '8px',
            background: '#40444b',
            color: '#dcddde',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px',
            marginBottom: '8px'
          }}>
            🎲 Roll Dice
          </button>
          <button style={{
            width: '100%',
            padding: '8px',
            background: '#40444b',
            color: '#dcddde',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px',
            marginBottom: '8px'
          }}>
            📚 Search Rules
          </button>
          <button style={{
            width: '100%',
            padding: '8px',
            background: '#40444b',
            color: '#dcddde',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px'
          }}>
            👤 View Character
          </button>
        </div>
      </div>
    </div>
    );
  };

  // Main render
  
  // Show Gothic Showcase if requested
  if (showGothicShowcase) {
    return <GothicShowcase onBack={() => setShowGothicShowcase(false)} />;
  }
  
  return (
    <div className="App">
      {!token && renderLogin()}
      {token && currentPage === 'dashboard' && renderDashboard()}
      {token && currentPage === 'createCampaign' && renderCreateCampaign()}
      {token && currentPage === 'campaignDetails' && renderCampaignDetails()}
      {token && currentPage === 'chat' && renderChat()}
      {token && currentPage === 'admin' && (
        <AdminPage 
          token={token} 
          user={user} 
          onBack={() => setCurrentPage('dashboard')} 
        />
      )}
    </div>
  );
}

export default SimpleApp;

import React, { useState, useEffect } from 'react';
import AdminPage from './pages/AdminPage';
import GothicShowcase from './pages/GothicShowcase';
import { GothicBox } from './components/GothicDecorations';
import './responsive.css';

const API_URL = '/api'; // Use relative URL through nginx proxy

function SimpleApp() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
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
  
  // Ref for chat input to maintain focus
  const chatInputRef = React.useRef(null);
  
  // Campaign editing state
  const [isEditingCampaignName, setIsEditingCampaignName] = useState(false);
  const [editedCampaignName, setEditedCampaignName] = useState('');
  const [isEditingCampaignDesc, setIsEditingCampaignDesc] = useState(false);
  const [editedCampaignDesc, setEditedCampaignDesc] = useState('');
  
  // Mobile responsive state
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(false);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);

  // Load user data on mount
  useEffect(() => {
    if (token) {
      fetchUserData();
    }
  }, [token]);

  // Handle window resize for responsive design
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      // Close sidebars when switching to desktop
      if (!mobile) {
        setLeftSidebarOpen(false);
        setRightSidebarOpen(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = (event) => {
      // If leaving chat page, show confirmation
      if (currentPage === 'chat' && event.state && event.state.page !== 'chat') {
        event.preventDefault();
        const locationName = currentLocation?.name || 'the location';
        /* eslint-disable-next-line no-restricted-globals */
        const confirmed = confirm(
          `⚠️ Leave Campaign?\n\n` +
          `You are currently in ${locationName}.\n` +
          `Your character will be marked as having left this location.\n\n` +
          `Are you sure you want to go back?`
        );
        
        if (!confirmed) {
          // Stay in chat - push chat state back
          window.history.pushState(
            { page: 'chat', selectedCampaign }, 
            '', 
            window.location.pathname
          );
          return;
        }
        // Clear chat state
        setSelectedCampaign(null);
        setCurrentLocation(null);
        setLocations([]);
        setMessages([]);
      }
      
      if (event.state) {
        setCurrentPage(event.state.page || 'dashboard');
        setShowGothicShowcase(event.state.showGothicShowcase || false);
        if (event.state.selectedCampaign) {
          setSelectedCampaign(event.state.selectedCampaign);
        }
      }
    };

    window.addEventListener('popstate', handlePopState);
    
    // Set initial state if not already set
    if (!window.history.state) {
      window.history.replaceState({ page: currentPage, showGothicShowcase }, '');
    }

    return () => window.removeEventListener('popstate', handlePopState);
  }, [currentPage, currentLocation, selectedCampaign]);

  // Navigate with browser history support
  const navigateTo = (page, campaign = null) => {
    const state = { 
      page, 
      showGothicShowcase: false,
      selectedCampaign: campaign 
    };
    window.history.pushState(state, '', window.location.pathname);
    setCurrentPage(page);
    if (campaign) {
      setSelectedCampaign(campaign);
    }
  };

  const showShowcase = (show) => {
    const state = { 
      page: currentPage,
      showGothicShowcase: show,
      selectedCampaign
    };
    if (show) {
      window.history.pushState(state, '', window.location.pathname);
    }
    setShowGothicShowcase(show);
  };

  // Fetch user data
  const fetchUserData = async () => {
    try {
      const response = await fetch(`${API_URL}/users/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data)); // Persist user data
      } else if (response.status === 401) {
        // Token expired or invalid, force logout
        console.error('Token expired or invalid');
        handleLogout();
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
        localStorage.setItem('user', JSON.stringify(data.user)); // Persist user data
        setCurrentPage('dashboard');
        setError('');
        fetchCampaigns();
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
        localStorage.setItem('user', JSON.stringify(data.user)); // Persist user data
        setCurrentPage('dashboard');
        setError('');
        fetchCampaigns();
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
    localStorage.removeItem('user'); // Clear persisted user data
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
    navigateTo('chat', campaign); // Use navigateTo for proper browser history
  };

  // Handle leaving chat with confirmation
  const handleLeaveCampaign = () => {
    const locationName = currentLocation?.name || 'the location';
    /* eslint-disable-next-line no-restricted-globals */
    const confirmed = confirm(
      `⚠️ Leave Campaign?\n\n` +
      `You are currently in ${locationName}.\n` +
      `Your character will be marked as having left this location.\n\n` +
      `Are you sure you want to exit?`
    );
    
    if (confirmed) {
      navigateTo('dashboard');
      setSelectedCampaign(null);
      setCurrentLocation(null);
      setLocations([]);
      setMessages([]);
    }
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
    
    // Keep focus on input after sending
    if (chatInputRef.current) {
      chatInputRef.current.focus();
    }

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

  // Update campaign name
  const handleUpdateCampaignName = async () => {
    if (!editedCampaignName.trim()) {
      setError('Campaign name cannot be empty');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: editedCampaignName })
      });

      if (response.ok) {
        // Update local state
        setSelectedCampaign({ ...selectedCampaign, name: editedCampaignName });
        setIsEditingCampaignName(false);
        // Refresh campaigns list
        fetchCampaigns();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update campaign name');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateCampaignDesc = async () => {
    if (!editedCampaignDesc.trim()) {
      setError('Campaign description cannot be empty');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ description: editedCampaignDesc })
      });

      if (response.ok) {
        // Update local state
        setSelectedCampaign({ ...selectedCampaign, description: editedCampaignDesc });
        setIsEditingCampaignDesc(false);
        // Refresh campaigns list
        fetchCampaigns();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update campaign description');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Get campaign theme based on game system
  const getCampaignTheme = (campaign) => {
    if (!campaign || !campaign.game_system) return 'none';
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Check for Vampire
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return 'vampire';
    }
    
    // Check for Mage
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return 'mage';
    }
    
    // Check for Werewolf
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return 'werewolf';
    }
    
    return 'none';
  };

  // Get campaign emoji based on game system
  const getCampaignEmoji = (campaign) => {
    if (!campaign || !campaign.game_system) return '📜';
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Vampire campaigns
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return '🦇';
    }
    
    // Mage campaigns
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return '🔮';
    }
    
    // Werewolf campaigns
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return '🐺';
    }
    
    // Changeling
    if (gameSystem.includes('changeling') || gameSystem.includes('dreaming')) {
      return '🧚';
    }
    
    // Hunter
    if (gameSystem.includes('hunter') || gameSystem.includes('reckoning')) {
      return '🗡️';
    }
    
    // Wraith
    if (gameSystem.includes('wraith') || gameSystem.includes('oblivion')) {
      return '👻';
    }
    
    // D&D / Fantasy
    if (gameSystem.includes('d&d') || gameSystem.includes('dungeons') || gameSystem.includes('pathfinder')) {
      return '⚔️';
    }
    
    // Default - ancient scroll
    return '📜';
  };

  // Get campaign color scheme based on game system
  const getCampaignColor = (campaign) => {
    if (!campaign || !campaign.game_system) {
      return {
        primary: '#e94560',
        bg: 'rgba(233, 69, 96, 0.2)',
        shadow: 'rgba(233, 69, 96, 0.3)'
      };
    }
    
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Vampire campaigns - Blood Red
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return {
        primary: '#e94560',
        bg: 'rgba(233, 69, 96, 0.2)',
        shadow: 'rgba(233, 69, 96, 0.3)'
      };
    }
    
    // Mage campaigns - Mystic Purple
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return {
        primary: '#9d4edd',
        bg: 'rgba(157, 78, 221, 0.2)',
        shadow: 'rgba(157, 78, 221, 0.3)'
      };
    }
    
    // Werewolf campaigns - Amber/Golden
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return {
        primary: '#d97706',
        bg: 'rgba(217, 119, 6, 0.2)',
        shadow: 'rgba(217, 119, 6, 0.3)'
      };
    }
    
    // Changeling - Fae Green
    if (gameSystem.includes('changeling') || gameSystem.includes('dreaming')) {
      return {
        primary: '#10b981',
        bg: 'rgba(16, 185, 129, 0.2)',
        shadow: 'rgba(16, 185, 129, 0.3)'
      };
    }
    
    // Hunter - Silver
    if (gameSystem.includes('hunter') || gameSystem.includes('reckoning')) {
      return {
        primary: '#94a3b8',
        bg: 'rgba(148, 163, 184, 0.2)',
        shadow: 'rgba(148, 163, 184, 0.3)'
      };
    }
    
    // Wraith - Ghost White/Blue
    if (gameSystem.includes('wraith') || gameSystem.includes('oblivion')) {
      return {
        primary: '#60a5fa',
        bg: 'rgba(96, 165, 250, 0.2)',
        shadow: 'rgba(96, 165, 250, 0.3)'
      };
    }
    
    // Default - Blood Red
    return {
      primary: '#e94560',
      bg: 'rgba(233, 69, 96, 0.2)',
      shadow: 'rgba(233, 69, 96, 0.3)'
    };
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
          onClick={() => showShowcase(true)}
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

      {/* Login and Register Side by Side (stacks on mobile) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)',
        gap: isMobile ? '20px' : '30px',
        width: '100%',
        maxWidth: isMobile ? '100%' : '950px',
        padding: isMobile ? '0 10px' : '0'
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
        padding: isMobile ? '15px' : '20px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center',
        gap: isMobile ? '15px' : '0',
        borderBottom: '2px solid #2a2a4e'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', justifyContent: isMobile ? 'center' : 'flex-start' }}>
          <img 
            src="https://github.com/Somnius/shadowrealms-ai/raw/main/assets/logos/logo-3.png" 
            alt="ShadowRealms AI" 
            style={{ width: isMobile ? '40px' : '50px', height: 'auto' }}
          />
          <h1 style={{ color: '#e94560', margin: 0, fontSize: isMobile ? '20px' : '24px' }}>ShadowRealms AI</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? '10px' : '15px', justifyContent: isMobile ? 'center' : 'flex-end', flexWrap: 'wrap' }}>
          <span style={{ color: '#b5b5c3', fontWeight: '500', fontSize: isMobile ? '14px' : '16px' }}>👤 {user?.username}</span>
          {user?.role === 'admin' && (
            <button
              onClick={() => navigateTo('admin')}
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
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: isMobile ? '20px 15px' : '40px 20px' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'stretch' : 'center', 
          gap: isMobile ? '15px' : '0',
          marginBottom: isMobile ? '20px' : '30px' 
        }}>
          <h2 style={{ color: '#e94560', margin: 0, fontSize: isMobile ? '20px' : '24px', textAlign: isMobile ? 'center' : 'left' }}>📚 Your Campaigns</h2>
          <button
            onClick={() => navigateTo('createCampaign')}
            style={{
              padding: '10px 20px',
              background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              color: 'white',
              border: '2px solid #e94560',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '16px',
              boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
              fontFamily: 'Cinzel, serif',
              transition: 'all 0.3s'
            }}
            onMouseOver={(e) => {
              e.target.style.boxShadow = '0 6px 25px rgba(233, 69, 96, 0.6)';
              e.target.style.transform = 'translateY(-2px)';
            }}
            onMouseOut={(e) => {
              e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
              e.target.style.transform = 'translateY(0)';
            }}
          >
            ✚ New Campaign
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
            gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: isMobile ? '15px' : '20px'
          }}>
            {campaigns.map(campaign => {
              // Extract first line or truncate description
              const firstLine = campaign.description.split('\n')[0];
              const shortDesc = firstLine.length > 100 
                ? firstLine.substring(0, 100) + '...' 
                : firstLine;
              
              const themeColor = getCampaignColor(campaign);
              
              return (
                <div
                  key={campaign.id}
                  style={{
                    position: 'relative',
                    background: '#16213e',
                    padding: '25px',
                    borderRadius: '10px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
                    cursor: 'pointer',
                    transition: 'transform 0.2s, border-color 0.2s, box-shadow 0.2s',
                    border: `2px solid #2a2a4e`,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '200px',
                    overflow: 'hidden'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.transform = 'translateY(-5px)';
                    e.currentTarget.style.borderColor = themeColor.primary;
                    e.currentTarget.style.boxShadow = `0 4px 20px ${themeColor.shadow}`;
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.borderColor = '#2a2a4e';
                    e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.5)';
                  }}
                >
                  {/* Gothic Ribbon - Top Left Corner */}
                  <div style={{
                    position: 'absolute',
                    top: '15px',
                    left: '-10px',
                    background: `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}cc 100%)`,
                    color: 'white',
                    padding: '8px 25px 8px 18px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    fontFamily: 'Cinzel, serif',
                    textTransform: 'uppercase',
                    letterSpacing: '1.5px',
                    boxShadow: `0 4px 15px ${themeColor.shadow}`,
                    borderRadius: '0 5px 5px 0',
                    zIndex: 10,
                    clipPath: 'polygon(10px 0, 100% 0, 100% 100%, 10px 100%, 0 50%)',
                    border: `2px solid ${themeColor.primary}`,
                    borderLeft: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    <span style={{ fontSize: '18px', lineHeight: '1' }}>{getCampaignEmoji(campaign)}</span>
                    <span>{campaign.game_system}</span>
                  </div>

                  <div onClick={() => enterCampaign(campaign)} style={{ marginTop: '45px' }}>
                    <h3 style={{ color: themeColor.primary, marginBottom: '10px', fontSize: '20px', fontFamily: 'Cinzel, serif' }}>
                      {campaign.name}
                    </h3>
                    <p style={{ color: '#b5b5c3', marginBottom: '15px', fontSize: '14px', lineHeight: '1.5', fontFamily: 'Crimson Text, serif' }}>
                      {shortDesc}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigateTo('campaignDetails', campaign);
                      }}
                      style={{
                        flex: 1,
                        padding: '8px 16px',
                        background: themeColor.bg,
                        color: themeColor.primary,
                        border: `1px solid ${themeColor.primary}`,
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600',
                        fontFamily: 'Cinzel, serif',
                        transition: 'all 0.2s'
                      }}
                      onMouseOver={(e) => {
                        e.target.style.background = themeColor.primary;
                        e.target.style.color = 'white';
                      }}
                      onMouseOut={(e) => {
                        e.target.style.background = themeColor.bg;
                        e.target.style.color = themeColor.primary;
                      }}
                    >
                      ⚙️ Settings
                    </button>
                    <button
                      onClick={() => enterCampaign(campaign)}
                      style={{
                        flex: 1,
                        padding: '8px 16px',
                        background: `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}dd 100%)`,
                        color: 'white',
                        border: `2px solid ${themeColor.primary}`,
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600',
                        boxShadow: `0 2px 10px ${themeColor.shadow}`,
                        fontFamily: 'Cinzel, serif',
                        transition: 'all 0.2s'
                      }}
                      onMouseOver={(e) => {
                        e.target.style.boxShadow = `0 4px 15px ${themeColor.shadow}`;
                        e.target.style.transform = 'translateY(-1px)';
                      }}
                      onMouseOut={(e) => {
                        e.target.style.boxShadow = `0 2px 10px ${themeColor.shadow}`;
                        e.target.style.transform = 'translateY(0)';
                      }}
                    >
                      ▶ Enter
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
          onClick={() => window.history.back()}
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
                background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                color: 'white',
                border: '2px solid #e94560',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '16px',
                boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
                fontFamily: 'Cinzel, serif',
                transition: 'all 0.3s'
              }}
              onMouseOver={(e) => {
                e.target.style.boxShadow = '0 6px 25px rgba(233, 69, 96, 0.6)';
                e.target.style.transform = 'translateY(-2px)';
              }}
              onMouseOut={(e) => {
                e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
                e.target.style.transform = 'translateY(0)';
              }}
            >
              ▶ Enter Campaign
            </button>
          </div>

          {/* Campaign Name - Editable for Admin */}
          <div style={{ marginBottom: '30px', paddingBottom: '20px', borderBottom: '2px solid #2a2a4e' }}>
            {isEditingCampaignName ? (
              <div style={{ marginBottom: '15px' }}>
                <input
                  type="text"
                  value={editedCampaignName}
                  onChange={(e) => setEditedCampaignName(e.target.value)}
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '12px',
                    fontSize: '24px',
                    fontWeight: 'bold',
                    color: '#e94560',
                    background: '#16213e',
                    border: '2px solid #e94560',
                    borderRadius: '8px',
                    marginBottom: '10px',
                    fontFamily: 'Cinzel, serif'
                  }}
                />
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleUpdateCampaignName}
                    disabled={loading}
                    style={{
                      padding: '8px 20px',
                      background: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    {loading ? 'Saving...' : '✓ Save'}
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingCampaignName(false);
                      setEditedCampaignName('');
                      setError('');
                    }}
                    style={{
                      padding: '8px 20px',
                      background: '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    ✗ Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '10px' }}>
                <h2 style={{ color: '#e94560', fontSize: '24px', margin: 0, fontFamily: 'Cinzel, serif' }}>
                  {selectedCampaign?.name}
                </h2>
                {user?.role === 'admin' && (
                  <button
                    onClick={() => {
                      setIsEditingCampaignName(true);
                      setEditedCampaignName(selectedCampaign?.name || '');
                    }}
                    style={{
                      padding: '6px 12px',
                      background: '#16213e',
                      color: '#e94560',
                      border: '2px solid #e94560',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    ✏️ Edit Name
                  </button>
                )}
              </div>
            )}
            <div style={{
              display: 'inline-block',
              padding: '5px 15px',
              background: 'rgba(157, 78, 221, 0.2)',
              color: '#9d4edd',
              border: '1px solid #9d4edd',
              borderRadius: '15px',
              fontSize: '14px',
              fontWeight: '600',
              fontFamily: 'Crimson Text, serif'
            }}>
              {selectedCampaign?.game_system}
            </div>
          </div>

          {/* Campaign Description/World Info */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '10px', fontFamily: 'Cinzel, serif' }}>
              📖 Campaign World & Setting
            </h3>
            {/* Warning about editing */}
            <div style={{
              background: 'rgba(233, 69, 96, 0.1)',
              border: '1px solid #e94560',
              borderRadius: '5px',
              padding: '10px',
              marginBottom: '10px',
              fontSize: '12px',
              color: '#e94560',
              fontFamily: 'Crimson Text, serif'
            }}>
              ⚠️ <strong>Warning:</strong> Changing this world setting will add or remove critical information that affects world generation, NPC behavior, and character interactions. Edit carefully.
            </div>
            {isEditingCampaignDesc ? (
              <div>
                <textarea
                  value={editedCampaignDesc}
                  onChange={(e) => setEditedCampaignDesc(e.target.value)}
                  autoFocus
                  style={{
                    width: '100%',
                    minHeight: '300px',
                    padding: '20px',
                    background: '#16213e',
                    color: '#d0d0e0',
                    border: '2px solid #e94560',
                    borderRadius: '8px',
                    fontSize: '15px',
                    lineHeight: '1.8',
                    fontFamily: 'Crimson Text, serif',
                    resize: 'vertical',
                    boxShadow: '0 0 20px rgba(233, 69, 96, 0.3)'
                  }}
                />
                <div style={{ marginTop: '10px', display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleUpdateCampaignDesc}
                    disabled={loading}
                    style={{
                      padding: '10px 20px',
                      background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                      color: 'white',
                      border: '2px solid #e94560',
                      borderRadius: '5px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif',
                      boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
                      opacity: loading ? 0.6 : 1
                    }}
                  >
                    ✓ Save Changes
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingCampaignDesc(false);
                      setEditedCampaignDesc('');
                    }}
                    disabled={loading}
                    style={{
                      padding: '10px 20px',
                      background: '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif',
                      opacity: loading ? 0.6 : 1
                    }}
                  >
                    ✗ Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{
                background: '#16213e',
                padding: '20px',
                borderRadius: '8px',
                border: '2px solid #2a2a4e',
                whiteSpace: 'pre-wrap',
                lineHeight: '1.8',
                fontSize: '15px',
                color: '#d0d0e0',
                maxHeight: '400px',
                overflowY: 'auto',
                fontFamily: 'Crimson Text, serif',
                boxShadow: 'inset 0 0 20px rgba(0,0,0,0.3)'
              }}>
                {selectedCampaign?.description}
              </div>
            )}
          </div>

          {/* Admin Actions */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px' }}>
              👑 Admin Actions
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <button
                onClick={() => {
                  setIsEditingCampaignDesc(true);
                  setEditedCampaignDesc(selectedCampaign?.description || '');
                }}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => {
                  e.target.style.background = '#ff556f';
                  e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
                }}
                onMouseOut={(e) => {
                  e.target.style.background = '#e94560';
                  e.target.style.boxShadow = 'none';
                }}
              >
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

          {/* Campaign Stats - Gothic Horror Style */}
          <div>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px', fontFamily: 'Cinzel, serif' }}>
              💀 Campaign Statistics
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
              {/* Active Players - Blood Red */}
              <div style={{ 
                background: '#1a0a0a', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(233, 69, 96, 0.3)',
                boxShadow: '0 0 15px rgba(233, 69, 96, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#e94560', fontFamily: 'Cinzel, serif' }}>0</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-users"></i> Active Players
                </div>
              </div>
              
              {/* Characters - Purple Magic */}
              <div style={{ 
                background: '#0a0a1a', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(157, 78, 221, 0.3)',
                boxShadow: '0 0 15px rgba(157, 78, 221, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#9d4edd', fontFamily: 'Cinzel, serif' }}>0</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-user-secret"></i> Characters
                </div>
              </div>
              
              {/* Locations - Amber Werewolf */}
              <div style={{ 
                background: '#1a1206', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(217, 119, 6, 0.3)',
                boxShadow: '0 0 15px rgba(217, 119, 6, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#d97706', fontFamily: 'Cinzel, serif' }}>0</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-map-marker-alt"></i> Locations
                </div>
              </div>
              
              {/* Messages - Silver */}
              <div style={{ 
                background: '#0f0f0f', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(181, 181, 195, 0.3)',
                boxShadow: '0 0 15px rgba(181, 181, 195, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#b5b5c3', fontFamily: 'Cinzel, serif' }}>0</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-comment"></i> Messages
                </div>
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
          onClick={() => window.history.back()}
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
    console.log('Chat Theme Debug:', {
      campaign: selectedCampaign?.name,
      gameSystem: selectedCampaign?.game_system,
      detectedTheme: campaignTheme
    });
    
    return (
    <div style={{ height: '100vh', display: 'flex', background: '#36393f', position: 'relative' }}>
      {/* Mobile Menu Buttons */}
      {isMobile && (
        <>
          <button
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            style={{
              position: 'fixed',
              top: '10px',
              left: '10px',
              zIndex: 1001,
              background: '#2f3136',
              border: '2px solid #e94560',
              color: '#e94560',
              padding: '10px',
              borderRadius: '8px',
              cursor: 'pointer',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px'
            }}
          >
            {leftSidebarOpen ? '✕' : '☰'}
          </button>
          <button
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            style={{
              position: 'fixed',
              top: '10px',
              right: '10px',
              zIndex: 1001,
              background: '#2f3136',
              border: '2px solid #e94560',
              color: '#e94560',
              padding: '10px',
              borderRadius: '8px',
              cursor: 'pointer',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px'
            }}
          >
            {rightSidebarOpen ? '✕' : '👤'}
          </button>
        </>
      )}

      {/* Sidebar Overlay for Mobile */}
      {isMobile && (leftSidebarOpen || rightSidebarOpen) && (
        <div
          onClick={() => {
            setLeftSidebarOpen(false);
            setRightSidebarOpen(false);
          }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            zIndex: 999
          }}
        />
      )}

      {/* Left Sidebar - Locations/Channels */}
      <div style={{
        width: isMobile ? '280px' : '240px',
        background: '#2f3136',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid #202225',
        position: isMobile ? 'fixed' : 'relative',
        left: isMobile ? (leftSidebarOpen ? '0' : '-280px') : 'auto',
        top: isMobile ? '0' : 'auto',
        bottom: isMobile ? '0' : 'auto',
        zIndex: 1000,
        transition: 'left 0.3s ease',
        height: isMobile ? '100vh' : 'auto'
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
            onClick={handleLeaveCampaign}
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
          justifyContent: 'space-between',
          padding: '0 20px',
          background: '#36393f',
          boxShadow: '0 1px 0 rgba(0,0,0,0.2)',
          fontFamily: 'Cinzel, serif'
        }}>
          <span style={{ color: 'white', fontSize: '16px', fontWeight: '600' }}>
            {currentLocation?.name || 'Select a location'}
          </span>
          {/* Debug theme indicator */}
          <span style={{ 
            fontSize: '11px', 
            color: '#72767d',
            background: '#2f3136',
            padding: '4px 8px',
            borderRadius: '4px',
            fontFamily: 'monospace'
          }}>
            Theme: {campaignTheme || 'none'}
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
                ref={chatInputRef}
                type="text"
                name="message"
                placeholder={`Message in ${currentLocation?.name || 'this location'}...`}
                disabled={loading}
                autoFocus
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
        width: isMobile ? '280px' : '280px',
        background: '#2f3136',
        borderLeft: '1px solid #202225',
        padding: '20px',
        position: isMobile ? 'fixed' : 'relative',
        right: isMobile ? (rightSidebarOpen ? '0' : '-280px') : 'auto',
        top: isMobile ? '0' : 'auto',
        bottom: isMobile ? '0' : 'auto',
        zIndex: 1000,
        transition: 'right 0.3s ease',
        height: isMobile ? '100vh' : 'auto',
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
    return <GothicShowcase onBack={() => window.history.back()} />;
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

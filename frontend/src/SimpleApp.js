import React, { useState, useEffect } from 'react';
import AdminPage from './pages/AdminPage';
import GothicShowcase from './pages/GothicShowcase';
import { GothicBox } from './components/GothicDecorations';
import ConfirmDialog from './components/ConfirmDialog';
import Footer from './components/Footer';
import LocationSuggestions from './components/LocationSuggestions';
import { useToast } from './components/ToastNotification';
import './responsive.css';

const API_URL = '/api'; // Use relative URL through nginx proxy

function SimpleApp() {
  // Initialize toast notification system
  const { showInfo, showError, showSuccess, ToastContainer } = useToast();
  
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
  
  // Confirmation dialog state
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState(null);
  
  // Location suggestions state
  const [showLocationSuggestions, setShowLocationSuggestions] = useState(false);
  const [newCampaignData, setNewCampaignData] = useState(null);
  
  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [showLocationManager, setShowLocationManager] = useState(false);
  const [campaignLocations, setCampaignLocations] = useState([]);
  const [showLocationDeleteConfirm, setShowLocationDeleteConfirm] = useState(false);
  const [locationToDelete, setLocationToDelete] = useState(null);

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
        // Store the pending navigation
        setPendingNavigation(event.state);
        // Show custom confirmation dialog
        setShowExitConfirm(true);
        // Push current state back temporarily until user confirms
        window.history.pushState(
          { page: 'chat', selectedCampaign }, 
          '', 
          window.location.pathname
        );
        return;
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
        // Store campaign data and show location suggestions
        console.log('✅ Campaign created:', data);
        setNewCampaignData({
          id: data.campaign_id, // ✅ Backend returns campaign_id, not id
          name: campaignData.name,
          description: campaignData.description,
          game_system: campaignData.game_system
        });
        setShowLocationSuggestions(true);
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

  // Fetch locations for a campaign from database
  const fetchCampaignLocations = async (campaignId) => {
    try {
      const response = await fetch(`${API_URL}/campaigns/${campaignId}/locations`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`📍 Loaded ${data.length} locations for campaign ${campaignId}`);
        return data;
      } else {
        console.error('Failed to load locations:', await response.text());
        return [];
      }
    } catch (error) {
      console.error('Error fetching locations:', error);
      return [];
    }
  };

  // Function to load locations for location manager
  const loadCampaignLocationsForManager = async (campaignId) => {
    try {
      const locations = await fetchCampaignLocations(campaignId);
      setCampaignLocations(locations);
    } catch (error) {
      console.error('Error loading campaign locations:', error);
      showError('Failed to load locations');
    }
  };

  // Function to trigger location delete confirmation
  const handleDeleteLocation = (locationId) => {
    setLocationToDelete(locationId);
    setShowLocationDeleteConfirm(true);
  };

  // Function to execute location deletion after confirmation
  const executeDeleteLocation = async () => {
    if (!locationToDelete) return;

    // Close confirmation modal immediately
    setShowLocationDeleteConfirm(false);
    const locationId = locationToDelete;
    setLocationToDelete(null);

    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/locations/${locationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMsg = errorData.error || `Failed to delete location (${response.status})`;
        throw new Error(errorMsg);
      }

      const data = await response.json();
      console.log('✅ Location deleted:', data);
      
      showSuccess('✅ Location deleted successfully!');
      
      // Reload locations list
      await loadCampaignLocationsForManager(selectedCampaign.id);
      
    } catch (error) {
      console.error('❌ Error deleting location:', error);
      showError(`❌ ${error.message || 'Failed to delete location'}`);
    } finally {
      setLoading(false);
    }
  };

  // Function to open location manager
  const openLocationManager = async () => {
    await loadCampaignLocationsForManager(selectedCampaign.id);
    setShowLocationManager(true);
  };

  // Function to trigger AI location suggestions for existing campaign
  const handleAddLocationsWithAI = () => {
    setNewCampaignData(selectedCampaign); // Reuse the same component
    setShowLocationSuggestions(true);
    setShowLocationManager(false); // Close manager while showing suggestions
  };

  // Callback when AI suggestions are completed (for existing campaign)
  const handleLocationSuggestionsComplete = async () => {
    setShowLocationSuggestions(false);
    setNewCampaignData(null);
    // Reload locations and reopen manager
    await loadCampaignLocationsForManager(selectedCampaign.id);
    setShowLocationManager(true);
    showSuccess('New locations added successfully!');
  };

  // Enter campaign (load locations from database and switch to chat view)
  const enterCampaign = async (campaign) => {
    setSelectedCampaign(campaign);
    
    // Fetch locations from database
    const campaignLocations = await fetchCampaignLocations(campaign.id);
    
    let initialLocation = null;
    if (campaignLocations.length > 0) {
      setLocations(campaignLocations);
      // Set OOC as default, or first location if no OOC
      const oocLocation = campaignLocations.find(loc => loc.type === 'ooc');
      initialLocation = oocLocation || campaignLocations[0];
      setCurrentLocation(initialLocation);
    } else {
      // Fallback if no locations (shouldn't happen but just in case)
      console.warn('⚠️ No locations found for campaign, using fallback');
      const fallbackLoc = { id: 0, name: '💬 OOC Chat', type: 'ooc' };
      setLocations([fallbackLoc]);
      setCurrentLocation(fallbackLoc);
      initialLocation = fallbackLoc;
    }
    
    // Load messages for initial location
    if (initialLocation) {
      await loadMessages(campaign.id, initialLocation.id);
    }
    
    navigateTo('chat', campaign); // Use navigateTo for proper browser history
  };

  // Handle leaving chat with confirmation
  const handleLeaveCampaign = () => {
    setShowExitConfirm(true);
  };

  // Confirm exit from campaign
  const confirmLeaveCampaign = () => {
    setShowExitConfirm(false);
    navigateTo('dashboard');
    setSelectedCampaign(null);
    setCurrentLocation(null);
    setLocations([]);
    setMessages([]);
    if (pendingNavigation) {
      setPendingNavigation(null);
    }
  };

  // Cancel exit from campaign
  const cancelLeaveCampaign = () => {
    setShowExitConfirm(false);
    // If there was a pending navigation (from back button), restore chat state
    if (pendingNavigation) {
      window.history.pushState(
        { page: 'chat', selectedCampaign }, 
        '', 
        window.location.pathname
      );
      setPendingNavigation(null);
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

    // Add user message to UI immediately (optimistic update)
    const tempUserMessage = {
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString(),
      location_id: currentLocation.id,
      username: user.username,
      temp: true  // Mark as temporary
    };
    setMessages(prev => [...prev, tempUserMessage]);
    e.target.reset();
    
    // Keep focus on input after sending
    if (chatInputRef.current) {
      chatInputRef.current.focus();
    }

    try {
      // Save user message to database
      const saveResponse = await fetch(`${API_URL}/messages/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: messageText,
          message_type: 'ic',
          role: 'user'
        })
      });

      if (saveResponse.ok) {
        const saveData = await saveResponse.json();
        console.log('✅ Message saved to database:', saveData);
        
        // Replace temp message with saved message
        setMessages(prev => 
          prev.map(msg => msg.temp ? saveData.data : msg)
        );
      } else {
        console.error('❌ Failed to save message to database');
      }

      // Get AI response
      const aiResponse = await fetch(`${API_URL}/ai/chat`, {
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

      const aiData = await aiResponse.json();

      if (aiResponse.ok) {
        const aiMessageContent = aiData.response || aiData.message || 'No response';
        
        // Save AI response to database
        const aiSaveResponse = await fetch(`${API_URL}/messages/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            content: aiMessageContent,
            message_type: 'ic',
            role: 'assistant'
          })
        });

        if (aiSaveResponse.ok) {
          const aiSaveData = await aiSaveResponse.json();
          console.log('✅ AI message saved to database:', aiSaveData);
          setMessages(prev => [...prev, aiSaveData.data]);
        } else {
          // Fallback: Add AI message to UI even if save failed
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: aiMessageContent,
            created_at: new Date().toISOString(),
            location_id: currentLocation.id,
            username: 'AI'
          }]);
        }
      } else {
        setError(aiData.error || 'Failed to get AI response');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load messages for a location
  const loadMessages = async (campaignId, locationId) => {
    try {
      console.log(`📨 Loading messages for location ${locationId}...`);
      const response = await fetch(`${API_URL}/messages/campaigns/${campaignId}/locations/${locationId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`✅ Loaded ${data.length} messages for location ${locationId}`);
        setMessages(data);
      } else {
        console.error('❌ Failed to load messages:', await response.text());
        setMessages([]);
      }
    } catch (error) {
      console.error('❌ Error loading messages:', error);
      setMessages([]);
    }
  };

  // Change location
  const changeLocation = async (location) => {
    setCurrentLocation(location);
    await loadMessages(selectedCampaign.id, location.id);
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
      flexDirection: 'column'
    }}>
      {/* Main Content - takes up available space */}
      <div style={{
        flex: 1,
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

      {/* Footer - sticks to bottom */}
      <Footer />
    </div>
  );

  // Render dashboard
  const renderDashboard = () => (
    <div style={{ 
      minHeight: '100vh', 
      background: '#0f0f1e',
      display: 'flex',
      flexDirection: 'column'
    }}>
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

      {/* Main content - takes up available space */}
      <div style={{ flex: 1 }}>
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

      {/* Footer - sticks to bottom */}
      <Footer />
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
              <button 
                onClick={() => showInfo('👥 Player management UI coming soon!\n\nFor now, players can join campaigns through invite codes.', 6000)}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                👥 Manage Players
              </button>
              <button 
                onClick={openLocationManager}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontFamily: 'Cinzel, serif'
                }}
              >
                🗺️ Manage Locations
              </button>
              <button 
                onClick={() => showInfo('📚 Rule book management coming soon!')}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                📚 Add Rule Books
              </button>
              <button 
                onClick={() => showInfo('💾 Export feature coming soon!')}
                style={{
                  padding: '12px',
                  background: '#ffc107',
                  color: '#e94560',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                💾 Export Campaign
              </button>
              <button 
                onClick={() => {
                  setDeleteConfirmText('');
                  setShowDeleteConfirm(true);
                }}
                style={{
                  padding: '12px',
                  background: '#dc3545',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
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
            messages.map((msg, idx) => (
              <div key={msg.id || idx} style={{ marginBottom: '20px' }}>
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
                        {msg.role === 'user' ? (msg.username || user?.username) : 'AI Storyteller'}
                      </span>
                      <span style={{ color: '#72767d', fontSize: '12px', marginLeft: '8px' }}>
                        {new Date(msg.created_at).toLocaleTimeString()}
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
      
      {/* Delete Campaign Confirmation Modal */}
      {showDeleteConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          animation: 'fadeIn 0.3s ease-out',
          padding: '20px'
        }}>
          <GothicBox theme="vampire" style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '15px',
            maxWidth: '550px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 0 40px rgba(233, 69, 96, 0.8)',
            border: '3px solid #e94560',
            position: 'relative'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>💀</div>
            <h2 style={{ 
              color: '#e94560', 
              marginBottom: '20px', 
              fontFamily: 'Cinzel, serif', 
              fontSize: '28px',
              textShadow: '0 0 10px rgba(233, 69, 96, 0.5)'
            }}>
              ⚠️ DELETE CAMPAIGN
            </h2>
            <div style={{
              background: 'rgba(220, 53, 69, 0.1)',
              border: '2px solid #dc3545',
              borderRadius: '10px',
              padding: '20px',
              marginBottom: '25px',
              textAlign: 'left'
            }}>
              <p style={{ 
                color: '#ff6b6b', 
                marginBottom: '15px', 
                lineHeight: '1.6',
                fontFamily: 'Crimson Text, serif',
                fontSize: '16px',
                fontWeight: 'bold'
              }}>
                You are about to permanently delete:
              </p>
              <p style={{ 
                color: '#d0d0e0', 
                marginBottom: '10px',
                fontFamily: 'Cinzel, serif',
                fontSize: '18px',
                textAlign: 'center',
                padding: '10px',
                background: 'rgba(233, 69, 96, 0.2)',
                borderRadius: '5px'
              }}>
                "{selectedCampaign?.name}"
              </p>
              <ul style={{ 
                color: '#ff6b6b', 
                marginBottom: '15px', 
                lineHeight: '1.8',
                fontFamily: 'Crimson Text, serif',
                fontSize: '15px',
                paddingLeft: '20px'
              }}>
                <li>All locations and rooms</li>
                <li>All characters and their data</li>
                <li>All messages and chat history</li>
                <li>All dice rolls and logs</li>
                <li>All campaign progress</li>
              </ul>
              <p style={{ 
                color: '#ff4444', 
                marginTop: '15px',
                fontFamily: 'Cinzel, serif',
                fontSize: '14px',
                fontWeight: 'bold',
                textAlign: 'center',
                textTransform: 'uppercase',
                letterSpacing: '1px'
              }}>
                ⚠️ THIS CANNOT BE UNDONE ⚠️
              </p>
            </div>
            
            <div style={{ marginBottom: '25px' }}>
              <label style={{ 
                color: '#b5b5c3', 
                display: 'block', 
                marginBottom: '10px',
                fontFamily: 'Crimson Text, serif',
                fontSize: '15px'
              }}>
                Type <strong style={{ color: '#e94560' }}>CONFIRM</strong> to proceed:
              </label>
              <input
                type="text"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="Type CONFIRM here"
                style={{
                  width: '100%',
                  padding: '12px',
                  background: '#0f1729',
                  border: '2px solid ' + (deleteConfirmText === 'CONFIRM' ? '#4ade80' : '#2a2a4e'),
                  borderRadius: '8px',
                  color: '#d0d0e0',
                  fontSize: '16px',
                  fontFamily: 'monospace',
                  textAlign: 'center',
                  textTransform: 'uppercase',
                  letterSpacing: '2px',
                  transition: 'all 0.3s'
                }}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteConfirmText('');
                }}
                style={{
                  padding: '14px 30px',
                  background: '#40444b',
                  color: '#dcddde',
                  border: '2px solid #6c757d',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => { 
                  e.target.style.background = '#6c757d'; 
                  e.target.style.color = 'white'; 
                }}
                onMouseOut={(e) => { 
                  e.target.style.background = '#40444b'; 
                  e.target.style.color = '#dcddde'; 
                }}
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (deleteConfirmText !== 'CONFIRM') return;
                  
                  try {
                    const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
                      method: 'DELETE',
                      headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    if (response.ok) {
                      setShowDeleteConfirm(false);
                      setDeleteConfirmText('');
                      await fetchCampaigns();
                      setCurrentPage('dashboard');
                      showSuccess('✅ Campaign deleted successfully!');
                    } else {
                      const data = await response.json();
                      showError('❌ Failed to delete: ' + (data.error || 'Unknown error'));
                    }
                  } catch (error) {
                    showError('❌ Error deleting campaign: ' + error.message);
                  }
                }}
                disabled={deleteConfirmText !== 'CONFIRM'}
                style={{
                  padding: '14px 30px',
                  background: deleteConfirmText === 'CONFIRM' 
                    ? 'linear-gradient(135deg, #dc3545 0%, #8b0000 100%)' 
                    : '#555',
                  color: deleteConfirmText === 'CONFIRM' ? 'white' : '#888',
                  border: deleteConfirmText === 'CONFIRM' ? '2px solid #dc3545' : '2px solid #555',
                  borderRadius: '8px',
                  cursor: deleteConfirmText === 'CONFIRM' ? 'pointer' : 'not-allowed',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  boxShadow: deleteConfirmText === 'CONFIRM' 
                    ? '0 4px 20px rgba(220, 53, 69, 0.6)' 
                    : 'none',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => {
                  if (deleteConfirmText === 'CONFIRM') {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 30px rgba(220, 53, 69, 0.8)';
                  }
                }}
                onMouseOut={(e) => {
                  if (deleteConfirmText === 'CONFIRM') {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 20px rgba(220, 53, 69, 0.6)';
                  }
                }}
              >
                {deleteConfirmText === 'CONFIRM' ? '🗑️ Delete Forever' : '🔒 Locked'}
              </button>
            </div>
          </GothicBox>
        </div>
      )}

      {/* Location Delete Confirmation Modal */}
      {showLocationDeleteConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          animation: 'fadeIn 0.3s ease-out',
          padding: '20px'
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '15px',
            maxWidth: '500px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 0 40px rgba(233, 69, 96, 0.8)',
            border: '3px solid #e94560'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>🗑️</div>
            <h2 style={{ 
              color: '#e94560', 
              marginBottom: '20px', 
              fontFamily: 'Cinzel, serif', 
              fontSize: '24px'
            }}>
              Delete Location?
            </h2>
            <p style={{ 
              color: '#d0d0e0', 
              marginBottom: '30px', 
              lineHeight: '1.6',
              fontFamily: 'Crimson Text, serif',
              fontSize: '16px'
            }}>
              Are you sure you want to delete this location?
              <br />
              <strong style={{ color: '#ff6b6b' }}>
                This will also delete all messages in this location.
              </strong>
              <br />
              This action cannot be undone.
            </p>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
              <button
                onClick={() => {
                  setShowLocationDeleteConfirm(false);
                  setLocationToDelete(null);
                }}
                style={{
                  padding: '14px 30px',
                  background: '#40444b',
                  color: '#dcddde',
                  border: '2px solid #6c757d',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => { 
                  e.target.style.background = '#5a5e66'; 
                  e.target.style.color = 'white'; 
                }}
                onMouseOut={(e) => { 
                  e.target.style.background = '#40444b'; 
                  e.target.style.color = '#dcddde'; 
                }}
              >
                Cancel
              </button>
              <button
                onClick={executeDeleteLocation}
                disabled={loading}
                style={{
                  padding: '14px 30px',
                  background: loading ? '#6c757d' : '#dc3545',
                  color: 'white',
                  border: loading ? '2px solid #6c757d' : '2px solid #dc3545',
                  borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => {
                  if (!loading) {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 30px rgba(220, 53, 69, 0.8)';
                  }
                }}
                onMouseOut={(e) => {
                  if (!loading) {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = 'none';
                  }
                }}
              >
                {loading ? '⏳ Deleting...' : '🗑️ Delete Location'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Location Suggestions Modal */}
      {showLocationSuggestions && newCampaignData && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          overflowY: 'auto'
        }}>
          <div style={{
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <LocationSuggestions
              campaignId={newCampaignData.id}
              settingDescription={newCampaignData.description}
              onComplete={async () => {
                // Check if we're adding to an existing campaign or new campaign
                if (selectedCampaign && selectedCampaign.id === newCampaignData.id) {
                  // Adding to existing campaign - return to location manager
                  await handleLocationSuggestionsComplete();
                } else {
                  // New campaign - return to dashboard
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  await fetchCampaigns();
                  setCurrentPage('dashboard');
                }
              }}
              onSkip={async () => {
                // Check if we're adding to an existing campaign or new campaign
                if (selectedCampaign && selectedCampaign.id === newCampaignData.id) {
                  // Adding to existing campaign - return to location manager
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  setShowLocationManager(true);
                } else {
                  // New campaign - return to dashboard
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  await fetchCampaigns();
                  setCurrentPage('dashboard');
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Location Manager Modal */}
      {showLocationManager && selectedCampaign && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          overflowY: 'auto'
        }}>
          <div style={{
            background: '#16213e',
            borderRadius: '15px',
            maxWidth: '800px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            border: '2px solid #e94560',
            boxShadow: '0 0 30px rgba(233, 69, 96, 0.5)'
          }}>
            {/* Header */}
            <div style={{
              background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              padding: '20px',
              borderTopLeftRadius: '13px',
              borderTopRightRadius: '13px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ color: 'white', margin: 0, fontFamily: 'Cinzel, serif', fontSize: '24px' }}>
                🗺️ Manage Locations
              </h2>
              <button
                onClick={() => setShowLocationManager(false)}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '50%',
                  width: '40px',
                  height: '40px',
                  cursor: 'pointer',
                  fontSize: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: '30px' }}>
              {/* Add Locations Button */}
              <div style={{ marginBottom: '30px', textAlign: 'center' }}>
                <button
                  onClick={handleAddLocationsWithAI}
                  disabled={loading}
                  style={{
                    padding: '15px 30px',
                    background: 'linear-gradient(135deg, #9d4edd 0%, #5a0099 100%)',
                    color: 'white',
                    border: '2px solid #9d4edd',
                    borderRadius: '10px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontSize: '18px',
                    fontWeight: 'bold',
                    fontFamily: 'Cinzel, serif',
                    boxShadow: '0 4px 15px rgba(157, 78, 221, 0.4)',
                    transition: 'all 0.3s'
                  }}
                  onMouseOver={(e) => !loading && (e.target.style.boxShadow = '0 6px 25px rgba(157, 78, 221, 0.6)')}
                  onMouseOut={(e) => !loading && (e.target.style.boxShadow = '0 4px 15px rgba(157, 78, 221, 0.4)')}
                >
                  ✨ Add New Locations (AI Suggestions)
                </button>
                <div style={{
                  marginTop: '10px',
                  color: '#9d4edd',
                  fontSize: '14px',
                  fontFamily: 'Crimson Text, serif'
                }}>
                  AI will suggest thematic locations based on your campaign setting
                </div>
              </div>

              {/* Current Locations */}
              <h3 style={{ color: '#e94560', marginBottom: '20px', fontFamily: 'Cinzel, serif' }}>
                Current Locations ({campaignLocations.length})
              </h3>

              {campaignLocations.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: '#8b8b9f',
                  fontFamily: 'Crimson Text, serif',
                  fontSize: '16px'
                }}>
                  No locations found. Click "Add New Locations" to create some!
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                  {campaignLocations.map((location) => (
                    <div
                      key={location.id}
                      style={{
                        background: '#0f1729',
                        padding: '20px',
                        borderRadius: '10px',
                        border: '2px solid #2a2a4e',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        transition: 'all 0.2s'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{
                          color: '#e94560',
                          fontSize: '18px',
                          fontWeight: 'bold',
                          marginBottom: '5px',
                          fontFamily: 'Cinzel, serif'
                        }}>
                          {location.name}
                        </div>
                        <div style={{
                          color: '#9d4edd',
                          fontSize: '14px',
                          marginBottom: '8px',
                          fontFamily: 'Crimson Text, serif',
                          textTransform: 'capitalize'
                        }}>
                          Type: {location.type}
                        </div>
                        {location.description && (
                          <div style={{
                            color: '#b5b5c3',
                            fontSize: '14px',
                            fontFamily: 'Crimson Text, serif',
                            lineHeight: '1.6'
                          }}>
                            {location.description}
                          </div>
                        )}
                      </div>
                      <div style={{ marginLeft: '20px', display: 'flex', gap: '10px' }}>
                        {location.type !== 'ooc' && (
                          <button
                            onClick={() => handleDeleteLocation(location.id)}
                            disabled={loading}
                            style={{
                              padding: '8px 16px',
                              background: '#dc3545',
                              color: 'white',
                              border: 'none',
                              borderRadius: '5px',
                              cursor: loading ? 'not-allowed' : 'pointer',
                              fontSize: '14px',
                              fontWeight: '600',
                              fontFamily: 'Cinzel, serif'
                            }}
                          >
                            🗑️ Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {token && currentPage === 'admin' && (
        <AdminPage 
          token={token} 
          user={user} 
          onBack={() => setCurrentPage('dashboard')} 
        />
      )}

      {/* Custom Exit Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showExitConfirm}
        title="⚠️ Leave Campaign?"
        message={`You are currently in ${currentLocation?.name || 'the location'}.\n\nYour character will be marked as having left this location.\n\nAre you sure you want to exit?`}
        onConfirm={confirmLeaveCampaign}
        onCancel={cancelLeaveCampaign}
        confirmText="Yes, Leave"
        cancelText="Stay Here"
      />
      
      {/* Toast Notifications */}
      <ToastContainer />
    </div>
  );
}

export default SimpleApp;

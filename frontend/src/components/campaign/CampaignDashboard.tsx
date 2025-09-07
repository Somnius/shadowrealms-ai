/**
 * ShadowRealms AI - Campaign Dashboard Component
 * 
 * This component provides the main interface for campaign management.
 * Users can view, create, join, and manage their RPG campaigns from this dashboard.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays a list of available campaigns with filtering options
 * 2. Provides campaign creation functionality
 * 3. Handles campaign joining and leaving
 * 4. Shows user's current campaigns and invitations
 * 5. Integrates with the campaign store for state management
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  PlusIcon, 
  MagnifyingGlassIcon,
  FunnelIcon,
  BookOpenIcon,
  UserGroupIcon,
  CalendarIcon,
  TagIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline';

// Import components and stores
import { useCampaignStore } from '../../store/campaignStore';
import { useAuthStore } from '../../store/authStore';
import { campaignService } from '../../services/campaignService';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import CampaignCard from './CampaignCard';
import CreateCampaignModal from './CreateCampaignModal';

// Import types
import { Campaign, CampaignStatus, RPGSystem, CampaignVisibility } from '../../types/campaign';

/**
 * Filter Options Interface
 * Defines the available filter options for campaigns
 */
interface FilterOptions {
  status: CampaignStatus | 'all';
  system: RPGSystem | 'all';
  visibility: CampaignVisibility | 'all';
  search: string;
}

/**
 * Campaign Dashboard Component
 * Main interface for campaign management
 */
const CampaignDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { 
    campaigns, 
    isLoading, 
    error, 
    setCampaigns, 
    setLoading, 
    setError, 
    clearError 
  } = useCampaignStore();

  // Local state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<FilterOptions>({
    status: 'all',
    system: 'all',
    visibility: 'all',
    search: ''
  });

  // Load campaigns on component mount
  useEffect(() => {
    loadCampaigns();
  }, []);

  /**
   * Load campaigns from the API
   */
  const loadCampaigns = async () => {
    try {
      setLoading(true);
      clearError();
      
      const response = await campaignService.getCampaigns({
        page: 1,
        limit: 50,
        ...(filters.status !== 'all' && { status: filters.status }),
        ...(filters.system !== 'all' && { system: filters.system }),
        ...(filters.visibility !== 'all' && { visibility: filters.visibility }),
        ...(filters.search && { search: filters.search })
      });
      
      setCampaigns(response.campaigns);
    } catch (error) {
      console.error('Failed to load campaigns:', error);
      setError('Failed to load campaigns. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Reload campaigns when filters change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      loadCampaigns();
    }, 500); // Debounce search

    return () => clearTimeout(timeoutId);
  }, [filters]);

  /**
   * Handle campaign creation
   */
  const handleCreateCampaign = async (campaignData: any) => {
    try {
      const newCampaign = await campaignService.createCampaign(campaignData);
      setCampaigns([...campaigns, newCampaign]);
      setShowCreateModal(false);
    } catch (error) {
      console.error('Failed to create campaign:', error);
      setError('Failed to create campaign. Please try again.');
    }
  };

  /**
   * Handle campaign join
   */
  const handleJoinCampaign = async (campaignId: string) => {
    try {
      await campaignService.joinCampaign({ campaignId });
      await loadCampaigns(); // Reload to get updated campaign data
    } catch (error) {
      console.error('Failed to join campaign:', error);
      setError('Failed to join campaign. Please try again.');
    }
  };

  /**
   * Handle campaign leave
   */
  const handleLeaveCampaign = async (campaignId: string) => {
    try {
      await campaignService.leaveCampaign(campaignId);
      await loadCampaigns(); // Reload to get updated campaign data
    } catch (error) {
      console.error('Failed to leave campaign:', error);
      setError('Failed to leave campaign. Please try again.');
    }
  };

  /**
   * Navigate to campaign chat
   */
  const handleEnterCampaign = (campaignId: string) => {
    navigate(`/campaign/${campaignId}/chat`);
  };

  /**
   * Update filter values
   */
  const updateFilter = (key: keyof FilterOptions, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  // Filter campaigns based on current filters
  const filteredCampaigns = campaigns.filter(campaign => {
    if (filters.status !== 'all' && campaign.status !== filters.status) return false;
    if (filters.system !== 'all' && campaign.system !== filters.system) return false;
    if (filters.visibility !== 'all' && campaign.visibility !== filters.visibility) return false;
    if (filters.search && !campaign.name.toLowerCase().includes(filters.search.toLowerCase()) &&
        !campaign.description.toLowerCase().includes(filters.search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-dark-900">
      {/* Header */}
      <header className="bg-dark-800 border-b border-dark-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5 }}
                className="flex items-center"
              >
                <BookOpenIcon className="h-8 w-8 text-primary-400 mr-3" />
                <h1 className="text-2xl font-bold text-white">Campaign Dashboard</h1>
              </motion.div>
            </div>

            <div className="flex items-center space-x-4">
              <Button
                variant="primary"
                onClick={() => setShowCreateModal(true)}
                className="flex items-center space-x-2"
              >
                <PlusIcon className="h-5 w-5" />
                <span>Create Campaign</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-8"
        >
          {/* Search and Filters */}
          <Card className="p-6">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0 lg:space-x-4">
              {/* Search */}
              <div className="flex-1">
                <Input
                  placeholder="Search campaigns..."
                  value={filters.search}
                  onChange={(e) => updateFilter('search', e.target.value)}
                  icon={MagnifyingGlassIcon}
                  className="w-full"
                />
              </div>

              {/* Filter Toggle */}
              <Button
                variant="secondary"
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center space-x-2"
              >
                <FunnelIcon className="h-5 w-5" />
                <span>Filters</span>
              </Button>
            </div>

            {/* Filter Options */}
            <AnimatePresence>
              {showFilters && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="mt-6 pt-6 border-t border-dark-700"
                >
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Status Filter */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Status
                      </label>
                      <select
                        value={filters.status}
                        onChange={(e) => updateFilter('status', e.target.value)}
                        className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      >
                        <option value="all">All Statuses</option>
                        <option value="draft">Draft</option>
                        <option value="active">Active</option>
                        <option value="paused">Paused</option>
                        <option value="completed">Completed</option>
                      </select>
                    </div>

                    {/* System Filter */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        RPG System
                      </label>
                      <select
                        value={filters.system}
                        onChange={(e) => updateFilter('system', e.target.value)}
                        className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      >
                        <option value="all">All Systems</option>
                        <option value="dnd_5e">D&D 5e</option>
                        <option value="world_of_darkness">World of Darkness</option>
                        <option value="pathfinder">Pathfinder</option>
                        <option value="custom">Custom</option>
                      </select>
                    </div>

                    {/* Visibility Filter */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Visibility
                      </label>
                      <select
                        value={filters.visibility}
                        onChange={(e) => updateFilter('visibility', e.target.value)}
                        className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      >
                        <option value="all">All Visibility</option>
                        <option value="public">Public</option>
                        <option value="private">Private</option>
                        <option value="friends_only">Friends Only</option>
                      </select>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>

          {/* Error Display */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-red-900/20 border border-red-500/30 rounded-lg p-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-red-400">{error}</p>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={clearError}
                >
                  Dismiss
                </Button>
              </div>
            </motion.div>
          )}

          {/* Campaigns Grid */}
          {isLoading ? (
            <div className="flex justify-center items-center py-12">
              <motion.div
                className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />
            </div>
          ) : filteredCampaigns.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCampaigns.map((campaign, index) => (
                <motion.div
                  key={campaign.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                >
                  <CampaignCard
                    campaign={campaign}
                    onJoin={() => handleJoinCampaign(campaign.id)}
                    onLeave={() => handleLeaveCampaign(campaign.id)}
                    onEnter={() => handleEnterCampaign(campaign.id)}
                    currentUserId={user?.id}
                  />
                </motion.div>
              ))}
            </div>
          ) : (
            <Card className="p-12 text-center">
              <BookOpenIcon className="h-16 w-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-400 mb-2">
                No Campaigns Found
              </h3>
              <p className="text-gray-500 mb-6">
                {filters.search || filters.status !== 'all' || filters.system !== 'all' || filters.visibility !== 'all'
                  ? 'Try adjusting your search or filters to find more campaigns.'
                  : 'Be the first to create a campaign and start your adventure!'
                }
              </p>
              <Button
                variant="primary"
                onClick={() => setShowCreateModal(true)}
                className="flex items-center space-x-2 mx-auto"
              >
                <PlusIcon className="h-5 w-5" />
                <span>Create Campaign</span>
              </Button>
            </Card>
          )}
        </motion.div>
      </main>

      {/* Create Campaign Modal */}
      <CreateCampaignModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateCampaign}
      />
    </div>
  );
};

export default CampaignDashboard;

/**
 * ShadowRealms AI - Campaign Store (Zustand)
 * 
 * This store manages all campaign-related state including:
 * - List of available campaigns
 * - Current active campaign
 * - Campaign creation and management
 * - Campaign settings and metadata
 * 
 * WHAT THIS STORE DOES:
 * 1. Manages campaign list and selection state
 * 2. Handles campaign creation, updates, and deletion
 * 3. Stores current campaign context for the application
 * 4. Provides actions for campaign management
 * 5. Persists campaign data to localStorage
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Import types
import { Campaign, CampaignCreateData, CampaignUpdateData } from '../types/campaign';

/**
 * Campaign Store State Interface
 * Defines the shape of the campaign store state
 */
interface CampaignState {
  // Campaign data
  campaigns: Campaign[];
  currentCampaign: Campaign | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setCampaigns: (campaigns: Campaign[]) => void;
  setCurrentCampaign: (campaign: Campaign | null) => void;
  addCampaign: (campaign: Campaign) => void;
  updateCampaign: (campaignId: string, updates: CampaignUpdateData) => void;
  deleteCampaign: (campaignId: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  
  // Computed getters
  getCampaignById: (campaignId: string) => Campaign | undefined;
  getUserCampaigns: (userId: string) => Campaign[];
  getActiveCampaigns: () => Campaign[];
}

/**
 * Campaign Store Implementation
 * Uses Zustand with persistence for state management
 */
export const useCampaignStore = create<CampaignState>()(
  persist(
    (set, get) => ({
      // Initial state
      campaigns: [],
      currentCampaign: null,
      isLoading: false,
      error: null,

      // Actions
      setCampaigns: (campaigns) => set({ campaigns, error: null }),

      setCurrentCampaign: (campaign) => set({ currentCampaign: campaign }),

      addCampaign: (campaign) => set((state) => ({
        campaigns: [...state.campaigns, campaign],
        error: null
      })),

      updateCampaign: (campaignId, updates) => set((state) => ({
        campaigns: state.campaigns.map((campaign) =>
          campaign.id === campaignId
            ? { ...campaign, ...updates, updatedAt: new Date().toISOString() }
            : campaign
        ),
        currentCampaign: state.currentCampaign?.id === campaignId
          ? { ...state.currentCampaign, ...updates, updatedAt: new Date().toISOString() }
          : state.currentCampaign,
        error: null
      })),

      deleteCampaign: (campaignId) => set((state) => ({
        campaigns: state.campaigns.filter((campaign) => campaign.id !== campaignId),
        currentCampaign: state.currentCampaign?.id === campaignId
          ? null
          : state.currentCampaign,
        error: null
      })),

      setLoading: (loading) => set({ isLoading: loading }),

      setError: (error) => set({ error }),

      clearError: () => set({ error: null }),

      // Computed getters
      getCampaignById: (campaignId) => {
        const state = get();
        return state.campaigns.find((campaign) => campaign.id === campaignId);
      },

      getUserCampaigns: (userId) => {
        const state = get();
        return state.campaigns.filter((campaign) => 
          campaign.gameMasterId === userId || 
          campaign.players.some((player) => player.id === userId)
        );
      },

      getActiveCampaigns: () => {
        const state = get();
        return state.campaigns.filter((campaign) => campaign.status === 'active');
      },
    }),
    {
      name: 'campaign-store', // localStorage key
      // Only persist campaigns and currentCampaign, not loading/error states
      partialize: (state) => ({
        campaigns: state.campaigns,
        currentCampaign: state.currentCampaign,
      }),
    }
  )
);

/**
 * Campaign Store Hooks
 * Convenience hooks for common campaign operations
 */

// Hook to get current campaign with null check
export const useCurrentCampaign = () => {
  const currentCampaign = useCampaignStore((state) => state.currentCampaign);
  return currentCampaign;
};

// Hook to get campaigns for current user
export const useUserCampaigns = (userId: string) => {
  const getUserCampaigns = useCampaignStore((state) => state.getUserCampaigns);
  return getUserCampaigns(userId);
};

// Hook to get campaign by ID
export const useCampaign = (campaignId: string) => {
  const getCampaignById = useCampaignStore((state) => state.getCampaignById);
  return getCampaignById(campaignId);
};

// Hook for campaign loading state
export const useCampaignLoading = () => {
  const isLoading = useCampaignStore((state) => state.isLoading);
  const setLoading = useCampaignStore((state) => state.setLoading);
  return { isLoading, setLoading };
};

// Hook for campaign error handling
export const useCampaignError = () => {
  const error = useCampaignStore((state) => state.error);
  const setError = useCampaignStore((state) => state.setError);
  const clearError = useCampaignStore((state) => state.clearError);
  return { error, setError, clearError };
};

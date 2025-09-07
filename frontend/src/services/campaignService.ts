/**
 * ShadowRealms AI - Campaign API Service
 * 
 * This service handles all API communication related to campaigns.
 * It provides methods for CRUD operations on campaigns and integrates
 * with the backend campaign management system.
 * 
 * WHAT THIS SERVICE DOES:
 * 1. Manages campaign CRUD operations (Create, Read, Update, Delete)
 * 2. Handles campaign joining and leaving
 * 3. Manages campaign invitations
 * 4. Provides campaign search and filtering
 * 5. Integrates with authentication for secure API calls
 */

import axios from 'axios';
import { 
  Campaign, 
  CampaignCreateData, 
  CampaignUpdateData,
  CampaignListResponse,
  CampaignJoinRequest,
  CampaignInvite,
  CampaignStatus,
  CampaignVisibility,
  RPGSystem
} from '../types/campaign';

// Create axios instance for campaign API calls
// This instance will include authentication headers and base configuration
const api = axios.create({
  baseURL: '/api/campaigns', // Base URL for campaign endpoints
  timeout: 10000, // 10 second timeout for requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include authentication token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle common errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid, redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/**
 * Campaign Service Class
 * Contains all methods for campaign-related API operations
 */
class CampaignService {
  /**
   * Get all campaigns with optional filtering and pagination
   * @param params - Query parameters for filtering and pagination
   * @returns Promise<CampaignListResponse>
   */
  async getCampaigns(params?: {
    page?: number;
    limit?: number;
    status?: CampaignStatus;
    system?: RPGSystem;
    visibility?: CampaignVisibility;
    search?: string;
    gameMasterId?: string;
  }): Promise<CampaignListResponse> {
    try {
      const response = await api.get('/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch campaigns:', error);
      throw error;
    }
  }

  /**
   * Get a specific campaign by ID
   * @param campaignId - The campaign ID
   * @returns Promise<Campaign>
   */
  async getCampaign(campaignId: string): Promise<Campaign> {
    try {
      const response = await api.get(`/${campaignId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Create a new campaign
   * @param campaignData - Data for creating the campaign
   * @returns Promise<Campaign>
   */
  async createCampaign(campaignData: CampaignCreateData): Promise<Campaign> {
    try {
      const response = await api.post('/', campaignData);
      return response.data;
    } catch (error) {
      console.error('Failed to create campaign:', error);
      throw error;
    }
  }

  /**
   * Update an existing campaign
   * @param campaignId - The campaign ID to update
   * @param updates - Data to update
   * @returns Promise<Campaign>
   */
  async updateCampaign(campaignId: string, updates: CampaignUpdateData): Promise<Campaign> {
    try {
      const response = await api.put(`/${campaignId}`, updates);
      return response.data;
    } catch (error) {
      console.error(`Failed to update campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Delete a campaign
   * @param campaignId - The campaign ID to delete
   * @returns Promise<void>
   */
  async deleteCampaign(campaignId: string): Promise<void> {
    try {
      await api.delete(`/${campaignId}`);
    } catch (error) {
      console.error(`Failed to delete campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Join a campaign
   * @param joinRequest - Join request data
   * @returns Promise<Campaign>
   */
  async joinCampaign(joinRequest: CampaignJoinRequest): Promise<Campaign> {
    try {
      const response = await api.post(`/${joinRequest.campaignId}/join`, joinRequest);
      return response.data;
    } catch (error) {
      console.error(`Failed to join campaign ${joinRequest.campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Leave a campaign
   * @param campaignId - The campaign ID to leave
   * @returns Promise<void>
   */
  async leaveCampaign(campaignId: string): Promise<void> {
    try {
      await api.post(`/${campaignId}/leave`);
    } catch (error) {
      console.error(`Failed to leave campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Get campaigns for the current user
   * @returns Promise<Campaign[]>
   */
  async getUserCampaigns(): Promise<Campaign[]> {
    try {
      const response = await api.get('/my-campaigns');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch user campaigns:', error);
      throw error;
    }
  }

  /**
   * Get campaigns where the user is the game master
   * @returns Promise<Campaign[]>
   */
  async getGameMasterCampaigns(): Promise<Campaign[]> {
    try {
      const response = await api.get('/my-gm-campaigns');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch GM campaigns:', error);
      throw error;
    }
  }

  /**
   * Search campaigns by name or description
   * @param query - Search query
   * @param filters - Optional filters
   * @returns Promise<CampaignListResponse>
   */
  async searchCampaigns(
    query: string, 
    filters?: {
      system?: RPGSystem;
      status?: CampaignStatus;
      visibility?: CampaignVisibility;
    }
  ): Promise<CampaignListResponse> {
    try {
      const response = await api.get('/search', {
        params: { q: query, ...filters }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to search campaigns:', error);
      throw error;
    }
  }

  /**
   * Get campaign invitations for the current user
   * @returns Promise<CampaignInvite[]>
   */
  async getCampaignInvites(): Promise<CampaignInvite[]> {
    try {
      const response = await api.get('/invites');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch campaign invites:', error);
      throw error;
    }
  }

  /**
   * Accept a campaign invitation
   * @param inviteId - The invitation ID
   * @returns Promise<Campaign>
   */
  async acceptInvite(inviteId: string): Promise<Campaign> {
    try {
      const response = await api.post(`/invites/${inviteId}/accept`);
      return response.data;
    } catch (error) {
      console.error(`Failed to accept invite ${inviteId}:`, error);
      throw error;
    }
  }

  /**
   * Decline a campaign invitation
   * @param inviteId - The invitation ID
   * @returns Promise<void>
   */
  async declineInvite(inviteId: string): Promise<void> {
    try {
      await api.post(`/invites/${inviteId}/decline`);
    } catch (error) {
      console.error(`Failed to decline invite ${inviteId}:`, error);
      throw error;
    }
  }

  /**
   * Invite a player to a campaign
   * @param campaignId - The campaign ID
   * @param playerId - The player ID to invite
   * @param message - Optional invite message
   * @returns Promise<CampaignInvite>
   */
  async invitePlayer(
    campaignId: string, 
    playerId: string, 
    message?: string
  ): Promise<CampaignInvite> {
    try {
      const response = await api.post(`/${campaignId}/invite`, {
        playerId,
        message
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to invite player to campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Remove a player from a campaign
   * @param campaignId - The campaign ID
   * @param playerId - The player ID to remove
   * @returns Promise<void>
   */
  async removePlayer(campaignId: string, playerId: string): Promise<void> {
    try {
      await api.delete(`/${campaignId}/players/${playerId}`);
    } catch (error) {
      console.error(`Failed to remove player from campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Get campaign statistics
   * @param campaignId - The campaign ID
   * @returns Promise<object>
   */
  async getCampaignStats(campaignId: string): Promise<object> {
    try {
      const response = await api.get(`/${campaignId}/stats`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch campaign stats ${campaignId}:`, error);
      throw error;
    }
  }
}

// Create and export a singleton instance of the service
export const campaignService = new CampaignService();
export default campaignService;

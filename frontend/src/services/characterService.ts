/**
 * ShadowRealms AI - Character API Service
 * 
 * This service handles all API communication related to character management.
 * It provides methods for CRUD operations on characters and integrates
 * with the backend character system.
 * 
 * WHAT THIS SERVICE DOES:
 * 1. Manages character CRUD operations (Create, Read, Update, Delete)
 * 2. Handles character dice rolling and actions
 * 3. Manages character equipment and inventory
 * 4. Provides character statistics and calculations
 * 5. Integrates with authentication for secure API calls
 */

import axios from 'axios';
import { 
  Character, 
  CharacterCreateData, 
  CharacterUpdateData,
  CharacterListResponse,
  CharacterResponse,
  CharacterRollRequest,
  CharacterActionRequest
} from '../types/character';

// Create axios instance for character API calls
const api = axios.create({
  baseURL: '/api/characters', // Base URL for character endpoints
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
 * Character Service Class
 * Contains all methods for character-related API operations
 */
class CharacterService {
  /**
   * Get all characters with optional filtering and pagination
   * @param params - Query parameters for filtering and pagination
   * @returns Promise<CharacterListResponse>
   */
  async getCharacters(params?: {
    page?: number;
    limit?: number;
    campaignId?: string;
    playerId?: string;
    status?: string;
    search?: string;
  }): Promise<CharacterListResponse> {
    try {
      const response = await api.get('/', { params });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch characters:', error);
      throw error;
    }
  }

  /**
   * Get a specific character by ID
   * @param characterId - The character ID
   * @returns Promise<Character>
   */
  async getCharacter(characterId: string): Promise<Character> {
    try {
      const response = await api.get(`/${characterId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Create a new character
   * @param characterData - Data for creating the character
   * @returns Promise<Character>
   */
  async createCharacter(characterData: CharacterCreateData): Promise<Character> {
    try {
      const response = await api.post('/', characterData);
      return response.data;
    } catch (error) {
      console.error('Failed to create character:', error);
      throw error;
    }
  }

  /**
   * Update an existing character
   * @param characterId - The character ID to update
   * @param updates - Data to update
   * @returns Promise<Character>
   */
  async updateCharacter(characterId: string, updates: CharacterUpdateData): Promise<Character> {
    try {
      const response = await api.put(`/${characterId}`, updates);
      return response.data;
    } catch (error) {
      console.error(`Failed to update character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Delete a character
   * @param characterId - The character ID to delete
   * @returns Promise<void>
   */
  async deleteCharacter(characterId: string): Promise<void> {
    try {
      await api.delete(`/${characterId}`);
    } catch (error) {
      console.error(`Failed to delete character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Get characters for a specific campaign
   * @param campaignId - The campaign ID
   * @returns Promise<Character[]>
   */
  async getCampaignCharacters(campaignId: string): Promise<Character[]> {
    try {
      const response = await api.get(`/campaign/${campaignId}`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch characters for campaign ${campaignId}:`, error);
      throw error;
    }
  }

  /**
   * Get characters for the current user
   * @returns Promise<Character[]>
   */
  async getUserCharacters(): Promise<Character[]> {
    try {
      const response = await api.get('/my-characters');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch user characters:', error);
      throw error;
    }
  }

  /**
   * Set a character as active for a campaign
   * @param characterId - The character ID
   * @param campaignId - The campaign ID
   * @returns Promise<Character>
   */
  async setActiveCharacter(characterId: string, campaignId: string): Promise<Character> {
    try {
      const response = await api.post(`/${characterId}/activate`, { campaignId });
      return response.data;
    } catch (error) {
      console.error(`Failed to activate character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Roll dice for a character
   * @param rollRequest - Roll request data
   * @returns Promise<any>
   */
  async rollDice(rollRequest: CharacterRollRequest): Promise<any> {
    try {
      const response = await api.post(`/${rollRequest.characterId}/roll`, rollRequest);
      return response.data;
    } catch (error) {
      console.error(`Failed to roll dice for character ${rollRequest.characterId}:`, error);
      throw error;
    }
  }

  /**
   * Perform a character action
   * @param actionRequest - Action request data
   * @returns Promise<any>
   */
  async performAction(actionRequest: CharacterActionRequest): Promise<any> {
    try {
      const response = await api.post(`/${actionRequest.characterId}/action`, actionRequest);
      return response.data;
    } catch (error) {
      console.error(`Failed to perform action for character ${actionRequest.characterId}:`, error);
      throw error;
    }
  }

  /**
   * Update character hit points
   * @param characterId - The character ID
   * @param hitPoints - New hit points value
   * @param isTemporary - Whether the HP change is temporary
   * @returns Promise<Character>
   */
  async updateHitPoints(characterId: string, hitPoints: number, isTemporary: boolean = false): Promise<Character> {
    try {
      const response = await api.put(`/${characterId}/hit-points`, { 
        hitPoints, 
        isTemporary 
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to update hit points for character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Add experience points to a character
   * @param characterId - The character ID
   * @param experiencePoints - XP to add
   * @returns Promise<Character>
   */
  async addExperience(characterId: string, experiencePoints: number): Promise<Character> {
    try {
      const response = await api.post(`/${characterId}/experience`, { 
        experiencePoints 
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to add experience to character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Level up a character
   * @param characterId - The character ID
   * @param newLevel - The new level
   * @returns Promise<Character>
   */
  async levelUp(characterId: string, newLevel: number): Promise<Character> {
    try {
      const response = await api.post(`/${characterId}/level-up`, { 
        newLevel 
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to level up character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Get character statistics
   * @param characterId - The character ID
   * @returns Promise<object>
   */
  async getCharacterStats(characterId: string): Promise<object> {
    try {
      const response = await api.get(`/${characterId}/stats`);
      return response.data;
    } catch (error) {
      console.error(`Failed to fetch stats for character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Search characters by name or description
   * @param query - Search query
   * @param filters - Optional filters
   * @returns Promise<CharacterListResponse>
   */
  async searchCharacters(
    query: string, 
    filters?: {
      campaignId?: string;
      playerId?: string;
      race?: string;
      class?: string;
      level?: number;
    }
  ): Promise<CharacterListResponse> {
    try {
      const response = await api.get('/search', {
        params: { q: query, ...filters }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to search characters:', error);
      throw error;
    }
  }

  /**
   * Duplicate a character
   * @param characterId - The character ID to duplicate
   * @param newName - Name for the new character
   * @returns Promise<Character>
   */
  async duplicateCharacter(characterId: string, newName: string): Promise<Character> {
    try {
      const response = await api.post(`/${characterId}/duplicate`, { 
        newName 
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to duplicate character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Export character data
   * @param characterId - The character ID
   * @param format - Export format ('json' | 'pdf' | 'text')
   * @returns Promise<Blob>
   */
  async exportCharacter(characterId: string, format: 'json' | 'pdf' | 'text' = 'json'): Promise<Blob> {
    try {
      const response = await api.get(`/${characterId}/export`, {
        params: { format },
        responseType: 'blob'
      });
      return response.data;
    } catch (error) {
      console.error(`Failed to export character ${characterId}:`, error);
      throw error;
    }
  }

  /**
   * Import character data
   * @param characterData - Character data to import
   * @param campaignId - Campaign to import character into
   * @returns Promise<Character>
   */
  async importCharacter(characterData: any, campaignId: string): Promise<Character> {
    try {
      const response = await api.post('/import', { 
        characterData, 
        campaignId 
      });
      return response.data;
    } catch (error) {
      console.error('Failed to import character:', error);
      throw error;
    }
  }
}

// Create and export a singleton instance of the service
export const characterService = new CharacterService();
export default characterService;

/**
 * ShadowRealms AI - Chat API Service
 * 
 * This service handles all API communication related to chat functionality.
 * It provides methods for sending messages, managing channels, and handling
 * real-time chat operations.
 * 
 * WHAT THIS SERVICE DOES:
 * 1. Manages chat message CRUD operations
 * 2. Handles channel creation and management
 * 3. Provides real-time chat functionality
 * 4. Manages user presence and typing indicators
 * 5. Integrates with WebSocket for real-time updates
 */

import axios from 'axios';
import { 
  ChatMessage, 
  ChatChannel, 
  ChatUser,
  SendMessageRequest,
  CreateChannelRequest,
  UpdateChannelRequest,
  ChatHistoryRequest,
  ChatResponse,
  MessageType,
  ChannelType
} from '../types/chat';

// Create axios instance for chat API calls
const api = axios.create({
  baseURL: '/api/chat', // Base URL for chat endpoints
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
 * Chat Service Class
 * Contains all methods for chat-related API operations
 */
class ChatService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;

  /**
   * Connect to WebSocket for real-time chat
   * @param campaignId - Campaign ID to connect to
   * @param onMessage - Callback for receiving messages
   * @param onUserUpdate - Callback for user status updates
   * @param onTyping - Callback for typing indicators
   */
  connectWebSocket(
    campaignId: string,
    onMessage: (message: ChatMessage) => void,
    onUserUpdate: (user: ChatUser) => void,
    onTyping: (typing: { userId: string; username: string; isTyping: boolean }) => void
  ) {
    try {
      const token = localStorage.getItem('token');
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat/${campaignId}?token=${token}`;
      
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'message':
              onMessage(data.message);
              break;
            case 'user_update':
              onUserUpdate(data.user);
              break;
            case 'typing':
              onTyping(data.typing);
              break;
            case 'error':
              console.error('WebSocket error:', data.error);
              break;
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.attemptReconnect(campaignId, onMessage, onUserUpdate, onTyping);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }

  /**
   * Attempt to reconnect WebSocket
   */
  private attemptReconnect(
    campaignId: string,
    onMessage: (message: ChatMessage) => void,
    onUserUpdate: (user: ChatUser) => void,
    onTyping: (typing: { userId: string; username: string; isTyping: boolean }) => void
  ) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      setTimeout(() => {
        console.log(`Attempting to reconnect WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        this.connectWebSocket(campaignId, onMessage, onUserUpdate, onTyping);
      }, delay);
    } else {
      console.error('Max WebSocket reconnection attempts reached');
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnectWebSocket() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a message via WebSocket
   * @param message - Message to send
   */
  sendMessage(message: SendMessageRequest) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'send_message',
        data: message
      }));
    } else {
      console.error('WebSocket is not connected');
    }
  }

  /**
   * Send typing indicator via WebSocket
   * @param channelId - Channel ID
   * @param isTyping - Whether user is typing
   */
  sendTypingIndicator(channelId: string, isTyping: boolean) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'typing',
        data: { channelId, isTyping }
      }));
    }
  }

  /**
   * Get chat history for a channel
   * @param request - Chat history request parameters
   * @returns Promise<ChatMessage[]>
   */
  async getChatHistory(request: ChatHistoryRequest): Promise<ChatMessage[]> {
    try {
      const response = await api.get(`/channels/${request.channelId}/messages`, {
        params: {
          limit: request.limit || 50,
          before: request.before,
          after: request.after,
          types: request.messageTypes?.join(',')
        }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch chat history:', error);
      throw error;
    }
  }

  /**
   * Send a message via HTTP API (fallback)
   * @param message - Message to send
   * @returns Promise<ChatMessage>
   */
  async sendMessageHTTP(message: SendMessageRequest): Promise<ChatMessage> {
    try {
      const response = await api.post('/messages', message);
      return response.data;
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }

  /**
   * Get all channels for a campaign
   * @param campaignId - Campaign ID
   * @returns Promise<ChatChannel[]>
   */
  async getChannels(campaignId: string): Promise<ChatChannel[]> {
    try {
      const response = await api.get(`/campaigns/${campaignId}/channels`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch channels:', error);
      throw error;
    }
  }

  /**
   * Create a new channel
   * @param campaignId - Campaign ID
   * @param channelData - Channel creation data
   * @returns Promise<ChatChannel>
   */
  async createChannel(campaignId: string, channelData: CreateChannelRequest): Promise<ChatChannel> {
    try {
      const response = await api.post(`/campaigns/${campaignId}/channels`, channelData);
      return response.data;
    } catch (error) {
      console.error('Failed to create channel:', error);
      throw error;
    }
  }

  /**
   * Update a channel
   * @param channelId - Channel ID
   * @param updates - Channel updates
   * @returns Promise<ChatChannel>
   */
  async updateChannel(channelId: string, updates: UpdateChannelRequest): Promise<ChatChannel> {
    try {
      const response = await api.put(`/channels/${channelId}`, updates);
      return response.data;
    } catch (error) {
      console.error('Failed to update channel:', error);
      throw error;
    }
  }

  /**
   * Delete a channel
   * @param channelId - Channel ID
   * @returns Promise<void>
   */
  async deleteChannel(channelId: string): Promise<void> {
    try {
      await api.delete(`/channels/${channelId}`);
    } catch (error) {
      console.error('Failed to delete channel:', error);
      throw error;
    }
  }

  /**
   * Get online users for a campaign
   * @param campaignId - Campaign ID
   * @returns Promise<ChatUser[]>
   */
  async getOnlineUsers(campaignId: string): Promise<ChatUser[]> {
    try {
      const response = await api.get(`/campaigns/${campaignId}/users`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch online users:', error);
      throw error;
    }
  }

  /**
   * Update user status
   * @param status - New user status
   * @returns Promise<void>
   */
  async updateUserStatus(status: 'online' | 'away' | 'busy' | 'offline'): Promise<void> {
    try {
      await api.put('/users/status', { status });
    } catch (error) {
      console.error('Failed to update user status:', error);
      throw error;
    }
  }

  /**
   * Mark channel as read
   * @param channelId - Channel ID
   * @returns Promise<void>
   */
  async markChannelAsRead(channelId: string): Promise<void> {
    try {
      await api.post(`/channels/${channelId}/read`);
    } catch (error) {
      console.error('Failed to mark channel as read:', error);
      throw error;
    }
  }

  /**
   * Edit a message
   * @param messageId - Message ID
   * @param content - New message content
   * @returns Promise<ChatMessage>
   */
  async editMessage(messageId: string, content: string): Promise<ChatMessage> {
    try {
      const response = await api.put(`/messages/${messageId}`, { content });
      return response.data;
    } catch (error) {
      console.error('Failed to edit message:', error);
      throw error;
    }
  }

  /**
   * Delete a message
   * @param messageId - Message ID
   * @returns Promise<void>
   */
  async deleteMessage(messageId: string): Promise<void> {
    try {
      await api.delete(`/messages/${messageId}`);
    } catch (error) {
      console.error('Failed to delete message:', error);
      throw error;
    }
  }

  /**
   * Add reaction to a message
   * @param messageId - Message ID
   * @param emoji - Emoji to add
   * @returns Promise<void>
   */
  async addReaction(messageId: string, emoji: string): Promise<void> {
    try {
      await api.post(`/messages/${messageId}/reactions`, { emoji });
    } catch (error) {
      console.error('Failed to add reaction:', error);
      throw error;
    }
  }

  /**
   * Remove reaction from a message
   * @param messageId - Message ID
   * @param emoji - Emoji to remove
   * @returns Promise<void>
   */
  async removeReaction(messageId: string, emoji: string): Promise<void> {
    try {
      await api.delete(`/messages/${messageId}/reactions/${emoji}`);
    } catch (error) {
      console.error('Failed to remove reaction:', error);
      throw error;
    }
  }

  /**
   * Get user's chat settings
   * @returns Promise<object>
   */
  async getChatSettings(): Promise<object> {
    try {
      const response = await api.get('/settings');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch chat settings:', error);
      throw error;
    }
  }

  /**
   * Update user's chat settings
   * @param settings - Settings to update
   * @returns Promise<object>
   */
  async updateChatSettings(settings: object): Promise<object> {
    try {
      const response = await api.put('/settings', settings);
      return response.data;
    } catch (error) {
      console.error('Failed to update chat settings:', error);
      throw error;
    }
  }
}

// Create and export a singleton instance of the service
export const chatService = new ChatService();
export default chatService;

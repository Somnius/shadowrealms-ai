/**
 * ShadowRealms AI - Chat Store (Zustand)
 * 
 * This store manages all chat-related state including:
 * - Chat messages and history
 * - Current chat channel/room
 * - Online users and their status
 * - Chat settings and preferences
 * - Real-time message updates
 * 
 * WHAT THIS STORE DOES:
 * 1. Manages chat messages and message history
 * 2. Handles real-time message updates and synchronization
 * 3. Tracks online users and their activity status
 * 4. Manages chat channels and room switching
 * 5. Provides actions for sending messages and managing chat state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Import types
import { ChatMessage, ChatChannel, ChatUser, ChatSettings } from '../types/chat';

/**
 * Chat Store State Interface
 * Defines the shape of the chat store state
 */
interface ChatState {
  // Chat data
  messages: ChatMessage[];
  channels: ChatChannel[];
  currentChannel: ChatChannel | null;
  onlineUsers: ChatUser[];
  settings: ChatSettings;
  
  // UI state
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;
  
  // Actions
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
  deleteMessage: (messageId: string) => void;
  clearMessages: () => void;
  
  setChannels: (channels: ChatChannel[]) => void;
  setCurrentChannel: (channel: ChatChannel | null) => void;
  addChannel: (channel: ChatChannel) => void;
  updateChannel: (channelId: string, updates: Partial<ChatChannel>) => void;
  removeChannel: (channelId: string) => void;
  
  setOnlineUsers: (users: ChatUser[]) => void;
  addOnlineUser: (user: ChatUser) => void;
  removeOnlineUser: (userId: string) => void;
  updateUserStatus: (userId: string, status: 'online' | 'away' | 'busy' | 'offline') => void;
  
  updateSettings: (settings: Partial<ChatSettings>) => void;
  
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setConnected: (connected: boolean) => void;
  clearError: () => void;
  
  // Computed getters
  getMessagesForChannel: (channelId: string) => ChatMessage[];
  getOnlineUserCount: () => number;
  getUnreadMessageCount: (channelId: string) => number;
  markChannelAsRead: (channelId: string) => void;
}

/**
 * Chat Store Implementation
 * Uses Zustand with persistence for state management
 */
export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // Initial state
      messages: [],
      channels: [],
      currentChannel: null,
      onlineUsers: [],
      settings: {
        showTimestamps: true,
        showUserAvatars: true,
        enableSoundNotifications: true,
        enableDesktopNotifications: true,
        messageHistoryLimit: 1000,
        autoScroll: true,
        compactMode: false,
        theme: 'dark'
      },
      
      isLoading: false,
      error: null,
      isConnected: false,

      // Message actions
      setMessages: (messages) => set({ messages, error: null }),

      addMessage: (message) => set((state) => ({
        messages: [...state.messages, message],
        error: null
      })),

      updateMessage: (messageId, updates) => set((state) => ({
        messages: state.messages.map((message) =>
          message.id === messageId
            ? { ...message, ...updates }
            : message
        ),
        error: null
      })),

      deleteMessage: (messageId) => set((state) => ({
        messages: state.messages.filter((message) => message.id !== messageId),
        error: null
      })),

      clearMessages: () => set({ messages: [], error: null }),

      // Channel actions
      setChannels: (channels) => set({ channels, error: null }),

      setCurrentChannel: (channel) => set({ currentChannel: channel }),

      addChannel: (channel) => set((state) => ({
        channels: [...state.channels, channel],
        error: null
      })),

      updateChannel: (channelId, updates) => set((state) => ({
        channels: state.channels.map((channel) =>
          channel.id === channelId
            ? { ...channel, ...updates }
            : channel
        ),
        error: null
      })),

      removeChannel: (channelId) => set((state) => ({
        channels: state.channels.filter((channel) => channel.id !== channelId),
        currentChannel: state.currentChannel?.id === channelId ? null : state.currentChannel,
        error: null
      })),

      // User actions
      setOnlineUsers: (users) => set({ onlineUsers: users, error: null }),

      addOnlineUser: (user) => set((state) => ({
        onlineUsers: [...state.onlineUsers.filter(u => u.id !== user.id), user],
        error: null
      })),

      removeOnlineUser: (userId) => set((state) => ({
        onlineUsers: state.onlineUsers.filter((user) => user.id !== userId),
        error: null
      })),

      updateUserStatus: (userId, status) => set((state) => ({
        onlineUsers: state.onlineUsers.map((user) =>
          user.id === userId
            ? { ...user, status, lastSeen: new Date().toISOString() }
            : user
        ),
        error: null
      })),

      // Settings actions
      updateSettings: (settings) => set((state) => ({
        settings: { ...state.settings, ...settings },
        error: null
      })),

      // General actions
      setLoading: (loading) => set({ isLoading: loading }),

      setError: (error) => set({ error }),

      setConnected: (connected) => set({ isConnected: connected }),

      clearError: () => set({ error: null }),

      // Computed getters
      getMessagesForChannel: (channelId) => {
        const state = get();
        return state.messages.filter((message) => message.channelId === channelId);
      },

      getOnlineUserCount: () => {
        const state = get();
        return state.onlineUsers.filter((user) => user.status === 'online').length;
      },

      getUnreadMessageCount: (channelId) => {
        const state = get();
        const channel = state.channels.find((c) => c.id === channelId);
        if (!channel) return 0;
        
        const lastReadAt = channel.lastReadAt;
        if (!lastReadAt) return 0;
        
        return state.messages.filter((message) => 
          message.channelId === channelId && 
          new Date(message.timestamp) > new Date(lastReadAt)
        ).length;
      },

      markChannelAsRead: (channelId) => set((state) => ({
        channels: state.channels.map((channel) =>
          channel.id === channelId
            ? { ...channel, lastReadAt: new Date().toISOString() }
            : channel
        )
      })),
    }),
    {
      name: 'chat-store', // localStorage key
      // Only persist messages, channels, and settings, not loading/error states
      partialize: (state) => ({
        messages: state.messages.slice(-state.settings.messageHistoryLimit), // Keep only recent messages
        channels: state.channels,
        settings: state.settings,
      }),
    }
  )
);

/**
 * Chat Store Hooks
 * Convenience hooks for common chat operations
 */

// Hook to get messages for current channel
export const useCurrentChannelMessages = () => {
  const currentChannel = useChatStore((state) => state.currentChannel);
  const getMessagesForChannel = useChatStore((state) => state.getMessagesForChannel);
  
  return currentChannel ? getMessagesForChannel(currentChannel.id) : [];
};

// Hook to get online users
export const useOnlineUsers = () => {
  const onlineUsers = useChatStore((state) => state.onlineUsers);
  const getOnlineUserCount = useChatStore((state) => state.getOnlineUserCount);
  
  return {
    users: onlineUsers,
    count: getOnlineUserCount()
  };
};

// Hook for chat settings
export const useChatSettings = () => {
  const settings = useChatStore((state) => state.settings);
  const updateSettings = useChatStore((state) => state.updateSettings);
  
  return { settings, updateSettings };
};

// Hook for chat connection status
export const useChatConnection = () => {
  const isConnected = useChatStore((state) => state.isConnected);
  const setConnected = useChatStore((state) => state.setConnected);
  
  return { isConnected, setConnected };
};

// Hook for chat loading state
export const useChatLoading = () => {
  const isLoading = useChatStore((state) => state.isLoading);
  const setLoading = useChatStore((state) => state.setLoading);
  
  return { isLoading, setLoading };
};

// Hook for chat error handling
export const useChatError = () => {
  const error = useChatStore((state) => state.error);
  const setError = useChatStore((state) => state.setError);
  const clearError = useChatStore((state) => state.clearError);
  
  return { error, setError, clearError };
};

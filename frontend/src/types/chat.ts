/**
 * ShadowRealms AI - Chat Types
 * 
 * This file contains all TypeScript type definitions related to chat functionality.
 * It includes interfaces for messages, users, channels, and related data structures.
 * 
 * WHAT THIS FILE CONTAINS:
 * 1. Chat message interfaces and types
 * 2. User and channel information types
 * 3. Message metadata and reaction types
 * 4. Chat settings and configuration types
 * 5. Enums for message types, user status, and channel types
 */

/**
 * Message Type Enum
 * Defines the different types of chat messages
 */
export enum MessageType {
  TEXT = 'text',
  SYSTEM = 'system',
  DICE_ROLL = 'dice_roll',
  OOC = 'ooc', // Out of character
  IC = 'ic', // In character
  WHISPER = 'whisper',
  ACTION = 'action',
  EMOTE = 'emote'
}

/**
 * User Status Enum
 * Defines the possible online statuses of a user
 */
export enum UserStatus {
  ONLINE = 'online',
  AWAY = 'away',
  BUSY = 'busy',
  OFFLINE = 'offline'
}

/**
 * Channel Type Enum
 * Defines the different types of chat channels
 */
export enum ChannelType {
  GENERAL = 'general',
  IC = 'ic', // In character
  OOC = 'ooc', // Out of character
  PRIVATE = 'private',
  WHISPER = 'whisper'
}

/**
 * Dice Roll Metadata Interface
 * Contains information about dice roll results
 */
export interface DiceRollMetadata {
  formula: string;
  results: number[];
  total: number;
  critical: boolean;
  fumble?: boolean;
}

/**
 * Message Reaction Interface
 * Represents a reaction to a message
 */
export interface MessageReaction {
  emoji: string;
  userId: string;
  username: string;
  timestamp: string;
}

/**
 * Message Mention Interface
 * Represents a user mention in a message
 */
export interface MessageMention {
  userId: string;
  username: string;
  startIndex: number;
  endIndex: number;
}

/**
 * Chat Message Interface
 * Represents a single chat message
 */
export interface ChatMessage {
  id: string;
  channelId: string;
  userId: string;
  username: string;
  content: string;
  type: MessageType;
  timestamp: string;
  editedAt?: string;
  mentions?: MessageMention[];
  reactions?: MessageReaction[];
  metadata?: {
    diceRoll?: DiceRollMetadata;
    [key: string]: any;
  };
}

/**
 * Chat User Interface
 * Represents a user in the chat system
 */
export interface ChatUser {
  id: string;
  username: string;
  avatar?: string;
  status: UserStatus;
  lastSeen: string;
  isTyping: boolean;
  role: 'player' | 'gm' | 'helper';
  characterName?: string;
}

/**
 * Chat Channel Interface
 * Represents a chat channel
 */
export interface ChatChannel {
  id: string;
  name: string;
  type: ChannelType;
  description?: string;
  isPrivate: boolean;
  participants: string[]; // User IDs
  createdAt: string;
  updatedAt: string;
}

/**
 * Typing Indicator Interface
 * Represents users currently typing in a channel
 */
export interface TypingIndicator {
  channelId: string;
  userId: string;
  username: string;
  timestamp: string;
}

/**
 * Chat Settings Interface
 * Defines chat configuration options
 */
export interface ChatSettings {
  enableSound: boolean;
  enableNotifications: boolean;
  showTimestamps: boolean;
  showUserAvatars: boolean;
  compactMode: boolean;
  autoScroll: boolean;
  messageHistory: number; // Number of messages to keep in memory
}

/**
 * Chat State Interface
 * Represents the current state of the chat system
 */
export interface ChatState {
  messages: ChatMessage[];
  channels: ChatChannel[];
  users: ChatUser[];
  currentChannel: ChatChannel | null;
  typingUsers: string[];
  isLoading: boolean;
  error: string | null;
}

/**
 * Send Message Data Interface
 * Used when sending a new message
 */
export interface SendMessageData {
  channelId: string;
  content: string;
  type: MessageType;
  mentions?: MessageMention[];
}

/**
 * Create Channel Data Interface
 * Used when creating a new channel
 */
export interface CreateChannelData {
  name: string;
  type: ChannelType;
  description?: string;
  isPrivate: boolean;
  participants?: string[];
}

/**
 * Update Channel Data Interface
 * Used when updating a channel
 */
export interface UpdateChannelData {
  name?: string;
  description?: string;
  participants?: string[];
}

/**
 * Join Channel Data Interface
 * Used when joining a channel
 */
export interface JoinChannelData {
  channelId: string;
  password?: string;
}

/**
 * Leave Channel Data Interface
 * Used when leaving a channel
 */
export interface LeaveChannelData {
  channelId: string;
}

/**
 * Whisper Data Interface
 * Used when sending a whisper message
 */
export interface WhisperData {
  recipientId: string;
  content: string;
}

/**
 * Message Search Result Interface
 * Represents a search result for messages
 */
export interface MessageSearchResult {
  message: ChatMessage;
  channel: ChatChannel;
  relevanceScore: number;
}
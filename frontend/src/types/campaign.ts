/**
 * ShadowRealms AI - Campaign Types
 * 
 * This file contains all TypeScript type definitions related to campaigns.
 * It includes interfaces for campaigns, users, settings, and related data structures.
 * 
 * WHAT THIS FILE CONTAINS:
 * 1. Campaign-related interfaces and types
 * 2. User and player information types
 * 3. Campaign settings and configuration types
 * 4. Campaign statistics and metadata types
 * 5. Enums for campaign status, visibility, and RPG systems
 */

/**
 * Campaign Status Enum
 * Defines the possible states of a campaign
 */
export enum CampaignStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled'
}

/**
 * Campaign Visibility Enum
 * Defines who can see and join a campaign
 */
export enum CampaignVisibility {
  PUBLIC = 'public',
  PRIVATE = 'private',
  INVITE_ONLY = 'invite_only'
}

/**
 * RPG System Enum
 * Defines the supported RPG systems
 */
export enum RPGSystem {
  DND_5E = 'dnd_5e',
  PATHFINDER_2E = 'pathfinder_2e',
  VAMPIRE_THE_MASQUERADE = 'vampire_the_masquerade',
  MAGE_THE_ASCENSION = 'mage_the_ascension',
  WEREWOLF_THE_APOCALYPSE = 'werewolf_the_apocalypse',
  CHANGELING_THE_DREAMING = 'changeling_the_dreaming',
  WRATH_THE_OBLIVION = 'wraith_the_oblivion',
  HUNTER_THE_RECKONING = 'hunter_the_reckoning',
  DEMON_THE_FALLEN = 'demon_the_fallen',
  CUSTOM = 'custom'
}

/**
 * User Interface
 * Represents a user in the system
 */
export interface User {
  id: string;
  username: string;
  email: string;
  role: 'player' | 'gm' | 'admin';
  experience?: number;
  specialties?: string[];
  avatar?: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * Campaign Player Interface
 * Represents a player in a campaign
 */
export interface CampaignPlayer {
  id: string;
  username: string;
  email: string;
  role: 'player' | 'helper';
  joinedAt: string;
  isOnline: boolean;
  characterCount: number;
  characterName?: string;
}

/**
 * Campaign Settings Interface
 * Defines the configuration options for a campaign
 */
export interface CampaignSettings {
  aiAssistance: boolean;
  aiPersonality: 'helpful' | 'neutral' | 'challenging';
  aiResponseLength: 'short' | 'medium' | 'long';
  maxPlayers: number;
  allowSpectators: boolean;
  requireApproval: boolean;
  enableOOC: boolean;
  enablePrivateMessages: boolean;
  enableDiceRolls: boolean;
  timezone: string;
  language: string;
}

/**
 * Campaign Statistics Interface
 * Tracks various metrics for a campaign
 */
export interface CampaignStats {
  totalSessions: number;
  totalPlayTime: number; // in hours
  totalMessages: number;
  averageSessionLength: number; // in hours
  lastSessionAt?: string;
  playerRetention: number; // percentage
}

/**
 * Campaign Interface
 * Represents a complete campaign with all its data
 */
export interface Campaign {
  id: string;
  name: string;
  description: string;
  system: RPGSystem;
  status: CampaignStatus;
  visibility: CampaignVisibility;
  gameMaster: User;
  gameMasterId: string;
  players: CampaignPlayer[];
  maxPlayers: number;
  setting: string;
  theme: string;
  tags?: string[];
  settings: CampaignSettings;
  stats: CampaignStats;
  createdAt: string;
  updatedAt: string;
}

/**
 * Create Campaign Data Interface
 * Used when creating a new campaign
 */
export interface CreateCampaignData {
  name: string;
  description: string;
  system: RPGSystem;
  visibility: CampaignVisibility;
  maxPlayers: number;
  setting: string;
  theme: string;
  tags?: string[];
  settings: Partial<CampaignSettings>;
}

/**
 * Update Campaign Data Interface
 * Used when updating an existing campaign
 */
export interface UpdateCampaignData {
  name?: string;
  description?: string;
  status?: CampaignStatus;
  visibility?: CampaignVisibility;
  maxPlayers?: number;
  setting?: string;
  theme?: string;
  tags?: string[];
  settings?: Partial<CampaignSettings>;
}

/**
 * Campaign Join Request Interface
 * Used when a player requests to join a campaign
 */
export interface CampaignJoinRequest {
  campaignId: string;
  message?: string;
  characterName?: string;
}

/**
 * Campaign Invite Interface
 * Used when inviting a player to a campaign
 */
export interface CampaignInvite {
  id: string;
  campaignId: string;
  campaignName: string;
  invitedBy: string;
  invitedByUsername: string;
  message?: string;
  expiresAt: string;
  createdAt: string;
}
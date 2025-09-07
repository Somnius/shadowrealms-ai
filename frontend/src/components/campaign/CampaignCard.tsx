/**
 * ShadowRealms AI - Campaign Card Component
 * 
 * This component displays a single campaign card with all relevant information
 * and action buttons based on the user's role and campaign status.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays campaign information (name, description, GM, players, etc.)
 * 2. Shows campaign status and visibility indicators
 * 3. Provides appropriate action buttons based on user role
 * 4. Handles user interactions (join, leave, enter campaign)
 * 5. Shows campaign statistics and metadata
 */

import React from 'react';
import { motion } from 'framer-motion';
import { 
  UserGroupIcon,
  CalendarIcon,
  ClockIcon,
  TagIcon
} from '@heroicons/react/24/outline';
import { Campaign, CampaignStatus, CampaignVisibility } from '../../types/campaign';
import Button from '../ui/Button';
import Card from '../ui/Card';

/**
 * Campaign Card Props Interface
 * Defines the props that the CampaignCard component accepts
 */
interface CampaignCardProps {
  campaign: Campaign;
  currentUserId?: string;
  onJoin?: () => void;
  onLeave?: (campaignId: string) => void;
  onEnter?: (campaignId: string) => void;
}

/**
 * Get status color and indicator for campaign status
 * @param status - Campaign status
 * @returns Object with color classes and indicator
 */
const getStatusInfo = (status: CampaignStatus) => {
  switch (status) {
    case CampaignStatus.ACTIVE:
      return {
        color: 'text-green-400',
        bgColor: 'bg-green-900/30',
        label: 'Active'
      };
    case CampaignStatus.PAUSED:
      return {
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/30',
        label: 'Paused'
      };
    case CampaignStatus.COMPLETED:
      return {
        color: 'text-blue-400',
        bgColor: 'bg-blue-900/30',
        label: 'Completed'
      };
    default:
      return {
        color: 'text-gray-400',
        bgColor: 'bg-gray-900/30',
        label: 'Unknown'
      };
  }
};

/**
 * Get visibility color and indicator for campaign visibility
 * @param visibility - Campaign visibility
 * @returns Object with color classes and indicator
 */
const getVisibilityInfo = (visibility: CampaignVisibility) => {
  switch (visibility) {
    case CampaignVisibility.PUBLIC:
      return {
        color: 'text-green-400',
        bgColor: 'bg-green-900/30',
        label: 'Public'
      };
    case CampaignVisibility.PRIVATE:
      return {
        color: 'text-red-400',
        bgColor: 'bg-red-900/30',
        label: 'Private'
      };
    case CampaignVisibility.INVITE_ONLY:
      return {
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/30',
        label: 'Invite Only'
      };
    default:
      return {
        color: 'text-gray-400',
        bgColor: 'bg-gray-900/30',
        label: 'Unknown'
      };
  }
};

/**
 * Campaign Card Component
 * Displays a single campaign with all relevant information and actions
 */
const CampaignCard: React.FC<CampaignCardProps> = ({
  campaign,
  currentUserId,
  onJoin,
  onLeave,
  onEnter
}) => {
  const statusInfo = getStatusInfo(campaign.status);
  const visibilityInfo = getVisibilityInfo(campaign.visibility);
  
  // Check if current user is in the campaign
  const isPlayer = campaign.players.some(player => player.id === currentUserId);
  const isGameMaster = campaign.gameMasterId === currentUserId;
  const isFull = campaign.players.length >= campaign.maxPlayers;
  
  // Determine what actions to show
  const canJoin = !isPlayer && !isGameMaster && campaign.status === CampaignStatus.ACTIVE && !isFull;
  const canLeave = (isPlayer || isGameMaster) && campaign.status === CampaignStatus.ACTIVE;
  const canEnter = (isPlayer || isGameMaster) && campaign.status === CampaignStatus.ACTIVE;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full"
    >
      <Card className="p-6 hover:border-primary-500/50 transition-colors duration-200">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h3 className="text-xl font-semibold text-primary-300 mb-2">
              {campaign.name}
            </h3>
            <p className="text-gray-400 text-sm mb-3">
              {campaign.description}
            </p>
          </div>
          
          {/* Status and Visibility Badges */}
          <div className="flex flex-col space-y-2 ml-4">
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusInfo.bgColor} ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${visibilityInfo.bgColor} ${visibilityInfo.color}`}>
              {visibilityInfo.label}
            </span>
          </div>
        </div>

        {/* Campaign Details */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <UserGroupIcon className="h-4 w-4" />
            <span>{campaign.players.length} / {campaign.maxPlayers} players</span>
            {isFull && <span className="text-red-400">(Full)</span>}
          </div>
          
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <CalendarIcon className="h-4 w-4" />
            <span>{campaign.setting}</span>
          </div>
          
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <ClockIcon className="h-4 w-4" />
            <span>{campaign.theme}</span>
          </div>
          
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <span className="font-medium">System:</span>
            <span>{campaign.system}</span>
          </div>
        </div>

        {/* Game Master */}
        <div className="mb-4">
          <div className="flex items-center space-x-2 text-sm text-gray-400">
            <span className="font-medium">Game Master:</span>
            <span className="text-primary-300">{campaign.gameMaster.username}</span>
          </div>
        </div>

        {/* Players */}
        {campaign.players.length > 0 && (
          <div className="mb-4">
            <div className="text-sm text-gray-400 mb-2">Players:</div>
            <div className="flex flex-wrap gap-2">
              {campaign.players.map((player) => (
                <div key={player.id} className="flex items-center space-x-1 text-xs">
                  <span className="text-primary-300">{player.username}</span>
                  {player.characterName && (
                    <span className="text-gray-500">({player.characterName})</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tags */}
        {campaign.tags && campaign.tags.length > 0 && (
          <div className="mb-4">
            <div className="flex flex-wrap gap-2">
              {campaign.tags.map((tag, index) => (
                <span
                  key={index}
                  className="flex items-center space-x-1 px-2 py-1 bg-dark-700 rounded-full text-xs text-gray-300"
                >
                  <TagIcon className="h-3 w-3" />
                  <span>{tag}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex space-x-2 pt-4 border-t border-dark-700">
          {canEnter && (
            <Button
              onClick={() => onEnter?.(campaign.id)}
              variant="primary"
              className="flex-1"
            >
              Enter Campaign
            </Button>
          )}
          
          {canJoin && (
            <Button
              onClick={onJoin}
              variant="secondary"
              className="flex-1"
            >
              Join Campaign
            </Button>
          )}
          
          {canLeave && (
            <Button
              onClick={() => onLeave?.(campaign.id)}
              variant="outline"
              className="flex-1"
            >
              Leave Campaign
            </Button>
          )}
          
          {!canJoin && !canLeave && !canEnter && campaign.status !== CampaignStatus.ACTIVE && (
            <div className="flex-1 text-center text-gray-500 text-sm py-2">
              Campaign is not active
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
};

export default CampaignCard;
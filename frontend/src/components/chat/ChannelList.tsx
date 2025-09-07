/**
 * ShadowRealms AI - Channel List Component
 * 
 * This component displays the list of available chat channels.
 * It shows channel information, unread counts, and provides navigation.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays available chat channels with their information
 * 2. Shows unread message counts and indicators
 * 3. Provides channel selection and navigation
 * 4. Groups channels by type (General, OOC, etc.)
 * 5. Handles channel creation and management
 */

import React from 'react';
import { motion } from 'framer-motion';
import { 
  ChatBubbleLeftRightIcon,
  UserGroupIcon,
  LockClosedIcon,
  PlusIcon,
  HashtagIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline';

// Import types
import { ChatChannel, ChannelType } from '../../types/chat';

/**
 * Channel List Props Interface
 * Defines the props that the ChannelList component accepts
 */
interface ChannelListProps {
  channels: ChatChannel[];
  currentChannel: ChatChannel | null;
  onChannelSelect: (channel: ChatChannel) => void;
}

/**
 * Get channel type icon and color
 * @param type - Channel type
 * @returns Object with icon component and color classes
 */
const getChannelTypeInfo = (type: ChannelType) => {
  switch (type) {
    case ChannelType.GENERAL:
      return {
        icon: HashtagIcon,
        color: 'text-gray-400',
        bgColor: 'bg-gray-900/30',
        label: 'General'
      };
    case ChannelType.OOC:
      return {
        icon: ChatBubbleLeftRightIcon,
        color: 'text-blue-400',
        bgColor: 'bg-blue-900/30',
        label: 'OOC'
      };
    case ChannelType.PRIVATE:
      return {
        icon: LockClosedIcon,
        color: 'text-red-400',
        bgColor: 'bg-red-900/30',
        label: 'Private'
      };
    case ChannelType.SYSTEM:
      return {
        icon: ExclamationTriangleIcon,
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/30',
        label: 'System'
      };
    case ChannelType.LOCATION:
      return {
        icon: EyeIcon,
        color: 'text-green-400',
        bgColor: 'bg-green-900/30',
        label: 'Location'
      };
    case ChannelType.RULES:
      return {
        icon: EyeSlashIcon,
        color: 'text-purple-400',
        bgColor: 'bg-purple-900/30',
        label: 'Rules'
      };
    default:
      return {
        icon: HashtagIcon,
        color: 'text-gray-400',
        bgColor: 'bg-gray-900/30',
        label: 'Unknown'
      };
  }
};

/**
 * Format last message timestamp
 * @param timestamp - ISO timestamp
 * @returns Formatted time string
 */
const formatLastMessage = (timestamp: string) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) {
    return 'Just now';
  } else if (diffMins < 60) {
    return `${diffMins}m`;
  } else if (diffHours < 24) {
    return `${diffHours}h`;
  } else if (diffDays < 7) {
    return `${diffDays}d`;
  } else {
    return date.toLocaleDateString();
  }
};

/**
 * Channel Item Component
 * Individual channel display component
 */
const ChannelItem: React.FC<{ 
  channel: ChatChannel; 
  isSelected: boolean; 
  index: number;
  onClick: () => void;
}> = ({ channel, isSelected, index, onClick }) => {
  const typeInfo = getChannelTypeInfo(channel.type);
  const TypeIcon = typeInfo.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={`flex items-center space-x-3 p-3 rounded-lg cursor-pointer transition-all duration-200 ${
        isSelected 
          ? 'bg-primary-900/30 border border-primary-500/30' 
          : 'hover:bg-dark-700/50'
      }`}
      onClick={onClick}
    >
      {/* Channel Icon */}
      <div className={`flex-shrink-0 p-2 rounded-lg ${typeInfo.bgColor}`}>
        <TypeIcon className={`h-4 w-4 ${typeInfo.color}`} />
      </div>

      {/* Channel Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className={`font-medium text-sm truncate ${
              isSelected ? 'text-primary-300' : 'text-white'
            }`}>
              {channel.name}
            </span>
            
            {/* Private Indicator */}
            {channel.isPrivate && (
              <LockClosedIcon className="h-3 w-3 text-gray-500" />
            )}
          </div>

          {/* Last Message Time */}
          {channel.lastMessageAt && (
            <span className="text-xs text-gray-500">
              {formatLastMessage(channel.lastMessageAt)}
            </span>
          )}
        </div>

        {/* Channel Description */}
        {channel.description && (
          <p className="text-xs text-gray-400 truncate mt-1">
            {channel.description}
          </p>
        )}

        {/* Channel Type and Participants */}
        <div className="flex items-center space-x-2 mt-1">
          <span className={`text-xs px-2 py-1 rounded-full ${typeInfo.bgColor} ${typeInfo.color}`}>
            {typeInfo.label}
          </span>
          <span className="text-xs text-gray-500">
            {channel.participants.length} participants
          </span>
        </div>
      </div>

      {/* Unread Count */}
      {channel.unreadCount > 0 && (
        <div className="flex-shrink-0">
          <div className="bg-primary-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
            {channel.unreadCount > 99 ? '99+' : channel.unreadCount}
          </div>
        </div>
      )}
    </motion.div>
  );
};

/**
 * Channel List Component
 * Main component for displaying chat channels
 */
const ChannelList: React.FC<ChannelListProps> = ({ 
  channels, 
  currentChannel, 
  onChannelSelect 
}) => {
  // Group channels by type
  const groupedChannels = channels.reduce((groups, channel) => {
    const type = channel.type;
    if (!groups[type]) {
      groups[type] = [];
    }
    groups[type].push(channel);
    return groups;
  }, {} as Record<ChannelType, ChatChannel[]>);

  // Sort channels within each group by name
  Object.keys(groupedChannels).forEach(type => {
    groupedChannels[type as ChannelType].sort((a, b) => a.name.localeCompare(b.name));
  });

  // Define channel type order for display
  const channelTypeOrder = [
    ChannelType.GENERAL,
    ChannelType.LOCATION,
    ChannelType.OOC,
    ChannelType.RULES,
    ChannelType.PRIVATE,
    ChannelType.SYSTEM
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-dark-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
            <ChatBubbleLeftRightIcon className="h-5 w-5 text-primary-400" />
            <span>Channels</span>
          </h3>
          <button className="text-gray-400 hover:text-white transition-colors">
            <PlusIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Channels List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-dark-600 scrollbar-track-dark-800">
        <div className="p-4 space-y-6">
          {channelTypeOrder.map(type => {
            const typeChannels = groupedChannels[type];
            if (!typeChannels || typeChannels.length === 0) return null;

            const typeInfo = getChannelTypeInfo(type);
            const TypeIcon = typeInfo.icon;

            return (
              <div key={type}>
                <h4 className="text-sm font-medium text-gray-400 mb-3 flex items-center space-x-2">
                  <TypeIcon className={`h-4 w-4 ${typeInfo.color}`} />
                  <span>{typeInfo.label} ({typeChannels.length})</span>
                </h4>
                <div className="space-y-2">
                  {typeChannels.map((channel, index) => (
                    <ChannelItem
                      key={channel.id}
                      channel={channel}
                      isSelected={currentChannel?.id === channel.id}
                      index={index}
                      onClick={() => onChannelSelect(channel)}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          {/* Empty State */}
          {channels.length === 0 && (
            <div className="text-center py-8">
              <ChatBubbleLeftRightIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-500 text-sm mb-2">No channels available</p>
              <p className="text-gray-600 text-xs">
                Channels will appear here when they are created
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChannelList;

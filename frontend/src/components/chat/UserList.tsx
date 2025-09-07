/**
 * ShadowRealms AI - User List Component
 * 
 * This component displays the list of online users in the chat.
 * It shows user status, avatars, and provides user interaction options.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays online users with their status indicators
 * 2. Shows user avatars and names
 * 3. Indicates user roles (GM, Player, Helper)
 * 4. Provides user status information
 * 5. Handles user interactions and context menus
 */

import React from 'react';
import { motion } from 'framer-motion';
import { 
  UserIcon,
  CrownIcon,
  ShieldCheckIcon,
  UserGroupIcon
} from '@heroicons/react/24/outline';

// Import types
import { ChatUser, UserStatus } from '../../types/chat';

/**
 * User List Props Interface
 * Defines the props that the UserList component accepts
 */
interface UserListProps {
  users: ChatUser[];
  currentUserId?: string;
}

/**
 * Get status color and indicator for user status
 * @param status - User status
 * @returns Object with color classes and indicator
 */
const getStatusInfo = (status: UserStatus) => {
  switch (status) {
    case UserStatus.ONLINE:
      return {
        color: 'text-green-400',
        bgColor: 'bg-green-500',
        indicator: '●',
        label: 'Online'
      };
    case UserStatus.AWAY:
      return {
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-500',
        indicator: '◐',
        label: 'Away'
      };
    case UserStatus.BUSY:
      return {
        color: 'text-red-400',
        bgColor: 'bg-red-500',
        indicator: '●',
        label: 'Busy'
      };
    case UserStatus.OFFLINE:
      return {
        color: 'text-gray-400',
        bgColor: 'bg-gray-500',
        indicator: '○',
        label: 'Offline'
      };
    default:
      return {
        color: 'text-gray-400',
        bgColor: 'bg-gray-500',
        indicator: '○',
        label: 'Unknown'
      };
  }
};

/**
 * Get role information and styling
 * @param role - User role
 * @returns Object with role styling and icon
 */
const getRoleInfo = (role: string) => {
  switch (role) {
    case 'gm':
      return {
        icon: CrownIcon,
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/30',
        label: 'Game Master'
      };
    case 'helper':
      return {
        icon: ShieldCheckIcon,
        color: 'text-blue-400',
        bgColor: 'bg-blue-900/30',
        label: 'Helper'
      };
    case 'player':
    default:
      return {
        icon: UserGroupIcon,
        color: 'text-green-400',
        bgColor: 'bg-green-900/30',
        label: 'Player'
      };
  }
};

/**
 * Format last seen time
 * @param lastSeen - ISO timestamp string
 * @returns Formatted relative time string
 */
const formatLastSeen = (lastSeen: string): string => {
  const now = new Date();
  const lastSeenDate = new Date(lastSeen);
  const diffInMinutes = Math.floor((now.getTime() - lastSeenDate.getTime()) / (1000 * 60));
  
  if (diffInMinutes < 1) return 'just now';
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
  if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
  return `${Math.floor(diffInMinutes / 1440)}d ago`;
};

/**
 * User Item Component
 * Displays a single user with their information and status
 */
const UserItem: React.FC<{ user: ChatUser; index: number; isCurrentUser: boolean }> = ({ 
  user, 
  index, 
  isCurrentUser 
}) => {
  const statusInfo = getStatusInfo(user.status);
  const roleInfo = getRoleInfo(user.role);
  const RoleIcon = roleInfo.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={`flex items-center space-x-3 p-3 rounded-lg transition-colors ${
        isCurrentUser 
          ? 'bg-primary-900/30 border border-primary-500/30'
          : 'hover:bg-dark-700/50'
      }`}
    >
      {/* Avatar */}
      <div className="flex-shrink-0 relative">
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={user.username}
            className="h-8 w-8 rounded-full object-cover"
          />
        ) : (
          <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center">
            <UserIcon className="h-5 w-5 text-white" />
          </div>
        )}
        
        {/* Status Indicator */}
        <div className={`absolute -bottom-1 -right-1 h-3 w-3 rounded-full border-2 border-dark-800 ${statusInfo.bgColor}`} />
      </div>

      {/* User Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-gray-200 truncate">
            {user.username}
            {isCurrentUser && <span className="text-primary-400 ml-1">(You)</span>}
          </span>
          
          {/* Role Badge */}
          <div className={`flex items-center space-x-1 px-2 py-1 rounded-full ${roleInfo.bgColor}`}>
            <RoleIcon className={`h-3 w-3 ${roleInfo.color}`} />
            <span className={`text-xs font-medium ${roleInfo.color}`}>
              {roleInfo.label}
            </span>
          </div>
        </div>
        
        {/* Character Name */}
        {user.characterName && (
          <div className="text-xs text-gray-400 mt-1">
            as {user.characterName}
          </div>
        )}
        
        {/* Status and Last Seen */}
        <div className="flex items-center space-x-2 mt-1">
          <span className={`text-xs ${statusInfo.color}`}>
            {statusInfo.indicator} {statusInfo.label}
          </span>
          {user.status === UserStatus.OFFLINE && (
            <span className="text-xs text-gray-500">
              {formatLastSeen(user.lastSeen)}
            </span>
          )}
        </div>
      </div>

      {/* Typing Indicator */}
      {user.isTyping && (
        <div className="flex space-x-1">
          <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce"></div>
          <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
          <div className="w-1 h-1 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
        </div>
      )}
    </motion.div>
  );
};

/**
 * User List Component
 * Displays a list of users with their status and information
 */
const UserList: React.FC<UserListProps> = ({ users, currentUserId }) => {
  // Group users by status
  const onlineUsers = users.filter(user => user.status === UserStatus.ONLINE);
  const awayUsers = users.filter(user => user.status === UserStatus.AWAY);
  const busyUsers = users.filter(user => user.status === UserStatus.BUSY);
  const offlineUsers = users.filter(user => user.status === UserStatus.OFFLINE);

  // Sort users by role (GM first, then helpers, then players)
  const sortUsers = (userList: ChatUser[]) => {
    return userList.sort((a, b) => {
      const roleOrder = { gm: 0, helper: 1, player: 2 };
      const aOrder = roleOrder[a.role as keyof typeof roleOrder] ?? 2;
      const bOrder = roleOrder[b.role as keyof typeof roleOrder] ?? 2;
      return aOrder - bOrder;
    });
  };

  const sortedOnlineUsers = sortUsers(onlineUsers);
  const sortedAwayUsers = sortUsers(awayUsers);
  const sortedBusyUsers = sortUsers(busyUsers);
  const sortedOfflineUsers = sortUsers(offlineUsers);

  if (users.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-center p-8">
        <div>
          <UserGroupIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-400 mb-2">No users online</h3>
          <p className="text-gray-500">
            Users will appear here when they join the channel
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-dark-700">
        <h3 className="text-lg font-semibold text-primary-300">
          Users ({users.length})
        </h3>
        <div className="text-sm text-gray-400 mt-1">
          Online ({onlineUsers.length})
        </div>
      </div>

      {/* User Lists */}
      <div className="flex-1 overflow-y-auto p-2 space-y-4">
        {/* Online Users */}
        {sortedOnlineUsers.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2 px-2">
              Online ({sortedOnlineUsers.length})
            </div>
            <div className="space-y-1">
              {sortedOnlineUsers.map((user, index) => (
                <UserItem
                  key={user.id}
                  user={user}
                  index={index}
                  isCurrentUser={user.id === currentUserId}
                />
              ))}
            </div>
          </div>
        )}

        {/* Away Users */}
        {sortedAwayUsers.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2 px-2">
              Away ({sortedAwayUsers.length})
            </div>
            <div className="space-y-1">
              {sortedAwayUsers.map((user, index) => (
                <UserItem
                  key={user.id}
                  user={user}
                  index={index}
                  isCurrentUser={user.id === currentUserId}
                />
              ))}
            </div>
          </div>
        )}

        {/* Busy Users */}
        {sortedBusyUsers.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2 px-2">
              Busy ({sortedBusyUsers.length})
            </div>
            <div className="space-y-1">
              {sortedBusyUsers.map((user, index) => (
                <UserItem
                  key={user.id}
                  user={user}
                  index={index}
                  isCurrentUser={user.id === currentUserId}
                />
              ))}
            </div>
          </div>
        )}

        {/* Offline Users */}
        {sortedOfflineUsers.length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-500 mb-2 px-2">
              Offline ({sortedOfflineUsers.length})
            </div>
            <div className="space-y-1">
              {sortedOfflineUsers.map((user, index) => (
                <UserItem
                  key={user.id}
                  user={user}
                  index={index}
                  isCurrentUser={user.id === currentUserId}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UserList;
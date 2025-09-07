/**
 * ShadowRealms AI - User List Component Tests
 * 
 * This test file covers the UserList component functionality including:
 * - Rendering online users correctly
 * - Displaying user status indicators
 * - Showing user roles and information
 * - Handling different user statuses
 * - Proper user grouping and sorting
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { motion } from 'framer-motion';
import UserList from '../../../components/chat/UserList';
import { ChatUser, UserStatus } from '../../../types/chat';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  UserIcon: ({ className }: any) => <div data-testid="user-icon" className={className} />,
  CrownIcon: ({ className }: any) => <div data-testid="crown-icon" className={className} />,
  ShieldCheckIcon: ({ className }: any) => <div data-testid="shield-check-icon" className={className} />,
  UserGroupIcon: ({ className }: any) => <div data-testid="user-group-icon" className={className} />,
}));

// Mock users data
const mockUsers: ChatUser[] = [
  {
    id: 'user1',
    username: 'TestUser',
    status: UserStatus.ONLINE,
    lastSeen: '2023-01-01T12:00:00Z',
    isTyping: false,
    role: 'player'
  },
  {
    id: 'user2',
    username: 'GameMaster',
    status: UserStatus.ONLINE,
    lastSeen: '2023-01-01T12:00:00Z',
    isTyping: true,
    role: 'gm',
    characterName: 'GM Character'
  },
  {
    id: 'user3',
    username: 'AwayUser',
    status: UserStatus.AWAY,
    lastSeen: '2023-01-01T11:30:00Z',
    isTyping: false,
    role: 'player'
  },
  {
    id: 'user4',
    username: 'BusyUser',
    status: UserStatus.BUSY,
    lastSeen: '2023-01-01T11:00:00Z',
    isTyping: false,
    role: 'helper'
  },
  {
    id: 'user5',
    username: 'OfflineUser',
    status: UserStatus.OFFLINE,
    lastSeen: '2023-01-01T10:00:00Z',
    isTyping: false,
    role: 'player'
  }
];

const mockProps = {
  users: mockUsers,
  currentUserId: 'user1'
};

describe('UserList', () => {
  it('renders all users correctly', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('TestUser')).toBeInTheDocument();
    expect(screen.getByText('GameMaster')).toBeInTheDocument();
    expect(screen.getByText('AwayUser')).toBeInTheDocument();
    expect(screen.getByText('BusyUser')).toBeInTheDocument();
    expect(screen.getByText('OfflineUser')).toBeInTheDocument();
  });

  it('displays user count in header', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('Users (5)')).toBeInTheDocument();
  });

  it('shows current user indicator', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('TestUser (You)')).toBeInTheDocument();
  });

  it('displays user roles correctly', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('Player')).toBeInTheDocument();
    expect(screen.getByText('Game Master')).toBeInTheDocument();
    expect(screen.getByText('Helper')).toBeInTheDocument();
  });

  it('shows character names when available', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('as GM Character')).toBeInTheDocument();
  });

  it('displays correct status indicators', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('● Online')).toBeInTheDocument();
    expect(screen.getByText('◐ Away')).toBeInTheDocument();
    expect(screen.getByText('● Busy')).toBeInTheDocument();
    expect(screen.getByText('○ Offline')).toBeInTheDocument();
  });

  it('shows typing indicator for typing users', () => {
    render(<UserList {...mockProps} />);
    
    // Should show typing animation dots for GameMaster
    const typingDots = screen.getAllByText('●');
    expect(typingDots.length).toBeGreaterThan(0);
  });

  it('groups users by status correctly', () => {
    render(<UserList {...mockProps} />);
    
    expect(screen.getByText('Online (2)')).toBeInTheDocument();
    expect(screen.getByText('Away (1)')).toBeInTheDocument();
    expect(screen.getByText('Busy (1)')).toBeInTheDocument();
    expect(screen.getByText('Offline (1)')).toBeInTheDocument();
  });

  it('sorts users by role (GM first, then helpers, then players)', () => {
    render(<UserList {...mockProps} />);
    
    const userElements = screen.getAllByText(/TestUser|GameMaster|AwayUser|BusyUser|OfflineUser/);
    
    // GameMaster should appear first (GM role)
    expect(userElements[0]).toHaveTextContent('GameMaster');
  });

  it('shows empty state when no users', () => {
    const emptyProps = { ...mockProps, users: [] };
    render(<UserList {...emptyProps} />);
    
    expect(screen.getByText('No users online')).toBeInTheDocument();
  });

  it('displays last seen time for offline users', () => {
    render(<UserList {...mockProps} />);
    
    // Should show relative time for offline users
    expect(screen.getByText(/ago/)).toBeInTheDocument();
  });

  it('handles users with avatars', () => {
    const usersWithAvatars: ChatUser[] = [
      {
        id: 'user1',
        username: 'AvatarUser',
        avatar: 'https://example.com/avatar.jpg',
        status: UserStatus.ONLINE,
        lastSeen: '2023-01-01T12:00:00Z',
        isTyping: false,
        role: 'player'
      }
    ];
    
    const props = { ...mockProps, users: usersWithAvatars };
    render(<UserList {...props} />);
    
    const avatar = screen.getByAltText('AvatarUser');
    expect(avatar).toHaveAttribute('src', 'https://example.com/avatar.jpg');
  });

  it('shows correct status colors', () => {
    render(<UserList {...mockProps} />);
    
    const onlineStatus = screen.getByText('● Online');
    expect(onlineStatus).toHaveClass('text-green-400');
    
    const awayStatus = screen.getByText('◐ Away');
    expect(awayStatus).toHaveClass('text-yellow-400');
    
    const busyStatus = screen.getByText('● Busy');
    expect(busyStatus).toHaveClass('text-red-400');
    
    const offlineStatus = screen.getByText('○ Offline');
    expect(offlineStatus).toHaveClass('text-gray-400');
  });

  it('displays role badges with correct colors', () => {
    render(<UserList {...mockProps} />);
    
    const gmBadge = screen.getByText('Game Master');
    expect(gmBadge).toHaveClass('text-yellow-400');
    
    const helperBadge = screen.getByText('Helper');
    expect(helperBadge).toHaveClass('text-blue-400');
    
    const playerBadge = screen.getByText('Player');
    expect(playerBadge).toHaveClass('text-green-400');
  });

  it('handles hover interactions correctly', () => {
    render(<UserList {...mockProps} />);
    
    const userItem = screen.getByText('TestUser').closest('div');
    expect(userItem).toHaveClass('hover:bg-dark-700/50');
  });

  it('shows current user with special styling', () => {
    render(<UserList {...mockProps} />);
    
    const currentUserItem = screen.getByText('TestUser (You)').closest('div');
    expect(currentUserItem).toHaveClass('bg-primary-900/30');
  });

  it('displays correct online user count', () => {
    render(<UserList {...mockProps} />);
    
    // Should count only online users
    const onlineUsers = mockUsers.filter(user => user.status === UserStatus.ONLINE);
    expect(screen.getByText(`Online (${onlineUsers.length})`)).toBeInTheDocument();
  });
});

/**
 * ShadowRealms AI - Campaign Card Component Tests
 * 
 * This test file covers the CampaignCard component functionality including:
 * - Rendering campaign information correctly
 * - Displaying appropriate status indicators
 * - Handling user interactions (join, leave, enter)
 * - Showing correct action buttons based on user role
 * - Proper visual feedback for different campaign states
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { motion } from 'framer-motion';
import CampaignCard from '../../../components/campaign/CampaignCard';
import { Campaign, CampaignStatus, CampaignVisibility, RPGSystem } from '../../../types/campaign';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  PlusIcon: ({ className }: any) => <div data-testid="plus-icon" className={className} />,
  UserGroupIcon: ({ className }: any) => <div data-testid="user-group-icon" className={className} />,
  CalendarIcon: ({ className }: any) => <div data-testid="calendar-icon" className={className} />,
  ClockIcon: ({ className }: any) => <div data-testid="clock-icon" className={className} />,
  TagIcon: ({ className }: any) => <div data-testid="tag-icon" className={className} />,
}));

// Mock campaign data
const mockCampaign: Campaign = {
  id: '1',
  name: 'Test Campaign',
  description: 'A test campaign for unit testing',
  system: RPGSystem.DND_5E,
  status: CampaignStatus.ACTIVE,
  visibility: CampaignVisibility.PUBLIC,
  gameMaster: {
    id: 'gm1',
    username: 'TestGM',
    email: 'gm@test.com',
    experience: 5,
    specialties: ['D&D 5e', 'World Building']
  },
  gameMasterId: 'gm1',
  players: [
    {
      id: 'player1',
      username: 'TestPlayer',
      email: 'player@test.com',
      role: 'player',
      joinedAt: '2023-01-01T00:00:00Z',
      isOnline: true,
      characterCount: 1
    }
  ],
  maxPlayers: 6,
  setting: 'Forgotten Realms',
  theme: 'Adventure',
  tags: ['beginner-friendly', 'roleplay-heavy'],
  settings: {
    aiAssistance: true,
    aiPersonality: 'helpful',
    aiResponseLength: 'medium',
    maxPlayers: 6,
    allowSpectators: true,
    requireApproval: false,
    enableOOC: true,
    enablePrivateMessages: true,
    enableDiceRolls: true,
    timezone: 'UTC',
    language: 'en'
  },
  stats: {
    totalSessions: 10,
    totalPlayTime: 50,
    totalMessages: 500,
    averageSessionLength: 5,
    lastSessionAt: '2023-01-15T20:00:00Z',
    playerRetention: 85
  },
  createdAt: '2023-01-01T00:00:00Z',
  updatedAt: '2023-01-15T20:00:00Z'
};

const mockProps = {
  campaign: mockCampaign,
  currentUserId: 'player1',
  onJoin: jest.fn(),
  onLeave: jest.fn(),
  onEnter: jest.fn()
};

describe('CampaignCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders campaign information correctly', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('Test Campaign')).toBeInTheDocument();
    expect(screen.getByText('A test campaign for unit testing')).toBeInTheDocument();
    expect(screen.getByText('Forgotten Realms')).toBeInTheDocument();
    expect(screen.getByText('Adventure')).toBeInTheDocument();
    expect(screen.getByText('TestGM')).toBeInTheDocument();
  });

  it('displays correct status indicator for active campaign', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('displays correct visibility indicator for public campaign', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('Public')).toBeInTheDocument();
  });

  it('shows player count correctly', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('1 / 6 players')).toBeInTheDocument();
  });

  it('displays campaign tags', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('beginner-friendly')).toBeInTheDocument();
    expect(screen.getByText('roleplay-heavy')).toBeInTheDocument();
  });

  it('shows correct action buttons for a player in the campaign', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('Enter Campaign')).toBeInTheDocument();
    expect(screen.getByText('Leave Campaign')).toBeInTheDocument();
  });

  it('shows correct action buttons for a non-player', () => {
    const props = { ...mockProps, currentUserId: 'other-user' };
    render(<CampaignCard {...props} />);
    
    expect(screen.getByText('Join Campaign')).toBeInTheDocument();
  });

  it('shows correct action buttons for the game master', () => {
    const props = { ...mockProps, currentUserId: 'gm1' };
    render(<CampaignCard {...props} />);
    
    expect(screen.getByText('Enter Campaign')).toBeInTheDocument();
    expect(screen.getByText('Leave Campaign')).toBeInTheDocument();
  });

  it('calls onEnter when Enter Campaign button is clicked', () => {
    render(<CampaignCard {...mockProps} />);
    
    const enterButton = screen.getByText('Enter Campaign');
    fireEvent.click(enterButton);
    
    expect(mockProps.onEnter).toHaveBeenCalledWith('1');
  });

  it('calls onJoin when Join Campaign button is clicked', () => {
    const props = { ...mockProps, currentUserId: 'other-user' };
    render(<CampaignCard {...props} />);
    
    const joinButton = screen.getByText('Join Campaign');
    fireEvent.click(joinButton);
    
    expect(mockProps.onJoin).toHaveBeenCalled();
  });

  it('calls onLeave when Leave Campaign button is clicked', () => {
    render(<CampaignCard {...mockProps} />);
    
    const leaveButton = screen.getByText('Leave Campaign');
    fireEvent.click(leaveButton);
    
    expect(mockProps.onLeave).toHaveBeenCalledWith('1');
  });

  it('shows full indicator when campaign is full', () => {
    const fullCampaign = {
      ...mockCampaign,
      players: Array(6).fill(null).map((_, i) => ({
        id: `player${i}`,
        username: `Player${i}`,
        email: `player${i}@test.com`,
        role: 'player' as const,
        joinedAt: '2023-01-01T00:00:00Z',
        isOnline: true,
        characterCount: 1
      }))
    };
    
    const props = { ...mockProps, campaign: fullCampaign, currentUserId: 'other-user' };
    render(<CampaignCard {...props} />);
    
    expect(screen.getByText('(Full)')).toBeInTheDocument();
  });

  it('shows appropriate message when campaign is not active', () => {
    const inactiveCampaign = { ...mockCampaign, status: CampaignStatus.PAUSED };
    const props = { ...mockProps, campaign: inactiveCampaign, currentUserId: 'other-user' };
    render(<CampaignCard {...props} />);
    
    expect(screen.getByText('Campaign is not active')).toBeInTheDocument();
  });

  it('displays RPG system correctly', () => {
    render(<CampaignCard {...mockProps} />);
    
    expect(screen.getByText('DND 5E')).toBeInTheDocument();
  });

  it('shows character name when player has a character', () => {
    const campaignWithCharacter = {
      ...mockCampaign,
      players: [{
        ...mockCampaign.players[0],
        characterName: 'TestCharacter'
      }]
    };
    
    const props = { ...mockProps, campaign: campaignWithCharacter };
    render(<CampaignCard {...props} />);
    
    expect(screen.getByText('TestCharacter')).toBeInTheDocument();
  });

  it('handles hover interactions correctly', () => {
    render(<CampaignCard {...mockProps} />);
    
    const card = screen.getByText('Test Campaign').closest('div');
    expect(card).toHaveClass('hover:border-primary-500/50');
  });

  it('displays correct status color for different campaign statuses', () => {
    const { rerender } = render(<CampaignCard {...mockProps} />);
    expect(screen.getByText('Active')).toHaveClass('text-green-400');
    
    const pausedCampaign = { ...mockCampaign, status: CampaignStatus.PAUSED };
    rerender(<CampaignCard {...mockProps} campaign={pausedCampaign} />);
    expect(screen.getByText('Paused')).toHaveClass('text-yellow-400');
    
    const completedCampaign = { ...mockCampaign, status: CampaignStatus.COMPLETED };
    rerender(<CampaignCard {...mockProps} campaign={completedCampaign} />);
    expect(screen.getByText('Completed')).toHaveClass('text-blue-400');
  });
});

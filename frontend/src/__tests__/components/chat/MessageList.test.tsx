/**
 * ShadowRealms AI - Message List Component Tests
 * 
 * This test file covers the MessageList component functionality including:
 * - Rendering messages correctly
 * - Displaying different message types
 * - Showing user information and timestamps
 * - Handling typing indicators
 * - Proper message grouping and formatting
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { motion, AnimatePresence } from 'framer-motion';
import MessageList from '../../../components/chat/MessageList';
import { ChatMessage, MessageType } from '../../../types/chat';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => children,
}));

// Mock Heroicons
jest.mock('@heroicons/react/24/outline', () => ({
  UserIcon: ({ className }: any) => <div data-testid="user-icon" className={className} />,
  ChatBubbleLeftRightIcon: ({ className }: any) => <div data-testid="chat-bubble-icon" className={className} />,
  ExclamationTriangleIcon: ({ className }: any) => <div data-testid="exclamation-icon" className={className} />,
}));

// Mock messages data
const mockMessages: ChatMessage[] = [
  {
    id: '1',
    channelId: 'channel1',
    userId: 'user1',
    username: 'TestUser',
    content: 'Hello, this is a test message',
    type: MessageType.TEXT,
    timestamp: '2023-01-01T12:00:00Z',
    mentions: [],
    reactions: []
  },
  {
    id: '2',
    channelId: 'channel1',
    userId: 'user2',
    username: 'AnotherUser',
    content: 'This is a system message',
    type: MessageType.SYSTEM,
    timestamp: '2023-01-01T12:01:00Z',
    mentions: [],
    reactions: []
  },
  {
    id: '3',
    channelId: 'channel1',
    userId: 'user1',
    username: 'TestUser',
    content: 'This is a dice roll',
    type: MessageType.DICE_ROLL,
    timestamp: '2023-01-01T12:02:00Z',
    mentions: [],
    reactions: [],
    metadata: {
      diceRoll: {
        formula: '1d20+5',
        results: [15],
        total: 20,
        critical: false
      }
    }
  }
];

const mockProps = {
  messages: mockMessages,
  typingUsers: ['user3'],
  messagesEndRef: { current: null }
};

describe('MessageList', () => {
  it('renders messages correctly', () => {
    render(<MessageList {...mockProps} />);
    
    expect(screen.getByText('Hello, this is a test message')).toBeInTheDocument();
    expect(screen.getByText('This is a system message')).toBeInTheDocument();
    expect(screen.getByText('This is a dice roll')).toBeInTheDocument();
  });

  it('displays usernames correctly', () => {
    render(<MessageList {...mockProps} />);
    
    expect(screen.getByText('TestUser')).toBeInTheDocument();
    expect(screen.getByText('AnotherUser')).toBeInTheDocument();
  });

  it('shows message timestamps', () => {
    render(<MessageList {...mockProps} />);
    
    // Timestamps should be formatted and displayed
    expect(screen.getByText('12:00')).toBeInTheDocument();
    expect(screen.getByText('12:01')).toBeInTheDocument();
    expect(screen.getByText('12:02')).toBeInTheDocument();
  });

  it('displays system messages with correct styling', () => {
    render(<MessageList {...mockProps} />);
    
    const systemMessage = screen.getByText('This is a system message');
    expect(systemMessage).toHaveClass('text-yellow-400');
  });

  it('displays dice roll messages with correct styling', () => {
    render(<MessageList {...mockProps} />);
    
    const diceMessage = screen.getByText('This is a dice roll');
    expect(diceMessage).toHaveClass('text-green-400');
  });

  it('shows dice roll metadata when available', () => {
    render(<MessageList {...mockProps} />);
    
    expect(screen.getByText('1d20+5 = 20')).toBeInTheDocument();
    expect(screen.getByText('Rolls: 15')).toBeInTheDocument();
  });

  it('displays typing indicator when users are typing', () => {
    render(<MessageList {...mockProps} />);
    
    expect(screen.getByText('user3 is typing')).toBeInTheDocument();
  });

  it('shows empty state when no messages', () => {
    const emptyProps = { ...mockProps, messages: [] };
    render(<MessageList {...emptyProps} />);
    
    expect(screen.getByText('No Messages Yet')).toBeInTheDocument();
    expect(screen.getByText('Be the first to send a message in this channel')).toBeInTheDocument();
  });

  it('groups consecutive messages from same user', () => {
    const consecutiveMessages: ChatMessage[] = [
      {
        id: '1',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'First message',
        type: MessageType.TEXT,
        timestamp: '2023-01-01T12:00:00Z',
        mentions: [],
        reactions: []
      },
      {
        id: '2',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Second message',
        type: MessageType.TEXT,
        timestamp: '2023-01-01T12:00:30Z',
        mentions: [],
        reactions: []
      }
    ];
    
    const props = { ...mockProps, messages: consecutiveMessages };
    render(<MessageList {...props} />);
    
    // Should only show one avatar for the grouped messages
    const avatars = screen.getAllByText('TestUser');
    expect(avatars).toHaveLength(2); // One for each message content
  });

  it('displays message reactions when available', () => {
    const messageWithReactions: ChatMessage[] = [
      {
        id: '1',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Message with reactions',
        type: MessageType.TEXT,
        timestamp: '2023-01-01T12:00:00Z',
        mentions: [],
        reactions: [
          {
            emoji: '👍',
            userId: 'user2',
            username: 'AnotherUser',
            timestamp: '2023-01-01T12:01:00Z'
          }
        ]
      }
    ];
    
    const props = { ...mockProps, messages: messageWithReactions };
    render(<MessageList {...props} />);
    
    expect(screen.getByText('👍')).toBeInTheDocument();
    expect(screen.getByText('AnotherUser')).toBeInTheDocument();
  });

  it('shows edit indicator for edited messages', () => {
    const editedMessage: ChatMessage[] = [
      {
        id: '1',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Edited message',
        type: MessageType.TEXT,
        timestamp: '2023-01-01T12:00:00Z',
        editedAt: '2023-01-01T12:01:00Z',
        mentions: [],
        reactions: []
      }
    ];
    
    const props = { ...mockProps, messages: editedMessage };
    render(<MessageList {...props} />);
    
    expect(screen.getByText('(edited)')).toBeInTheDocument();
  });

  it('handles different message types with correct icons', () => {
    const variousMessageTypes: ChatMessage[] = [
      {
        id: '1',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'OOC message',
        type: MessageType.OOC,
        timestamp: '2023-01-01T12:00:00Z',
        mentions: [],
        reactions: []
      },
      {
        id: '2',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Whisper message',
        type: MessageType.WHISPER,
        timestamp: '2023-01-01T12:01:00Z',
        mentions: [],
        reactions: []
      },
      {
        id: '3',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Action message',
        type: MessageType.ACTION,
        timestamp: '2023-01-01T12:02:00Z',
        mentions: [],
        reactions: []
      }
    ];
    
    const props = { ...mockProps, messages: variousMessageTypes };
    render(<MessageList {...props} />);
    
    expect(screen.getByText('[OOC]')).toBeInTheDocument();
    expect(screen.getByText('[WHISPER]')).toBeInTheDocument();
    expect(screen.getByText('[ACTION]')).toBeInTheDocument();
  });

  it('displays critical dice roll indicator', () => {
    const criticalDiceMessage: ChatMessage[] = [
      {
        id: '1',
        channelId: 'channel1',
        userId: 'user1',
        username: 'TestUser',
        content: 'Critical roll',
        type: MessageType.DICE_ROLL,
        timestamp: '2023-01-01T12:00:00Z',
        mentions: [],
        reactions: [],
        metadata: {
          diceRoll: {
            formula: '1d20',
            results: [20],
            total: 20,
            critical: true
          }
        }
      }
    ];
    
    const props = { ...mockProps, messages: criticalDiceMessage };
    render(<MessageList {...props} />);
    
    expect(screen.getByText('Critical Success!')).toBeInTheDocument();
  });
});

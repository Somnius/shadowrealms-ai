/**
 * ShadowRealms AI - Chat Interface Component
 * 
 * This component provides the main chat interface for campaigns.
 * It includes message display, input, user list, and real-time functionality.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays chat messages in a scrollable interface
 * 2. Provides message input with typing indicators
 * 3. Shows online users and their status
 * 4. Handles real-time message updates via WebSocket
 * 5. Manages chat channels and navigation
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  PaperAirplaneIcon,
  UserGroupIcon,
  EllipsisVerticalIcon,
  ArrowLeftIcon,
  ChatBubbleLeftRightIcon
} from '@heroicons/react/24/outline';

// Import components and stores
import { useChatStore } from '../../store/chatStore';
import { useCampaignStore } from '../../store/campaignStore';
import { useAuthStore } from '../../store/authStore';
import { chatService } from '../../services/chatService';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import MessageList from './MessageList';
import UserList from './UserList';
import ChannelList from './ChannelList';

// Import types
import { ChatMessage, SendMessageRequest, MessageType } from '../../types/chat';

/**
 * Chat Interface Component
 * Main chat interface for campaigns
 */
const ChatInterface: React.FC = () => {
  const { campaignId } = useParams<{ campaignId: string }>();
  const navigate = useNavigate();
  
  // Store hooks
  const { user } = useAuthStore();
  const { currentCampaign } = useCampaignStore();
  const {
    messages,
    channels,
    currentChannel,
    onlineUsers,
    isLoading,
    error,
    setMessages,
    addMessage,
    setChannels,
    setCurrentChannel,
    setOnlineUsers,
    setLoading,
    setError,
    clearError,
    getMessagesForChannel
  } = useChatStore();

  // Local state
  const [messageInput, setMessageInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showUserList, setShowUserList] = useState(true);
  const [showChannelList, setShowChannelList] = useState(false);
  const [typingUsers, setTypingUsers] = useState<Set<string>>(new Set());
  
  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Load campaign data
  useEffect(() => {
    if (campaignId && !currentCampaign) {
      // Load campaign data if not already loaded
      // This would typically be handled by the campaign store
    }
  }, [campaignId, currentCampaign]);

  // Load chat data
  useEffect(() => {
    if (campaignId) {
      loadChatData();
    }
  }, [campaignId]);

  // Connect to WebSocket
  useEffect(() => {
    if (campaignId && user) {
      connectWebSocket();
    }

    return () => {
      chatService.disconnectWebSocket();
    };
  }, [campaignId, user]);

  /**
   * Load initial chat data
   */
  const loadChatData = async () => {
    if (!campaignId) return;

    try {
      setLoading(true);
      clearError();

      // Load channels and online users in parallel
      const [channelsData, usersData] = await Promise.all([
        chatService.getChannels(campaignId),
        chatService.getOnlineUsers(campaignId)
      ]);

      setChannels(channelsData);
      setOnlineUsers(usersData);

      // Set first channel as current if none selected
      if (channelsData.length > 0 && !currentChannel) {
        setCurrentChannel(channelsData[0]);
      }
    } catch (error) {
      console.error('Failed to load chat data:', error);
      setError('Failed to load chat data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Connect to WebSocket for real-time updates
   */
  const connectWebSocket = () => {
    if (!campaignId || !user) return;

    chatService.connectWebSocket(
      campaignId,
      handleNewMessage,
      handleUserUpdate,
      handleTypingIndicator
    );
  };

  /**
   * Handle new message from WebSocket
   */
  const handleNewMessage = useCallback((message: ChatMessage) => {
    addMessage(message);
    
    // Auto-scroll to bottom if user is at bottom
    if (messagesEndRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = messagesEndRef.current;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 100;
      
      if (isAtBottom) {
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      }
    }
  }, [addMessage]);

  /**
   * Handle user status update from WebSocket
   */
  const handleUserUpdate = useCallback((updatedUser: any) => {
    setOnlineUsers(prev => 
      prev.map(user => user.id === updatedUser.id ? updatedUser : user)
    );
  }, [setOnlineUsers]);

  /**
   * Handle typing indicator from WebSocket
   */
  const handleTypingIndicator = useCallback((typing: { userId: string; username: string; isTyping: boolean }) => {
    setTypingUsers(prev => {
      const newSet = new Set(prev);
      if (typing.isTyping) {
        newSet.add(typing.userId);
      } else {
        newSet.delete(typing.userId);
      }
      return newSet;
    });
  }, []);

  /**
   * Handle message input change
   */
  const handleMessageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setMessageInput(value);

    // Send typing indicator
    if (currentChannel) {
      if (!isTyping && value.length > 0) {
        setIsTyping(true);
        chatService.sendTypingIndicator(currentChannel.id, true);
      }

      // Clear existing timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }

      // Set new timeout to stop typing indicator
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        chatService.sendTypingIndicator(currentChannel.id, false);
      }, 1000);
    }
  };

  /**
   * Handle message send
   */
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!messageInput.trim() || !currentChannel || !user) return;

    try {
      const messageRequest: SendMessageRequest = {
        channelId: currentChannel.id,
        content: messageInput.trim(),
        type: MessageType.TEXT
      };

      // Send message via WebSocket
      chatService.sendMessage(messageRequest);
      
      // Clear input and stop typing indicator
      setMessageInput('');
      setIsTyping(false);
      if (currentChannel) {
        chatService.sendTypingIndicator(currentChannel.id, false);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      setError('Failed to send message. Please try again.');
    }
  };

  /**
   * Handle channel change
   */
  const handleChannelChange = (channel: any) => {
    setCurrentChannel(channel);
    setShowChannelList(false);
    
    // Mark channel as read
    chatService.markChannelAsRead(channel.id);
  };

  /**
   * Handle back to campaigns
   */
  const handleBackToCampaigns = () => {
    navigate('/campaigns');
  };

  // Get current channel messages
  const currentMessages = currentChannel ? getMessagesForChannel(currentChannel.id) : [];

  // Get typing users for current channel
  const currentTypingUsers = Array.from(typingUsers).filter(userId => 
    onlineUsers.some(user => user.id === userId)
  );

  return (
    <div className="h-screen bg-dark-900 flex flex-col">
      {/* Header */}
      <header className="bg-dark-800 border-b border-dark-700 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleBackToCampaigns}
              className="flex items-center space-x-2"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              <span>Back</span>
            </Button>
            
            <div className="flex items-center space-x-3">
              <ChatBubbleLeftRightIcon className="h-6 w-6 text-primary-400" />
              <div>
                <h1 className="text-lg font-semibold text-white">
                  {currentCampaign?.name || 'Campaign Chat'}
                </h1>
                {currentChannel && (
                  <p className="text-sm text-gray-400">
                    #{currentChannel.name}
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowChannelList(!showChannelList)}
              className="flex items-center space-x-2"
            >
              <ChatBubbleLeftRightIcon className="h-4 w-4" />
              <span>Channels</span>
            </Button>
            
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowUserList(!showUserList)}
              className="flex items-center space-x-2"
            >
              <UserGroupIcon className="h-4 w-4" />
              <span>Users ({onlineUsers.length})</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Channel List Sidebar */}
        <AnimatePresence>
          {showChannelList && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 250, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="bg-dark-800 border-r border-dark-700 overflow-hidden"
            >
              <ChannelList
                channels={channels}
                currentChannel={currentChannel}
                onChannelSelect={handleChannelChange}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-hidden">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <motion.div
                  className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                />
              </div>
            ) : currentChannel ? (
              <MessageList
                messages={currentMessages}
                typingUsers={currentTypingUsers}
                messagesEndRef={messagesEndRef}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <ChatBubbleLeftRightIcon className="h-16 w-16 text-gray-600 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-gray-400 mb-2">
                    No Channel Selected
                  </h3>
                  <p className="text-gray-500">
                    Select a channel from the sidebar to start chatting
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Message Input */}
          {currentChannel && (
            <div className="bg-dark-800 border-t border-dark-700 p-4">
              <form onSubmit={handleSendMessage} className="flex space-x-3">
                <div className="flex-1">
                  <Input
                    placeholder={`Message #${currentChannel.name}`}
                    value={messageInput}
                    onChange={handleMessageInputChange}
                    className="w-full"
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={!messageInput.trim()}
                  className="flex items-center space-x-2"
                >
                  <PaperAirplaneIcon className="h-4 w-4" />
                  <span>Send</span>
                </Button>
              </form>
            </div>
          )}
        </div>

        {/* User List Sidebar */}
        <AnimatePresence>
          {showUserList && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 250, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="bg-dark-800 border-l border-dark-700 overflow-hidden"
            >
              <UserList
                users={onlineUsers}
                currentUserId={user?.id}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Error Display */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-red-900/20 border-t border-red-500/30 px-4 py-3"
        >
          <div className="flex items-center justify-between">
            <p className="text-red-400">{error}</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={clearError}
            >
              Dismiss
            </Button>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default ChatInterface;

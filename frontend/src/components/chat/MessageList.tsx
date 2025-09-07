/**
 * ShadowRealms AI - Message List Component
 * 
 * This component displays a list of chat messages with proper formatting,
 * user information, timestamps, and message types.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays chat messages in chronological order
 * 2. Shows user avatars and names
 * 3. Formats different message types (text, system, dice rolls, etc.)
 * 4. Handles message grouping and timestamps
 * 5. Shows typing indicators and message reactions
 */

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  UserIcon,
  ChatBubbleLeftRightIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import { ChatMessage, MessageType } from '../../types/chat';

/**
 * Message List Props Interface
 * Defines the props that the MessageList component accepts
 */
interface MessageListProps {
  messages: ChatMessage[];
  typingUsers?: string[];
  messagesEndRef?: React.RefObject<HTMLDivElement>;
}

/**
 * Get message type styling and icon
 * @param type - Message type
 * @returns Object with styling and icon information
 */
const getMessageTypeInfo = (type: MessageType) => {
  switch (type) {
    case MessageType.SYSTEM:
      return {
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/20',
        icon: ExclamationTriangleIcon,
        prefix: '[SYSTEM]'
      };
    case MessageType.DICE_ROLL:
      return {
        color: 'text-green-400',
        bgColor: 'bg-green-900/20',
        icon: ChatBubbleLeftRightIcon,
        prefix: '[DICE]'
      };
    case MessageType.OOC:
      return {
        color: 'text-blue-400',
        bgColor: 'bg-blue-900/20',
        icon: ChatBubbleLeftRightIcon,
        prefix: '[OOC]'
      };
    case MessageType.WHISPER:
      return {
        color: 'text-purple-400',
        bgColor: 'bg-purple-900/20',
        icon: ChatBubbleLeftRightIcon,
        prefix: '[WHISPER]'
      };
    case MessageType.ACTION:
      return {
        color: 'text-orange-400',
        bgColor: 'bg-orange-900/20',
        icon: ChatBubbleLeftRightIcon,
        prefix: '[ACTION]'
      };
    default:
      return {
        color: 'text-gray-200',
        bgColor: 'bg-transparent',
        icon: ChatBubbleLeftRightIcon,
        prefix: ''
      };
  }
};

/**
 * Format timestamp for display
 * @param timestamp - ISO timestamp string
 * @returns Formatted time string
 */
const formatTimestamp = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

/**
 * Message Item Component
 * Displays a single message with all its information
 */
const MessageItem: React.FC<{ message: ChatMessage; index: number }> = ({ message, index }) => {
  const typeInfo = getMessageTypeInfo(message.type);
  const TypeIcon = typeInfo.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      className="flex items-start space-x-3 p-3 hover:bg-dark-800/50 rounded-lg transition-colors"
    >
      {/* Avatar */}
      <div className="flex-shrink-0">
        <div className="h-8 w-8 rounded-full bg-primary-600 flex items-center justify-center">
          <UserIcon className="h-5 w-5 text-white" />
        </div>
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-baseline space-x-2 mb-1">
          <span className="font-semibold text-primary-300">{message.username}</span>
          {typeInfo.prefix && (
            <span className={`text-xs font-medium ${typeInfo.color}`}>
              {typeInfo.prefix}
            </span>
          )}
          <span className="text-xs text-gray-500">
            {formatTimestamp(message.timestamp)}
          </span>
          {message.editedAt && (
            <span className="text-xs text-gray-500">(edited)</span>
          )}
        </div>

        {/* Message Content */}
        <div className={`${typeInfo.color} ${typeInfo.bgColor} p-2 rounded-md`}>
          <p className="text-sm">{message.content}</p>
          
          {/* Dice Roll Metadata */}
          {message.type === MessageType.DICE_ROLL && message.metadata?.diceRoll && (
            <div className="mt-2 text-xs text-gray-300">
              <div className="font-mono">
                {message.metadata.diceRoll.formula} = {message.metadata.diceRoll.total}
                {message.metadata.diceRoll.critical && (
                  <span className="text-yellow-400 ml-2">Critical Success!</span>
                )}
              </div>
              <div className="text-gray-400">
                Rolls: {message.metadata.diceRoll.results.join(', ')}
              </div>
            </div>
          )}
        </div>

        {/* Reactions */}
        {message.reactions && message.reactions.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {message.reactions.map((reaction, reactionIndex) => (
              <div
                key={reactionIndex}
                className="flex items-center space-x-1 px-2 py-1 bg-dark-700 rounded-full text-xs"
              >
                <span>{reaction.emoji}</span>
                <span className="text-gray-300">{reaction.username}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
};

/**
 * Typing Indicator Component
 * Shows when users are typing
 */
const TypingIndicator: React.FC<{ usernames: string[] }> = ({ usernames }) => {
  if (usernames.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="flex items-center space-x-3 p-3"
    >
      <div className="h-8 w-8 rounded-full bg-gray-600 flex items-center justify-center">
        <div className="flex space-x-1">
          <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce"></div>
          <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
          <div className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
        </div>
      </div>
      <div className="text-sm text-gray-400">
        {usernames.length === 1 
          ? `${usernames[0]} is typing...`
          : `${usernames.join(', ')} are typing...`
        }
      </div>
    </motion.div>
  );
};

/**
 * Message List Component
 * Displays a list of chat messages with proper formatting and interactions
 */
const MessageList: React.FC<MessageListProps> = ({
  messages,
  typingUsers = [],
  messagesEndRef
}) => {
  const localMessagesEndRef = useRef<HTMLDivElement>(null);
  const endRef = messagesEndRef || localMessagesEndRef;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, endRef]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-center p-8">
        <div>
          <ChatBubbleLeftRightIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-400 mb-2">No Messages Yet</h3>
          <p className="text-gray-500">
            Be the first to send a message in this channel
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-2">
      <AnimatePresence>
        {messages.map((message, index) => (
          <MessageItem
            key={message.id}
            message={message}
            index={index}
          />
        ))}
      </AnimatePresence>
      
      {/* Typing Indicator */}
      <AnimatePresence>
        {typingUsers.length > 0 && (
          <TypingIndicator usernames={typingUsers} />
        )}
      </AnimatePresence>
      
      {/* Scroll anchor */}
      <div ref={endRef} />
    </div>
  );
};

export default MessageList;
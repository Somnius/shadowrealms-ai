/**
 * ShadowRealms AI - Main Dashboard Component
 * 
 * This is the main dashboard that users see after logging in.
 * It provides navigation to different parts of the application and
 * displays key information about the user's campaigns and activity.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays user information and welcome message
 * 2. Provides quick access to campaigns and recent activity
 * 3. Shows system status and notifications
 * 4. Includes navigation to main application features
 * 5. Handles user logout functionality
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  UserIcon, 
  ChatBubbleLeftRightIcon, 
  BookOpenIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  PlusIcon
} from '@heroicons/react/24/outline';

// Import components and stores
import { useAuthStore } from '../store/authStore';
import { Button } from './ui/Button';
import { Card } from './ui/Card';

/**
 * Dashboard Component
 * Main landing page after user authentication
 */
const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  // Handle user logout
  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  // Quick action items for the dashboard
  const quickActions = [
    {
      title: 'View Campaigns',
      description: 'Browse and manage your RPG campaigns',
      icon: BookOpenIcon,
      action: () => navigate('/campaigns'),
      color: 'primary'
    },
    {
      title: 'Join Chat',
      description: 'Enter the active campaign chat',
      icon: ChatBubbleLeftRightIcon,
      action: () => navigate('/campaigns'),
      color: 'secondary'
    },
    {
      title: 'Create Campaign',
      description: 'Start a new RPG campaign',
      icon: PlusIcon,
      action: () => navigate('/campaigns'),
      color: 'accent'
    }
  ];

  // Animation variants for staggered entrance
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0 }
  };

  return (
    <div className="min-h-screen bg-dark-900">
      {/* Header */}
      <header className="bg-dark-800 border-b border-dark-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Title */}
            <div className="flex items-center">
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5 }}
                className="flex items-center"
              >
                <BookOpenIcon className="h-8 w-8 text-primary-400 mr-3" />
                <h1 className="text-2xl font-bold text-white">ShadowRealms AI</h1>
              </motion.div>
            </div>

            {/* User Menu */}
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <UserIcon className="h-6 w-6 text-gray-400" />
                <span className="text-gray-300">
                  Welcome, {user?.username || 'Adventurer'}
                </span>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleLogout}
                className="flex items-center space-x-2"
              >
                <ArrowRightOnRectangleIcon className="h-4 w-4" />
                <span>Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-8"
        >
          {/* Welcome Section */}
          <motion.div variants={itemVariants}>
            <Card className="p-8 bg-gradient-to-r from-primary-900/20 to-secondary-900/20 border-primary-500/30">
              <div className="text-center">
                <h2 className="text-3xl font-bold text-white mb-4">
                  Welcome to ShadowRealms AI
                </h2>
                <p className="text-xl text-gray-300 mb-6">
                  Your AI-powered tabletop RPG adventure awaits
                </p>
                <p className="text-gray-400 max-w-2xl mx-auto">
                  Experience the future of tabletop gaming with intelligent AI assistance, 
                  persistent world memory, and seamless multi-language support.
                </p>
              </div>
            </Card>
          </motion.div>

          {/* Quick Actions */}
          <motion.div variants={itemVariants}>
            <h3 className="text-2xl font-bold text-white mb-6">Quick Actions</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {quickActions.map((action, index) => (
                <motion.div
                  key={action.title}
                  variants={itemVariants}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <Card 
                    className="p-6 cursor-pointer hover:border-primary-500/50 transition-all duration-200"
                    onClick={action.action}
                  >
                    <div className="flex items-center mb-4">
                      <div className={`p-3 rounded-lg bg-${action.color}-900/30 mr-4`}>
                        <action.icon className={`h-6 w-6 text-${action.color}-400`} />
                      </div>
                      <h4 className="text-lg font-semibold text-white">
                        {action.title}
                      </h4>
                    </div>
                    <p className="text-gray-400 mb-4">
                      {action.description}
                    </p>
                    <div className="flex items-center text-primary-400 text-sm font-medium">
                      <span>Get Started</span>
                      <ArrowRightOnRectangleIcon className="h-4 w-4 ml-2 rotate-90" />
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Recent Activity */}
          <motion.div variants={itemVariants}>
            <h3 className="text-2xl font-bold text-white mb-6">Recent Activity</h3>
            <Card className="p-6">
              <div className="text-center py-12">
                <ChatBubbleLeftRightIcon className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                <h4 className="text-lg font-semibold text-gray-400 mb-2">
                  No Recent Activity
                </h4>
                <p className="text-gray-500 mb-6">
                  Start a campaign or join a chat to see your activity here
                </p>
                <Button
                  variant="primary"
                  onClick={() => navigate('/campaigns')}
                >
                  Browse Campaigns
                </Button>
              </div>
            </Card>
          </motion.div>

          {/* System Status */}
          <motion.div variants={itemVariants}>
            <h3 className="text-2xl font-bold text-white mb-6">System Status</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-lg font-semibold text-white">AI Service</h4>
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                    <span className="text-green-400 text-sm">Online</span>
                  </div>
                </div>
                <p className="text-gray-400 text-sm">
                  AI Dungeon Master is ready to assist with your campaigns
                </p>
              </Card>

              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-lg font-semibold text-white">Memory System</h4>
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-green-400 rounded-full mr-2"></div>
                    <span className="text-green-400 text-sm">Active</span>
                  </div>
                </div>
                <p className="text-gray-400 text-sm">
                  Campaign memory and context are being maintained
                </p>
              </Card>
            </div>
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
};

export default Dashboard;

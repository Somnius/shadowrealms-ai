/**
 * ShadowRealms AI - Create Campaign Modal Component
 * 
 * This component provides a modal interface for creating new campaigns.
 * It includes form validation and integrates with the campaign service
 * to create new campaigns.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Provides a form for creating new campaigns
 * 2. Validates form input and shows error messages
 * 3. Handles campaign creation through the API service
 * 4. Manages modal state and form submission
 * 5. Provides a clean, accessible modal interface
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  XMarkIcon, 
  BookOpenIcon,
  UserGroupIcon,
  EyeIcon,
  EyeSlashIcon,
  UserGroupIcon as FriendsIcon
} from '@heroicons/react/24/outline';

// Import components
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

// Import types
import { CampaignCreateData, RPGSystem, CampaignVisibility } from '../../types/campaign';

/**
 * Create Campaign Modal Props Interface
 * Defines the props that the CreateCampaignModal component accepts
 */
interface CreateCampaignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (campaignData: CampaignCreateData) => Promise<void>;
}

/**
 * Form Data Interface
 * Defines the structure of the campaign creation form data
 */
interface FormData {
  name: string;
  description: string;
  system: RPGSystem;
  visibility: CampaignVisibility;
  setting: string;
  theme: string;
  maxPlayers: number;
  tags: string;
}

/**
 * Form Errors Interface
 * Defines the structure for form validation errors
 */
interface FormErrors {
  name?: string;
  description?: string;
  setting?: string;
  theme?: string;
  maxPlayers?: string;
  general?: string;
}

/**
 * Create Campaign Modal Component
 * Modal for creating new campaigns
 */
const CreateCampaignModal: React.FC<CreateCampaignModalProps> = ({
  isOpen,
  onClose,
  onCreate
}) => {
  // Form state
  const [formData, setFormData] = useState<FormData>({
    name: '',
    description: '',
    system: RPGSystem.DND_5E,
    visibility: CampaignVisibility.PUBLIC,
    setting: '',
    theme: '',
    maxPlayers: 6,
    tags: ''
  });

  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * Handle form input changes
   */
  const handleInputChange = (field: keyof FormData, value: string | number) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error for this field when user starts typing
    if (errors[field as keyof FormErrors]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  /**
   * Validate form data
   */
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Required fields validation
    if (!formData.name.trim()) {
      newErrors.name = 'Campaign name is required';
    } else if (formData.name.length < 3) {
      newErrors.name = 'Campaign name must be at least 3 characters';
    } else if (formData.name.length > 50) {
      newErrors.name = 'Campaign name must be less than 50 characters';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Campaign description is required';
    } else if (formData.description.length < 10) {
      newErrors.description = 'Description must be at least 10 characters';
    } else if (formData.description.length > 500) {
      newErrors.description = 'Description must be less than 500 characters';
    }

    if (!formData.setting.trim()) {
      newErrors.setting = 'Campaign setting is required';
    }

    if (!formData.theme.trim()) {
      newErrors.theme = 'Campaign theme is required';
    }

    // Max players validation
    if (formData.maxPlayers < 2) {
      newErrors.maxPlayers = 'Campaign must allow at least 2 players';
    } else if (formData.maxPlayers > 12) {
      newErrors.maxPlayers = 'Campaign cannot have more than 12 players';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /**
   * Handle form submission
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      // Prepare campaign data
      const campaignData: CampaignCreateData = {
        name: formData.name.trim(),
        description: formData.description.trim(),
        system: formData.system,
        visibility: formData.visibility,
        setting: formData.setting.trim(),
        theme: formData.theme.trim(),
        maxPlayers: formData.maxPlayers,
        tags: formData.tags ? formData.tags.split(',').map(tag => tag.trim()).filter(tag => tag) : [],
        settings: {
          aiAssistance: true,
          aiPersonality: 'helpful',
          aiResponseLength: 'medium',
          allowSpectators: true,
          requireApproval: false,
          enableOOC: true,
          enablePrivateMessages: true,
          enableDiceRolls: true,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          language: 'en'
        }
      };

      await onCreate(campaignData);
      
      // Reset form and close modal
      setFormData({
        name: '',
        description: '',
        system: RPGSystem.DND_5E,
        visibility: CampaignVisibility.PUBLIC,
        setting: '',
        theme: '',
        maxPlayers: 6,
        tags: ''
      });
      onClose();
    } catch (error) {
      console.error('Failed to create campaign:', error);
      setErrors({ general: 'Failed to create campaign. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle modal close
   */
  const handleClose = () => {
    if (!isSubmitting) {
      setFormData({
        name: '',
        description: '',
        system: RPGSystem.DND_5E,
        visibility: CampaignVisibility.PUBLIC,
        setting: '',
        theme: '',
        maxPlayers: 6,
        tags: ''
      });
      setErrors({});
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 overflow-y-auto"
        >
          {/* Backdrop */}
          <div className="fixed inset-0 bg-black bg-opacity-50" onClick={handleClose} />

          {/* Modal */}
          <div className="flex min-h-full items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.2 }}
              className="relative bg-dark-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-dark-700">
                <div className="flex items-center space-x-3">
                  <BookOpenIcon className="h-6 w-6 text-primary-400" />
                  <h2 className="text-xl font-bold text-white">Create New Campaign</h2>
                </div>
                <button
                  onClick={handleClose}
                  disabled={isSubmitting}
                  className="text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="p-6 space-y-6">
                {/* General Error */}
                {errors.general && (
                  <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                    <p className="text-red-400">{errors.general}</p>
                  </div>
                )}

                {/* Campaign Name */}
                <div>
                  <Input
                    label="Campaign Name"
                    placeholder="Enter campaign name"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    error={errors.name}
                    required
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Description *
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    placeholder="Describe your campaign setting, story, and what players can expect..."
                    rows={4}
                    className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                  {errors.description && (
                    <p className="mt-1 text-sm text-red-400">{errors.description}</p>
                  )}
                </div>

                {/* System and Visibility */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* RPG System */}
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      RPG System *
                    </label>
                    <select
                      value={formData.system}
                      onChange={(e) => handleInputChange('system', e.target.value as RPGSystem)}
                      className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value={RPGSystem.DND_5E}>D&D 5th Edition</option>
                      <option value={RPGSystem.WORLD_OF_DARKNESS}>World of Darkness</option>
                      <option value={RPGSystem.PATHFINDER}>Pathfinder</option>
                      <option value={RPGSystem.CUSTOM}>Custom System</option>
                    </select>
                  </div>

                  {/* Visibility */}
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Visibility *
                    </label>
                    <select
                      value={formData.visibility}
                      onChange={(e) => handleInputChange('visibility', e.target.value as CampaignVisibility)}
                      className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value={CampaignVisibility.PUBLIC}>
                        <EyeIcon className="h-4 w-4 inline mr-2" />
                        Public
                      </option>
                      <option value={CampaignVisibility.PRIVATE}>
                        <EyeSlashIcon className="h-4 w-4 inline mr-2" />
                        Private
                      </option>
                      <option value={CampaignVisibility.FRIENDS_ONLY}>
                        <FriendsIcon className="h-4 w-4 inline mr-2" />
                        Friends Only
                      </option>
                    </select>
                  </div>
                </div>

                {/* Setting and Theme */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Input
                      label="Setting"
                      placeholder="e.g., Forgotten Realms, Modern Day, Space Opera"
                      value={formData.setting}
                      onChange={(e) => handleInputChange('setting', e.target.value)}
                      error={errors.setting}
                      required
                    />
                  </div>
                  <div>
                    <Input
                      label="Theme"
                      placeholder="e.g., Horror, Adventure, Mystery, Romance"
                      value={formData.theme}
                      onChange={(e) => handleInputChange('theme', e.target.value)}
                      error={errors.theme}
                      required
                    />
                  </div>
                </div>

                {/* Max Players and Tags */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Input
                      label="Maximum Players"
                      type="number"
                      min="2"
                      max="12"
                      value={formData.maxPlayers.toString()}
                      onChange={(e) => handleInputChange('maxPlayers', parseInt(e.target.value) || 6)}
                      error={errors.maxPlayers}
                      required
                    />
                  </div>
                  <div>
                    <Input
                      label="Tags (comma-separated)"
                      placeholder="e.g., beginner-friendly, roleplay-heavy, combat-focused"
                      value={formData.tags}
                      onChange={(e) => handleInputChange('tags', e.target.value)}
                    />
                  </div>
                </div>

                {/* Actions */}
                <div className="flex justify-end space-x-4 pt-6 border-t border-dark-700">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleClose}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isSubmitting}
                    className="flex items-center space-x-2"
                  >
                    {isSubmitting ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        <span>Creating...</span>
                      </>
                    ) : (
                      <>
                        <BookOpenIcon className="h-4 w-4" />
                        <span>Create Campaign</span>
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CreateCampaignModal;

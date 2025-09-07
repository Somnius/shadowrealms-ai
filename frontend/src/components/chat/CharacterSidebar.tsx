/**
 * ShadowRealms AI - Character Sidebar Component
 * 
 * This component displays character information and traits in the chat interface.
 * It shows character stats, abilities, and provides quick access to character actions.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Displays current character information and stats
 * 2. Shows character abilities, skills, and traits
 * 3. Provides quick access to dice rolls and actions
 * 4. Handles character switching and management
 * 5. Integrates with the character system
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  UserIcon,
  HeartIcon,
  ShieldCheckIcon,
  BoltIcon,
  StarIcon,
  Cog6ToothIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

// Import components
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

// Import types
import { Character, CharacterStats, CharacterAbility } from '../../types/character';

/**
 * Character Sidebar Props Interface
 * Defines the props that the CharacterSidebar component accepts
 */
interface CharacterSidebarProps {
  currentCharacter: Character | null;
  onCharacterSelect: (character: Character) => void;
  onDiceRoll: (formula: string) => void;
  onAction: (action: string) => void;
}

/**
 * Character Stats Display Component
 * Shows character statistics in a compact format
 */
const CharacterStatsDisplay: React.FC<{ stats: CharacterStats }> = ({ stats }) => {
  const statItems = [
    { label: 'HP', value: `${stats.currentHP}/${stats.maxHP}`, color: 'text-red-400' },
    { label: 'AC', value: stats.armorClass.toString(), color: 'text-blue-400' },
    { label: 'Speed', value: `${stats.speed}ft`, color: 'text-green-400' },
    { label: 'Level', value: stats.level.toString(), color: 'text-purple-400' },
  ];

  return (
    <div className="grid grid-cols-2 gap-3">
      {statItems.map((item, index) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
          className="bg-dark-700 rounded-lg p-3 text-center"
        >
          <div className={`text-lg font-bold ${item.color}`}>
            {item.value}
          </div>
          <div className="text-xs text-gray-400">
            {item.label}
          </div>
        </motion.div>
      ))}
    </div>
  );
};

/**
 * Ability Score Display Component
 * Shows character ability scores
 */
const AbilityScoresDisplay: React.FC<{ abilities: CharacterAbility[] }> = ({ abilities }) => {
  const getAbilityModifier = (score: number) => {
    return Math.floor((score - 10) / 2);
  };

  const getModifierColor = (modifier: number) => {
    if (modifier >= 3) return 'text-green-400';
    if (modifier >= 1) return 'text-blue-400';
    if (modifier >= -1) return 'text-gray-400';
    if (modifier >= -3) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="space-y-2">
      {abilities.map((ability, index) => {
        const modifier = getAbilityModifier(ability.score);
        return (
          <motion.div
            key={ability.name}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: index * 0.1 }}
            className="flex items-center justify-between p-2 bg-dark-700 rounded-lg"
          >
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-primary-400 rounded-full"></div>
              <span className="text-sm font-medium text-white">
                {ability.name}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-300">
                {ability.score}
              </span>
              <span className={`text-sm font-bold ${getModifierColor(modifier)}`}>
                {modifier >= 0 ? '+' : ''}{modifier}
              </span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
};

/**
 * Quick Actions Component
 * Provides quick access to common character actions
 */
const QuickActions: React.FC<{ 
  onDiceRoll: (formula: string) => void;
  onAction: (action: string) => void;
}> = ({ onDiceRoll, onAction }) => {
  const commonRolls = [
    { label: 'd20', formula: '1d20', color: 'bg-blue-600' },
    { label: 'd100', formula: '1d100', color: 'bg-green-600' },
    { label: '2d6', formula: '2d6', color: 'bg-purple-600' },
    { label: '3d6', formula: '3d6', color: 'bg-red-600' },
  ];

  const commonActions = [
    { label: 'Initiative', action: 'roll initiative', icon: BoltIcon },
    { label: 'Perception', action: 'roll perception', icon: EyeIcon },
    { label: 'Stealth', action: 'roll stealth', icon: UserIcon },
    { label: 'Attack', action: 'roll attack', icon: ShieldCheckIcon },
  ];

  return (
    <div className="space-y-4">
      {/* Common Dice Rolls */}
      <div>
        <h4 className="text-sm font-medium text-gray-300 mb-2">Quick Rolls</h4>
        <div className="grid grid-cols-2 gap-2">
          {commonRolls.map((roll, index) => (
            <motion.button
              key={roll.label}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
              onClick={() => onDiceRoll(roll.formula)}
              className={`${roll.color} text-white text-sm font-medium py-2 px-3 rounded-lg hover:opacity-80 transition-opacity`}
            >
              {roll.label}
            </motion.button>
          ))}
        </div>
      </div>

      {/* Common Actions */}
      <div>
        <h4 className="text-sm font-medium text-gray-300 mb-2">Quick Actions</h4>
        <div className="space-y-2">
          {commonActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <motion.button
                key={action.label}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.1 }}
                onClick={() => onAction(action.action)}
                className="w-full flex items-center space-x-3 p-2 bg-dark-700 rounded-lg hover:bg-dark-600 transition-colors"
              >
                <Icon className="h-4 w-4 text-primary-400" />
                <span className="text-sm text-white">{action.label}</span>
              </motion.button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

/**
 * Character Sidebar Component
 * Main component for displaying character information
 */
const CharacterSidebar: React.FC<CharacterSidebarProps> = ({
  currentCharacter,
  onCharacterSelect,
  onDiceRoll,
  onAction
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<'stats' | 'abilities' | 'actions'>('stats');

  if (!currentCharacter) {
    return (
      <div className="w-80 bg-dark-800 border-l border-dark-700 flex flex-col">
        <div className="p-4 border-b border-dark-700">
          <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
            <UserIcon className="h-5 w-5 text-primary-400" />
            <span>Character</span>
          </h3>
        </div>
        
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <UserIcon className="h-16 w-16 text-gray-600 mx-auto mb-4" />
            <h4 className="text-lg font-semibold text-gray-400 mb-2">
              No Character Selected
            </h4>
            <p className="text-gray-500 text-sm mb-4">
              Select a character to view their information and actions
            </p>
            <Button
              variant="primary"
              size="sm"
              className="flex items-center space-x-2"
            >
              <PlusIcon className="h-4 w-4" />
              <span>Create Character</span>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-dark-800 border-l border-dark-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-dark-700">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center space-x-2">
            <UserIcon className="h-5 w-5 text-primary-400" />
            <span>Character</span>
          </h3>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-white transition-colors"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-5 w-5" />
            ) : (
              <ChevronRightIcon className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {isExpanded && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.3 }}
          className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-dark-600 scrollbar-track-dark-800"
        >
          <div className="p-4 space-y-6">
            {/* Character Info */}
            <Card className="p-4">
              <div className="text-center">
                <div className="w-16 h-16 bg-primary-600 rounded-full mx-auto mb-3 flex items-center justify-center">
                  <UserIcon className="h-8 w-8 text-white" />
                </div>
                <h4 className="text-lg font-semibold text-white mb-1">
                  {currentCharacter.name}
                </h4>
                <p className="text-sm text-gray-400 mb-2">
                  {currentCharacter.race} {currentCharacter.class}
                </p>
                <div className="flex items-center justify-center space-x-2">
                  <StarIcon className="h-4 w-4 text-yellow-400" />
                  <span className="text-sm text-gray-300">
                    Level {currentCharacter.stats.level}
                  </span>
                </div>
              </div>
            </Card>

            {/* Tab Navigation */}
            <div className="flex space-x-1 bg-dark-700 rounded-lg p-1">
              {[
                { id: 'stats', label: 'Stats', icon: HeartIcon },
                { id: 'abilities', label: 'Abilities', icon: ShieldCheckIcon },
                { id: 'actions', label: 'Actions', icon: BoltIcon },
              ].map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`flex-1 flex items-center justify-center space-x-2 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                      activeTab === tab.id
                        ? 'bg-primary-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <AnimatePresence mode="wait">
              {activeTab === 'stats' && (
                <motion.div
                  key="stats"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <CharacterStatsDisplay stats={currentCharacter.stats} />
                </motion.div>
              )}

              {activeTab === 'abilities' && (
                <motion.div
                  key="abilities"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <AbilityScoresDisplay abilities={currentCharacter.abilities} />
                </motion.div>
              )}

              {activeTab === 'actions' && (
                <motion.div
                  key="actions"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <QuickActions onDiceRoll={onDiceRoll} onAction={onAction} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}
    </div>
  );
};

export default CharacterSidebar;

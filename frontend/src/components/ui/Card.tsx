/**
 * ShadowRealms AI - Card Component
 * 
 * A reusable card component for displaying content in containers.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Provides consistent card styling across the application
 * 2. Supports different card variants and sizes
 * 3. Includes proper spacing and border styling
 * 4. Supports custom content and styling
 * 5. Includes hover effects and animations
 */

import React from 'react';
import { motion } from 'framer-motion';

/**
 * Card Variant Types
 * Defines the available card styles
 */
export type CardVariant = 'default' | 'elevated' | 'outlined' | 'filled';

/**
 * Card Props Interface
 * Defines the props that the Card component accepts
 */
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

/**
 * Get card variant classes
 * @param variant - Card variant
 * @returns CSS classes for the variant
 */
const getVariantClasses = (variant: CardVariant): string => {
  switch (variant) {
    case 'default':
      return 'bg-dark-800 border border-dark-700';
    case 'elevated':
      return 'bg-dark-800 border border-dark-700 shadow-lg';
    case 'outlined':
      return 'bg-transparent border border-dark-700';
    case 'filled':
      return 'bg-dark-700 border border-dark-600';
    default:
      return 'bg-dark-800 border border-dark-700';
  }
};

/**
 * Card Component
 * A reusable card container with consistent styling
 */
const Card: React.FC<CardProps> = ({
  variant = 'default',
  children,
  className = '',
  hover = false,
  ...props
}) => {
  const baseClasses = 'rounded-lg transition-colors duration-200';
  const variantClasses = getVariantClasses(variant);
  const hoverClasses = hover ? 'hover:border-primary-500/50 hover:shadow-lg' : '';
  
  const cardClasses = `${baseClasses} ${variantClasses} ${hoverClasses} ${className}`;

  if (hover) {
    return (
      <motion.div
        whileHover={{ y: -2 }}
        transition={{ duration: 0.2 }}
        className={cardClasses}
        {...props}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <div className={cardClasses} {...props}>
      {children}
    </div>
  );
};

export default Card;
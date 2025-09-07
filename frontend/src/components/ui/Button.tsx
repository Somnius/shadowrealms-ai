/**
 * ShadowRealms AI - Button Component
 * 
 * A reusable button component with multiple variants and states.
 * 
 * WHAT THIS COMPONENT DOES:
 * 1. Provides consistent button styling across the application
 * 2. Supports multiple variants (primary, secondary, outline, ghost)
 * 3. Handles loading states and disabled states
 * 4. Includes proper accessibility attributes
 * 5. Supports custom styling and animations
 */

import React from 'react';
import { motion } from 'framer-motion';

/**
 * Button Variant Types
 * Defines the available button styles
 */
export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';

/**
 * Button Size Types
 * Defines the available button sizes
 */
export type ButtonSize = 'sm' | 'md' | 'lg';

/**
 * Button Props Interface
 * Defines the props that the Button component accepts
 */
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Get button variant classes
 * @param variant - Button variant
 * @returns CSS classes for the variant
 */
const getVariantClasses = (variant: ButtonVariant): string => {
  switch (variant) {
    case 'primary':
      return 'bg-primary-600 hover:bg-primary-700 text-white border-primary-600 hover:border-primary-700';
    case 'secondary':
      return 'bg-dark-700 hover:bg-dark-600 text-gray-200 border-dark-700 hover:border-dark-600';
    case 'outline':
      return 'bg-transparent hover:bg-primary-600 text-primary-400 border-primary-600 hover:text-white';
    case 'ghost':
      return 'bg-transparent hover:bg-dark-700 text-gray-400 border-transparent hover:text-gray-200';
    case 'danger':
      return 'bg-red-600 hover:bg-red-700 text-white border-red-600 hover:border-red-700';
    default:
      return 'bg-primary-600 hover:bg-primary-700 text-white border-primary-600 hover:border-primary-700';
  }
};

/**
 * Get button size classes
 * @param size - Button size
 * @returns CSS classes for the size
 */
const getSizeClasses = (size: ButtonSize): string => {
  switch (size) {
    case 'sm':
      return 'px-3 py-1.5 text-sm';
    case 'md':
      return 'px-4 py-2 text-sm';
    case 'lg':
      return 'px-6 py-3 text-base';
    default:
      return 'px-4 py-2 text-sm';
  }
};

/**
 * Button Component
 * A reusable button with consistent styling and behavior
 */
const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  children,
  className = '',
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium rounded-md border transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-dark-900 disabled:opacity-50 disabled:cursor-not-allowed';
  const variantClasses = getVariantClasses(variant);
  const sizeClasses = getSizeClasses(size);
  
  const buttonClasses = `${baseClasses} ${variantClasses} ${sizeClasses} ${className}`;

  return (
    <motion.button
      whileHover={{ scale: disabled || isLoading ? 1 : 1.02 }}
      whileTap={{ scale: disabled || isLoading ? 1 : 0.98 }}
      className={buttonClasses}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {children}
    </motion.button>
  );
};

export default Button;
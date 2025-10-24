/**
 * Security utilities for ShadowRealms AI
 * Provides input sanitization, XSS prevention, and validation helpers
 */

/**
 * Sanitize HTML input to prevent XSS attacks
 * @param {string} input - Raw user input
 * @returns {string} - Sanitized input safe for display
 */
export const sanitizeHtml = (input) => {
  if (!input) return '';
  
  const div = document.createElement('div');
  div.textContent = input;
  return div.innerHTML;
};

/**
 * Sanitize input for use in URLs
 * @param {string} input - Raw user input
 * @returns {string} - URL-safe encoded string
 */
export const sanitizeUrl = (input) => {
  if (!input) return '';
  return encodeURIComponent(input);
};

/**
 * Validate email format
 * @param {string} email - Email address to validate
 * @returns {boolean} - True if valid email format
 */
export const isValidEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Validate username format (alphanumeric, underscores, hyphens, 3-20 chars)
 * @param {string} username - Username to validate
 * @returns {boolean} - True if valid username format
 */
export const isValidUsername = (username) => {
  const usernameRegex = /^[a-zA-Z0-9_-]{3,20}$/;
  return usernameRegex.test(username);
};

/**
 * Validate password strength
 * Requires: 8+ chars, uppercase, lowercase, number
 * @param {string} password - Password to validate
 * @returns {object} - {valid: boolean, errors: string[]}
 */
export const validatePassword = (password) => {
  const errors = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
};

/**
 * Strip potentially dangerous characters from campaign/character names
 * Allows: letters, numbers, spaces, basic punctuation
 * @param {string} name - Name to sanitize
 * @returns {string} - Sanitized name
 */
export const sanitizeName = (name) => {
  if (!name) return '';
  
  // Remove HTML tags
  let sanitized = name.replace(/<[^>]*>/g, '');
  
  // Remove special characters except allowed ones
  sanitized = sanitized.replace(/[^a-zA-Z0-9\s\-',.!?()]/g, '');
  
  // Trim and limit length
  sanitized = sanitized.trim().substring(0, 100);
  
  return sanitized;
};

/**
 * Sanitize campaign description and setting text
 * Removes scripts, dangerous HTML, but allows basic formatting
 * @param {string} text - Text to sanitize
 * @returns {string} - Sanitized text
 */
export const sanitizeDescription = (text) => {
  if (!text) return '';
  
  // Remove script tags and event handlers
  let sanitized = text.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  sanitized = sanitized.replace(/on\w+="[^"]*"/gi, '');
  sanitized = sanitized.replace(/on\w+='[^']*'/gi, '');
  
  // Remove dangerous tags
  const dangerousTags = ['iframe', 'object', 'embed', 'link', 'style', 'meta'];
  dangerousTags.forEach(tag => {
    const regex = new RegExp(`<${tag}\\b[^<]*(?:(?!<\\/${tag}>)<[^<]*)*<\\/${tag}>`, 'gi');
    sanitized = sanitized.replace(regex, '');
  });
  
  // Limit length
  sanitized = sanitized.substring(0, 10000);
  
  return sanitized.trim();
};

/**
 * Validate and sanitize chat message
 * @param {string} message - Chat message to validate
 * @returns {object} - {valid: boolean, sanitized: string, error: string}
 */
export const validateChatMessage = (message) => {
  if (!message || message.trim().length === 0) {
    return { valid: false, sanitized: '', error: 'Message cannot be empty' };
  }
  
  if (message.length > 2000) {
    return { valid: false, sanitized: '', error: 'Message too long (max 2000 characters)' };
  }
  
  // Sanitize HTML
  const sanitized = sanitizeHtml(message);
  
  return { valid: true, sanitized, error: null };
};

/**
 * Rate limiting helper (client-side)
 * Prevents spam by tracking action timestamps
 */
export class RateLimiter {
  constructor(maxActions, windowMs) {
    this.maxActions = maxActions;
    this.windowMs = windowMs;
    this.actions = [];
  }
  
  /**
   * Check if action is allowed
   * @returns {boolean} - True if action is allowed
   */
  isAllowed() {
    const now = Date.now();
    
    // Remove old actions outside the time window
    this.actions = this.actions.filter(time => now - time < this.windowMs);
    
    // Check if under limit
    if (this.actions.length < this.maxActions) {
      this.actions.push(now);
      return true;
    }
    
    return false;
  }
  
  /**
   * Get time until next action is allowed
   * @returns {number} - Milliseconds until next action allowed
   */
  getTimeUntilAllowed() {
    if (this.actions.length < this.maxActions) return 0;
    
    const now = Date.now();
    const oldestAction = this.actions[0];
    return Math.max(0, this.windowMs - (now - oldestAction));
  }
}

/**
 * Secure localStorage wrapper with encryption (basic obfuscation)
 * Note: Not true encryption, but better than plain text
 */
export const secureStorage = {
  /**
   * Store data securely
   * @param {string} key - Storage key
   * @param {*} value - Value to store
   */
  set: (key, value) => {
    try {
      const jsonValue = JSON.stringify(value);
      // Basic obfuscation (not secure encryption, just obscurity)
      const encoded = btoa(jsonValue);
      localStorage.setItem(key, encoded);
    } catch (error) {
      console.error('Error storing data:', error);
    }
  },
  
  /**
   * Retrieve data securely
   * @param {string} key - Storage key
   * @returns {*} - Retrieved value or null
   */
  get: (key) => {
    try {
      const encoded = localStorage.getItem(key);
      if (!encoded) return null;
      
      const jsonValue = atob(encoded);
      return JSON.parse(jsonValue);
    } catch (error) {
      console.error('Error retrieving data:', error);
      return null;
    }
  },
  
  /**
   * Remove data
   * @param {string} key - Storage key
   */
  remove: (key) => {
    localStorage.removeItem(key);
  },
  
  /**
   * Clear all data
   */
  clear: () => {
    localStorage.clear();
  }
};

/**
 * Prevent common injection attacks in search queries
 * @param {string} query - Search query to sanitize
 * @returns {string} - Sanitized query
 */
export const sanitizeSearchQuery = (query) => {
  if (!query) return '';
  
  // Remove SQL-like injection attempts
  let sanitized = query.replace(/[';\\]/g, '');
  
  // Remove excessive wildcards
  sanitized = sanitized.replace(/\*{2,}/g, '*');
  
  // Trim and limit length
  sanitized = sanitized.trim().substring(0, 200);
  
  return sanitized;
};

/**
 * Validate campaign data before submission
 * @param {object} campaignData - Campaign data to validate
 * @returns {object} - {valid: boolean, errors: object, sanitized: object}
 */
export const validateCampaignData = (campaignData) => {
  const errors = {};
  const sanitized = {};
  
  // Name validation
  if (!campaignData.name || campaignData.name.trim().length === 0) {
    errors.name = 'Campaign name is required';
  } else if (campaignData.name.length > 100) {
    errors.name = 'Campaign name too long (max 100 characters)';
  } else {
    sanitized.name = sanitizeName(campaignData.name);
  }
  
  // Description validation
  if (campaignData.description) {
    sanitized.description = sanitizeDescription(campaignData.description);
  }
  
  // Game system validation
  const validSystems = ['vampire', 'werewolf', 'mage', 'changeling', 'hunter', 'dnd', 'other'];
  if (!campaignData.game_system || !validSystems.includes(campaignData.game_system.toLowerCase())) {
    errors.game_system = 'Invalid game system';
  } else {
    sanitized.game_system = campaignData.game_system.toLowerCase();
  }
  
  // Setting validation (if provided)
  if (campaignData.setting) {
    sanitized.setting = sanitizeDescription(campaignData.setting);
  }
  
  return {
    valid: Object.keys(errors).length === 0,
    errors,
    sanitized
  };
};

/**
 * Prevent click-jacking by checking if page is in iframe
 * @returns {boolean} - True if page is likely being clickjacked
 */
export const detectClickjacking = () => {
  return window.self !== window.top;
};

/**
 * Generate CSRF token for forms
 * @returns {string} - Random CSRF token
 */
export const generateCSRFToken = () => {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
};

export default {
  sanitizeHtml,
  sanitizeUrl,
  isValidEmail,
  isValidUsername,
  validatePassword,
  sanitizeName,
  sanitizeDescription,
  validateChatMessage,
  RateLimiter,
  secureStorage,
  sanitizeSearchQuery,
  validateCampaignData,
  detectClickjacking,
  generateCSRFToken
};


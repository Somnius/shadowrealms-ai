/**
 * Test Setup File for ShadowRealms AI Frontend
 * 
 * This file runs before every test file and sets up the testing environment.
 * It configures mocks, global variables, and test utilities that all tests need.
 * 
 * WHAT THIS FILE DOES:
 * 1. Imports Jest DOM matchers for better assertions
 * 2. Mocks browser APIs that aren't available in the test environment
 * 3. Sets up global mocks for external libraries
 * 4. Configures the testing environment for React components
 */

// Import Jest DOM matchers
// This adds custom matchers like toBeInTheDocument(), toHaveClass(), etc.
// These make it easier to test DOM elements in React components
import '@testing-library/jest-dom';

// Mock localStorage - a browser API for storing data locally
// In tests, we need to mock this because it's not available in Node.js
// We create a mock object with the same methods as real localStorage
const localStorageMock = {
  getItem: jest.fn(),      // Mock function for getting stored values
  setItem: jest.fn(),      // Mock function for storing values
  removeItem: jest.fn(),   // Mock function for removing values
  clear: jest.fn(),        // Mock function for clearing all values
};
// Make the mock available globally so our code can use it
global.localStorage = localStorageMock;

// Mock window.location - browser API for URL information
// We need to mock this because it's not available in the test environment
// First, delete the existing location property
delete (window as any).location;
// Then set a simple mock with just the href property
window.location = { href: '' } as any;

// Mock framer-motion - animation library that can cause issues in tests
// We replace the animated components with regular HTML elements
// This prevents animation-related errors and makes tests run faster
jest.mock('framer-motion', () => {
  const React = require('react');
  return {
    // Mock motion components - replace animated elements with regular ones
    motion: {
      div: ({ children, ...props }: any) => React.createElement('div', props, children),
      button: ({ children, ...props }: any) => React.createElement('button', props, children),
      input: ({ children, ...props }: any) => React.createElement('input', props, children),
      p: ({ children, ...props }: any) => React.createElement('p', props, children),
      span: ({ children, ...props }: any) => React.createElement('span', props, children),
    },
    // Mock AnimatePresence - just render children without animation logic
    AnimatePresence: ({ children }: any) => children,
  };
});

// Mock axios - HTTP client library
// We provide a basic mock that can be overridden in individual test files
jest.mock('axios', () => ({
  // Mock axios.create() method that returns a configured axios instance
  create: jest.fn(() => ({
    get: jest.fn().mockResolvedValue({ data: {} }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    put: jest.fn().mockResolvedValue({ data: {} }),
    delete: jest.fn().mockResolvedValue({ data: {} }),
    // Mock interceptors for request/response handling
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  })),
  // Mock direct axios methods (not using create)
  get: jest.fn().mockResolvedValue({ data: {} }),
  post: jest.fn().mockResolvedValue({ data: {} }),
  put: jest.fn().mockResolvedValue({ data: {} }),
  delete: jest.fn().mockResolvedValue({ data: {} }),
}));

// Mock Heroicons - icon library
// We replace icon components with simple div elements that have test IDs
// This allows us to test that icons are rendered without importing the actual icons
jest.mock('@heroicons/react/24/outline', () => ({
  EyeIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'eye-icon' });
  },
  EyeSlashIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'eye-slash-icon' });
  },
  UserIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'user-icon' });
  },
  LockClosedIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'lock-icon' });
  },
  UserGroupIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'user-group-icon' });
  },
  CalendarIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'calendar-icon' });
  },
  ClockIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'clock-icon' });
  },
  TagIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'tag-icon' });
  },
  PlayIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'play-icon' });
  },
  PauseIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'pause-icon' });
  },
  ArchiveBoxIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'archive-icon' });
  },
  CheckCircleIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'check-circle-icon' });
  },
  ArrowRightOnRectangleIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'arrow-right-icon' });
  },
  UserPlusIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'user-plus-icon' });
  },
  UserMinusIcon: () => {
    const React = require('react');
    return React.createElement('div', { 'data-testid': 'user-minus-icon' });
  },
}));

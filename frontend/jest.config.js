/**
 * Jest Configuration for ShadowRealms AI Frontend
 * 
 * This configuration file tells Jest how to run tests for our React application.
 * Jest is a JavaScript testing framework that runs our test files.
 * 
 * WHAT EACH OPTION DOES:
 * - testEnvironment: Sets up a browser-like environment for testing React components
 * - setupFilesAfterEnv: Runs setup code before each test file
 * - moduleNameMapping: Allows importing files with @/ prefix instead of relative paths
 * - collectCoverageFrom: Specifies which files to include in coverage reports
 * - coverageThreshold: Sets minimum coverage percentages that must be met
 * - coverageReporters: Specifies what format to generate coverage reports in
 * - testMatch: Tells Jest which files are test files
 * - transform: Specifies how to transform different file types
 * - moduleFileExtensions: Lists file extensions Jest should recognize
 * - testPathIgnorePatterns: Tells Jest which directories to ignore
 */

module.exports = {
  // Use jsdom environment to simulate a browser for React component testing
  // This provides DOM APIs like document, window, etc. that React needs
  testEnvironment: 'jsdom',
  
  // Run setupTests.ts before each test file to configure the testing environment
  // This file contains global mocks and test utilities
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.ts'],
  
  // Module name mapping for cleaner imports
  // Allows us to use '@/components/Button' instead of '../../../components/Button'
  moduleNameMapping: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  
  // Specify which files to include in coverage reports
  // The '!' prefix excludes files from coverage collection
  collectCoverageFrom: [
    'src/components/auth/**/*.{js,jsx,ts,tsx}',  // Authentication components
    'src/components/ui/**/*.{js,jsx,ts,tsx}',    // UI components
    'src/services/**/*.{js,jsx,ts,tsx}',         // API services
    'src/store/**/*.{js,jsx,ts,tsx}',            // State management
    'src/types/**/*.{js,jsx,ts,tsx}',            // TypeScript type definitions
    '!src/**/*.d.ts',                            // Exclude TypeScript declaration files
    '!src/**/*.test.{js,jsx,ts,tsx}',            // Exclude test files themselves
    '!src/**/*.spec.{js,jsx,ts,tsx}',            // Exclude spec files
  ],
  
  // Set minimum coverage thresholds that must be met
  // If coverage falls below these percentages, tests will fail
  coverageThreshold: {
    global: {
      branches: 80,    // 80% of code branches must be tested
      functions: 80,   // 80% of functions must be tested
      lines: 80,       // 80% of lines must be executed
      statements: 80,  // 80% of statements must be executed
    },
  },
  
  // Generate coverage reports in multiple formats
  coverageReporters: [
    'text',   // Text output in terminal
    'lcov',   // LCOV format for CI/CD tools
    'html',   // HTML report for viewing in browser
  ],
  
  // Tell Jest which files are test files
  // These patterns match files in __tests__ directories or files ending with .test/.spec
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{test,spec}.{js,jsx,ts,tsx}',
  ],
  
  // Transform files using Babel before running tests
  // This allows us to use modern JavaScript/TypeScript features
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest',
  },
  
  // File extensions that Jest should recognize as modules
  moduleFileExtensions: ['js', 'jsx', 'ts', 'tsx', 'json'],
  
  // Directories to ignore when looking for test files
  testPathIgnorePatterns: [
    '<rootDir>/node_modules/',  // Don't test third-party packages
    '<rootDir>/build/',         // Don't test build output
  ],
};

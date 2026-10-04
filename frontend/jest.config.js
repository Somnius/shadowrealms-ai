/**
 * Jest configuration (the only one; package.json has no "jest" key).
 *
 * These are the settings Create React App used to supply, kept so the tests behave the same:
 * jsdom, src/setupTests.js, the same test file patterns, resetMocks, and the d3 packages
 * (ES modules only) compiled by Babel. Vite doesn't take part in the tests.
 */
module.exports = {
  roots: ['<rootDir>/src'],
  testEnvironment: 'jsdom',
  setupFiles: ['<rootDir>/jest/polyfills.js'],
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{spec,test}.{js,jsx,ts,tsx}',
  ],
  transform: {
    '^.+\\.(js|jsx|mjs|cjs)$': [
      'babel-jest',
      {
        presets: [
          ['@babel/preset-env', { targets: { node: 'current' } }],
          ['@babel/preset-react', { runtime: 'automatic' }],
        ],
        babelrc: false,
        configFile: false,
      },
    ],
  },
  // d3-* and internmap ship only ES modules, so they go through Babel too
  transformIgnorePatterns: ['node_modules/(?!(d3-[a-z-]+|internmap)/)'],
  moduleNameMapper: {
    '\\.(css|less|sass|scss)$': 'identity-obj-proxy',
    '\\.(png|jpe?g|gif|webp|avif|ico|svg|woff2?|ttf|eot|mp3|mp4|webm)$': '<rootDir>/jest/fileStub.js',
  },
  moduleFileExtensions: ['js', 'jsx', 'mjs', 'cjs', 'json', 'node'],
  resetMocks: true,
  collectCoverageFrom: ['src/**/*.{js,jsx}', '!src/**/*.d.ts'],
  coverageReporters: ['text', 'lcov', 'html'],
};

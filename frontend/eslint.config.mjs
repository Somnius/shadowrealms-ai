// ESLint flat config (replaces CRA's eslint-config-react-app). Run with `npm run lint`.
// Not part of `npm run build`; the existing warnings are cleaned up separately.
import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['build/', 'coverage/', 'node_modules/'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,mjs,cjs}'],
    ...react.configs.flat.recommended,
    ...react.configs.flat['jsx-runtime'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      // process.env.NODE_ENV is replaced at build time
      globals: { ...globals.browser, process: 'readonly' },
    },
    settings: { react: { version: 'detect' } },
    plugins: { react, 'react-hooks': reactHooks },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...react.configs.flat['jsx-runtime'].rules,
      // Same severity as CRA had; existing findings are warnings, not errors
      'no-unused-vars': ['warn', { args: 'none', ignoreRestSiblings: true }],
      'no-irregular-whitespace': 'warn',
      'react/no-unescaped-entities': 'warn',
      'react/prop-types': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    files: ['src/**/__tests__/**', 'src/**/*.test.{js,jsx}', 'src/setupTests.js', 'src/design/testing/**'],
    languageOptions: { globals: { ...globals.jest, ...globals.node } },
  },
  {
    files: ['*.{js,mjs,cjs}', 'jest/**', 'scripts/**', 'src/**/*.node.js'],
    languageOptions: { globals: { ...globals.node } },
  },
];

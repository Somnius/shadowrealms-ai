/**
 * Jest setup (loaded automatically by react-scripts before every test file).
 *
 * jsdom doesn't ship a few browser APIs the app uses, so we fill them in here.
 */
import '@testing-library/jest-dom';
import { webcrypto } from 'crypto';

// SimpleApp reads the viewport through matchMedia on mount
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
}

// security.js generates CSRF tokens with crypto.getRandomValues
if (!globalThis.crypto || !globalThis.crypto.getRandomValues) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
}

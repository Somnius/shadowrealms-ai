// Create React App's Jest setup loaded a fetch polyfill (react-app-polyfill/jsdom); jsdom has no
// fetch of its own. Tests mock it (jest.spyOn(global, 'fetch') needs it to exist); unmocked calls fail.
if (typeof globalThis.fetch !== 'function') {
  globalThis.fetch = () => Promise.reject(new TypeError('fetch is not available in tests; mock it'));
}

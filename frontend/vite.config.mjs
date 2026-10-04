import path from 'node:path';
import { defineConfig, loadEnv, transformWithOxc } from 'vite';
import react from '@vitejs/plugin-react';

// Most components are .js files with JSX in them (a CRA habit). Vite only parses JSX in .jsx, so
// compile the JSX in src/**/*.js first; Vite and the React plugin then treat the output as plain JS
// (fast refresh still applies). Cheaper than renaming every file.
function jsxInJsFiles() {
  let isDev = false;
  let srcDir = '';
  return {
    name: 'sr:jsx-in-js',
    enforce: 'pre',
    configResolved(config) {
      isDev = config.command === 'serve';
      srcDir = path.resolve(config.root, 'src') + path.sep;
    },
    async transform(code, id) {
      const file = id.split('?')[0];
      if (!file.endsWith('.js') || !file.startsWith(srcDir) || file.includes('/node_modules/')) return null;
      const result = await transformWithOxc(code, file, {
        lang: 'jsx',
        jsx: { runtime: 'automatic', development: isDev },
        sourcemap: true,
      });
      return { code: result.code, map: result.map };
    },
  };
}

export default defineConfig(({ mode }) => {
  // Old CRA-style variables still work: REACT_APP_* is readable as import.meta.env.REACT_APP_*
  // and as process.env.REACT_APP_* (process.env.NODE_ENV is replaced by Vite itself).
  const reactAppEnv = loadEnv(mode, process.cwd(), 'REACT_APP_');
  const define = Object.fromEntries(
    Object.entries(reactAppEnv).map(([key, value]) => [`process.env.${key}`, JSON.stringify(value)])
  );

  // Optional for running the dev server without nginx in front: API_PROXY_TARGET=http://127.0.0.1:5000
  const apiTarget = process.env.API_PROXY_TARGET;

  return {
    plugins: [jsxInJsFiles(), react()],
    envPrefix: ['VITE_', 'REACT_APP_'],
    define,
    server: {
      host: '0.0.0.0',
      port: 3000,
      strictPort: true,
      // nginx proxies to the dev server under its upstream name (Host: frontend); localhost and
      // IP addresses are allowed by default
      allowedHosts: ['frontend'],
      proxy: apiTarget ? { '/api': { target: apiTarget } } : undefined,
    },
    // The dev server's dependency scan reads src/ too, so it needs to know .js may contain JSX
    optimizeDeps: { rolldownOptions: { moduleTypes: { '.js': 'jsx' } } },
    preview: { host: '0.0.0.0', port: 3000, strictPort: true },
    build: {
      // nginx serves frontend/build and caches /static/ for a year (nginx/nginx.conf)
      outDir: 'build',
      assetsDir: 'static',
      sourcemap: false,
      // Vite ignores package.json browserslist. Keep about the floor CRA built for, so older
      // Safari/Chrome still parse the bundle and CSS fallbacks (100vh before 100dvh) stay.
      target: ['chrome109', 'edge109', 'firefox115', 'safari15.6', 'ios15.6'],
      cssTarget: ['chrome109', 'safari15', 'firefox115'],
      // The polyfill is an inline script, which the Content-Security-Policy (script-src 'self') blocks
      modulePreload: { polyfill: false },
    },
  };
});

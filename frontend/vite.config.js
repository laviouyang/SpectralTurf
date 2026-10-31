import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Requests to /api/... are passed on to our Python backend on port 8000.
// So the page only ever talks to the address it was loaded from, which also
// works when someone opens it through a share link (see README "Sharing a link").
const backendProxy = { '/api': 'http://localhost:8000' };

// Vite is the tool that runs our React app (npm run dev) and serves the
// finished build (npm run share).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: backendProxy },
  preview: {
    port: 4173,
    proxy: backendProxy,
    // Only allow our own computer and Cloudflare's temporary share links.
    allowedHosts: ['.trycloudflare.com'],
  },
});

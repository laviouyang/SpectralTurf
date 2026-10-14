import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite is the tool that runs our React app during development (npm run dev).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});

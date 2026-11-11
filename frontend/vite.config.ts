import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// /api/* is forwarded to FastAPI, so no CORS setup is needed in dev.
// --host lets a phone on the same Wi-Fi open the app (http://<laptop-ip>:5173).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});

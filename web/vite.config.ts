import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // FastAPI backend — uvicorn api.main:app --reload --port 8000, run from
      // the trading-platform/ repo root. Frontend code always calls relative
      // /api/... paths, dev and prod alike.
      "/api": {
        target: "http://localhost:8000",
        // false, not true: the API refuses a state-changing request whose
        // Origin does not match its Host (api/auth.py's require_user).
        // changeOrigin rewrote Host to localhost:8000 while the browser's
        // Origin stayed localhost:5173, so every save and run made through
        // `npm run dev` came back 403 "Cross-origin request refused".
        // Keeping the browser's Host is what production's nginx does
        // (proxy_set_header Host $host). Dev server only -- `vite build` does
        // not read this block.
        changeOrigin: false,
        ws: true, // needed for the Phase 3 replay WebSocket
      },
    },
  },
})

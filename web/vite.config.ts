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
        changeOrigin: true,
        ws: true, // needed for the Phase 3 replay WebSocket
      },
    },
  },
})

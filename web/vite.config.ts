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
  // THE SAME PROXY, FOR `vite preview`.
  //
  // The end-to-end suite runs against a BUILT app -- that is the point of it,
  // since three of the bugs it exists to catch only appear after the CSS has
  // been through the minifier and Tailwind's layers have been flattened. A
  // built app is static files, which have no proxy, so `vite preview` needs
  // its own; `server.proxy` above is read by `vite dev` and nothing else.
  //
  // E2E_API_TARGET lets the runner point this at the throwaway API it started
  // on a free port, instead of whatever is on 8000.
  preview: {
    proxy: {
      "/api": {
        target: process.env.E2E_API_TARGET ?? "http://localhost:8000",
        // false for the same reason as above: the API compares Origin against
        // Host and refuses a state-changing request when they disagree.
        changeOrigin: false,
        ws: true,
      },
    },
  },
})

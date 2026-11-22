// Builds offline-export/ -- the whole app answered from a recording, for sir -- into one bundle
// that pack_offline.py inlines into a single HTML file. Not part of the app build.
import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  // root is the web app itself, so the CSS build sees every class the app uses
  root: __dirname,
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: [
      { find: "@", replacement: path.resolve(__dirname, "./src") },
    ],
  },
  build: {
    outDir: process.env.VIEWER_OUT ?? path.resolve(__dirname, "offline-export/dist"),
    emptyOutDir: true,
    assetsInlineLimit: 100_000_000,
    cssCodeSplit: false,
    rollupOptions: { input: path.resolve(__dirname, "offline-export/index.html"), output: { codeSplitting: false } },
  },
})

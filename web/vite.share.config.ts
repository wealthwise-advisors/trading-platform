// Serving the built app through a temporary share link (a tunnel to this laptop):
// the same config as the app, plus accepting the tunnel's host name. Not used by the app build.
import base from "./vite.config"
import { mergeConfig } from "vite"

export default mergeConfig(base, {
  server: { allowedHosts: true },
  preview: { allowedHosts: true },
})

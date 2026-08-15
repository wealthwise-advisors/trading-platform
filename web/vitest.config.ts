// Vitest lives in its own config rather than a `test` block inside
// vite.config.ts so the dev/build config stays free of test-only concerns and
// the app build never has to resolve vitest.
//
// Environment is plain node: every module under test is pure logic (timestamp
// serialization, bucketing, shape geometry). Nothing here needs a DOM, and
// avoiding jsdom keeps the suite in the tens of milliseconds.

import path from "path"
import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    reporters: "verbose",
  },
})

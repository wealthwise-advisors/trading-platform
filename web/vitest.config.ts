// Vitest lives in its own config rather than a `test` block inside
// vite.config.ts so the dev/build config stays free of test-only concerns and
// the app build never has to resolve vitest.
//
// Environment is plain node for the logic suites: most modules under test are
// pure (timestamp serialization, bucketing, shape geometry), and avoiding jsdom
// keeps those in the tens of milliseconds.
//
// The accessibility suites are the exception. They render real components and
// run axe-core against the result, which needs a DOM, so *.a11y.test.tsx opts
// into jsdom with a `@vitest-environment jsdom` docblock at the top of the file. That keeps
// the fast suite fast and still lets accessibility be MEASURED rather than
// asserted from the presence of aria- attributes.

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
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/*.a11y.test.tsx"],
    reporters: "verbose",
  },
})

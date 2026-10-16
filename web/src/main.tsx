import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { WorkspaceLoader } from './components/WorkspaceLoader'
import { ErrorBoundary } from './components/ErrorBoundary'
import { installGlobalCrashHandlers } from './lib/crashReporter'

const queryClient = new QueryClient()

// Before the first render: an error thrown during startup is exactly the
// one worth catching, and the boundary below cannot see a rejected promise.
installGlobalCrashHandlers()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* OUTSIDE the providers and the loader, deliberately. A boundary only
        catches what renders beneath it, so one placed inside the loader would
        miss a throw in the loader itself -- and it is the first thing that
        runs, which makes it the most expensive place to go blank. */}
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {/* No sign-in (removed 2026-10-16): the loader fetches the workspace
            account the app runs as, shows the first-run introduction if it is
            due, and then renders the dashboard straight away. */}
        <WorkspaceLoader>{(user) => <App user={user} />}</WorkspaceLoader>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)

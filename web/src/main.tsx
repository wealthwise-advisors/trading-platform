import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { AuthGate } from './components/AuthGate'
import { ErrorBoundary } from './components/ErrorBoundary'
import { installGlobalCrashHandlers } from './lib/crashReporter'

const queryClient = new QueryClient()

// Before the first render: an error thrown during startup is exactly the
// one worth catching, and the boundary below cannot see a rejected promise.
installGlobalCrashHandlers()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* OUTSIDE the providers and the gate, deliberately. A boundary only
        catches what renders beneath it, so one placed inside AuthGate would
        miss a throw in the gate itself -- and the gate is the first thing that
        runs, which makes it the most expensive place to go blank. */}
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {/* The gate wraps the whole app so no panel mounts, and no request is
            fired, before the session is known. The real boundary is the API's
            401 -- this only avoids a dashboard of failed panels. */}
        <AuthGate>{(user) => <App user={user} />}</AuthGate>
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
)

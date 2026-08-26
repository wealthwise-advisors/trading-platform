import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { AuthGate } from './components/AuthGate'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* The gate wraps the whole app so no panel mounts, and no request is
          fired, before the session is known. The real boundary is the API's
          401 -- this only avoids a dashboard of failed panels. */}
      <AuthGate>{() => <App />}</AuthGate>
    </QueryClientProvider>
  </StrictMode>,
)

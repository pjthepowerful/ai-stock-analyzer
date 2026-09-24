import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './design/tokens.css'
import './design/ui.css'
import App from './app/App'
import { LaunchGate } from './features/launch/LaunchGate'
import { SessionProvider } from './lib/auth'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 15_000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <LaunchGate>
          <App />
        </LaunchGate>
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
)

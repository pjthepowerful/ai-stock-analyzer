import { createContext, useContext } from 'react'
import type { ChatMessage } from './api'

// App-level sheets any screen can open without prop-drilling through Shell.
export interface Chrome {
  openPlus: () => void
  openReport: (transcript?: ChatMessage[]) => void
  /** Open a ticker in Analyze from anywhere in the app. */
  analyze: (ticker: string) => void
}

export const ChromeContext = createContext<Chrome | null>(null)

export function useChrome() {
  const ctx = useContext(ChromeContext)
  if (!ctx) throw new Error('useChrome must be used within Shell')
  return ctx
}

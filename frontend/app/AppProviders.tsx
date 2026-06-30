import type { ReactNode } from 'react'
import { Toaster } from 'react-hot-toast'
import { ArenaDataProvider } from '@/contexts/ArenaDataContext'
import { AuthProvider } from '@/contexts/AuthContext'
import { ExchangeProvider } from '@/contexts/ExchangeContext'
import { TradingModeProvider } from '@/contexts/TradingModeContext'

interface AppProvidersProps {
  children: ReactNode
}

export default function AppProviders({ children }: AppProvidersProps) {
  return (
    <AuthProvider>
      <ExchangeProvider>
        <TradingModeProvider>
          <ArenaDataProvider>
            <Toaster position="top-right" />
            {children}
          </ArenaDataProvider>
        </TradingModeProvider>
      </ExchangeProvider>
    </AuthProvider>
  )
}
